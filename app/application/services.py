"""Camada de aplicação: casos de uso que orquestram domínio e infraestrutura em transações."""
import hashlib
from dataclasses import dataclass
from typing import Optional

from ..config import Settings
from ..domain.entities import (CanalPedido, ItemPedido, Pedido, Perfil, PONTOS_MINIMOS_RESGATE, StatusPagamento,
                               StatusPedido, STATUS_PERMITIDOS_POR_PERFIL, TipoMovimento, Usuario, calcular_pontos)
from ..domain.errors import (ConflictError, ForbiddenError, GatewayUnavailableError, NotFoundError,
                             UnauthorizedError, ValidationError)
from ..infrastructure.db import agora_iso, transaction
from ..infrastructure.payment_gateway import PaymentGatewayMock
from ..infrastructure.repositories import (AuditoriaRepository, ConsentimentoRepository, EstoqueRepository,
                                           FidelidadeRepository, PagamentoRepository, PedidoRepository,
                                           ProdutoRepository, PromocaoRepository, UnidadeRepository, UsuarioRepository)
from ..infrastructure.security import TokenService, hash_senha, verificar_senha
from .validation import Validador, exigir_objeto_json

FORMAS_PAGAMENTO = ("MOCK", "PIX", "CREDITO", "DEBITO")
SENHA_FICTICIA = hash_senha("senha-ficticia-para-igualar-tempo-de-resposta-1")


@dataclass
class Contexto:
    usuario: Optional[Usuario]
    request_id: str


def exigir_escopo_unidade(usuario: Usuario, unidade_id: int):
    """Equipe vinculada a uma unidade só opera nela; ADMIN e usuários sem unidade têm visão da rede."""
    if usuario.perfil == Perfil.ADMIN.value or usuario.unidade_id is None:
        return
    if usuario.unidade_id != unidade_id:
        raise ForbiddenError("Seu perfil não tem acesso a esta unidade.", code="UNIDADE_FORA_DO_ESCOPO")


class Servicos:
    """Fábrica de casos de uso ligados a uma conexão (uma por requisição)."""

    def __init__(self, conn, settings: Settings, tokens: TokenService, gateway: PaymentGatewayMock):
        self.conn, self.settings, self.tokens, self.gateway = conn, settings, tokens, gateway
        self.usuarios = UsuarioRepository(conn)
        self.consentimentos = ConsentimentoRepository(conn)
        self.unidades = UnidadeRepository(conn)
        self.produtos = ProdutoRepository(conn)
        self.estoque = EstoqueRepository(conn)
        self.promocoes = PromocaoRepository(conn)
        self.pedidos = PedidoRepository(conn)
        self.pagamentos = PagamentoRepository(conn)
        self.fidelidade = FidelidadeRepository(conn)
        self.auditoria = AuditoriaRepository(conn)

    # ---------------------------------------------------------------- auditoria
    def auditar(self, ctx: Contexto, acao, entidade, entidade_id=None, detalhes=None):
        u = ctx.usuario
        self.auditoria.registrar(u.id if u else None, u.perfil if u else None, acao, entidade, entidade_id,
                                 detalhes, ctx.request_id, agora_iso())

    def listar_auditoria(self, ctx, args, page, limit, offset):
        itens, total = self.auditoria.listar(args.get("acao"), args.get("entidade"), args.get("entidadeId"), limit, offset)
        return itens, total

    # ---------------------------------------------------------------- autenticação
    def registrar_cliente(self, ctx, dados):
        dados = exigir_objeto_json(dados)
        v = Validador(dados)
        nome = v.texto("nome", 2, 100)
        email = v.email("email")
        senha = v.senha("senha")
        aceite = v.booleano("aceitePoliticaPrivacidade")
        if aceite is False:
            v._falha("aceitePoliticaPrivacidade", "o aceite da política de privacidade é obrigatório para o cadastro")
        v.concluir()
        with transaction(self.conn):
            if self.usuarios.por_email(email):
                raise ConflictError("Já existe um cadastro com este e-mail.", code="EMAIL_JA_CADASTRADO",
                                    details=[{"field": "email", "issue": "já cadastrado"}])
            usuario = self.usuarios.criar(nome, email, hash_senha(senha), Perfil.CLIENTE.value, None, agora_iso())
            self.auditar(Contexto(usuario, ctx.request_id), "USUARIO_CRIADO", "usuario", usuario.id, {"perfil": usuario.perfil})
        return usuario

    def login(self, ctx, dados):
        dados = exigir_objeto_json(dados)
        v = Validador(dados)
        email = v.email("email")
        senha = v._presente("senha", True)
        v.concluir()
        usuario = self.usuarios.por_email(email)
        senha_ok = verificar_senha(str(senha), usuario.senha_hash if usuario else SENHA_FICTICIA)
        if not usuario or not usuario.ativo or not senha_ok:
            with transaction(self.conn):
                self.auditar(ctx, "LOGIN_FALHA", "usuario", None, {"motivo": "CREDENCIAIS_INVALIDAS"})
            raise UnauthorizedError("E-mail ou senha inválidos.", code="CREDENCIAIS_INVALIDAS")
        with transaction(self.conn):
            self.auditar(Contexto(usuario, ctx.request_id), "LOGIN_SUCESSO", "usuario", usuario.id)
        return usuario, self.tokens.emitir(usuario.id, usuario.perfil)

    # ---------------------------------------------------------------- usuários / LGPD
    def criar_usuario_equipe(self, ctx, dados):
        dados = exigir_objeto_json(dados)
        v = Validador(dados)
        nome, email, senha = v.texto("nome", 2, 100), v.email("email"), v.senha("senha")
        perfil = v.enum("perfil", Perfil)
        unidade_id = v.inteiro("unidadeId", minimo=1, obrigatorio=False)
        v.concluir()
        if perfil != Perfil.ADMIN and perfil != Perfil.CLIENTE and unidade_id is None:
            raise ValidationError("Usuários de equipe devem ser vinculados a uma unidade.",
                                  [{"field": "unidadeId", "issue": "campo obrigatório para este perfil"}])
        with transaction(self.conn):
            if unidade_id and not self.unidades.por_id(unidade_id):
                raise NotFoundError("Unidade não encontrada.", code="UNIDADE_NAO_ENCONTRADA")
            if self.usuarios.por_email(email):
                raise ConflictError("Já existe um cadastro com este e-mail.", code="EMAIL_JA_CADASTRADO")
            usuario = self.usuarios.criar(nome, email, hash_senha(senha), perfil.value, unidade_id, agora_iso())
            self.auditar(ctx, "USUARIO_CRIADO", "usuario", usuario.id, {"perfil": perfil.value})
        return usuario

    def obter_usuario(self, ctx, uid):
        usuario = self.usuarios.por_id(uid)
        if not usuario:
            raise NotFoundError("Usuário não encontrado.", code="USUARIO_NAO_ENCONTRADO")
        with transaction(self.conn):
            self.auditar(ctx, "DADOS_USUARIO_CONSULTADOS", "usuario", uid)
        return usuario

    def listar_usuarios(self, ctx, limit, offset):
        with transaction(self.conn):
            self.auditar(ctx, "LISTA_USUARIOS_CONSULTADA", "usuario")
        return self.usuarios.listar(limit, offset)

    def anonimizar_conta(self, ctx):
        """Direito de eliminação (LGPD art. 18): remove dados pessoais, preserva pedidos para fins fiscais."""
        u = ctx.usuario
        with transaction(self.conn):
            anonimo = f"anonimo-{hashlib.sha256(str(u.id).encode()).hexdigest()[:12]}@anonimizado.invalid"
            self.usuarios.anonimizar(u.id, anonimo, hash_senha(hashlib.sha256(anonimo.encode()).hexdigest()))
            self.consentimentos.registrar(u.id, False, agora_iso())
            self.auditar(ctx, "USUARIO_ANONIMIZADO", "usuario", u.id)

    # ---------------------------------------------------------------- unidades, produtos, cardápio
    def criar_unidade(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        nome, cidade = v.texto("nome", 2, 100), v.texto("cidade", 2, 100)
        uf = v.texto("uf", 2, 2)
        v.concluir()
        with transaction(self.conn):
            try:
                unidade = self.unidades.criar(nome, cidade, uf.upper(), agora_iso())
            except Exception as exc:
                if "UNIQUE" in str(exc):
                    raise ConflictError("Já existe uma unidade com este nome.", code="UNIDADE_DUPLICADA")
                raise
            self.auditar(ctx, "UNIDADE_CRIADA", "unidade", unidade.id)
        return unidade

    def obter_unidade(self, uid):
        unidade = self.unidades.por_id(uid)
        if not unidade:
            raise NotFoundError("Unidade não encontrada.", code="UNIDADE_NAO_ENCONTRADA")
        return unidade

    def atualizar_unidade(self, ctx, uid, dados):
        dados = exigir_objeto_json(dados)
        v = Validador(dados)
        nome = v.texto("nome", 2, 100, obrigatorio=False)
        ativa = v.booleano("ativa", obrigatorio=False)
        v.concluir()
        with transaction(self.conn):
            unidade = self.obter_unidade(uid)
            self.unidades.atualizar(uid, nome or unidade.nome, unidade.ativa if ativa is None else ativa)
            self.auditar(ctx, "UNIDADE_ATUALIZADA", "unidade", uid, {"ativa": ativa})
        return self.unidades.por_id(uid)

    def criar_produto(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        nome = v.texto("nome", 2, 100)
        descricao = v.texto("descricao", 1, 300, obrigatorio=False)
        preco = v.dinheiro_centavos("precoBase")
        v.concluir()
        with transaction(self.conn):
            try:
                produto = self.produtos.criar(nome, descricao, preco, agora_iso())
            except Exception as exc:
                if "UNIQUE" in str(exc):
                    raise ConflictError("Já existe um produto com este nome.", code="PRODUTO_DUPLICADO")
                raise
            self.auditar(ctx, "PRODUTO_CRIADO", "produto", produto.id)
        return produto

    def obter_produto(self, pid):
        produto = self.produtos.por_id(pid)
        if not produto:
            raise NotFoundError("Produto não encontrado.", code="PRODUTO_NAO_ENCONTRADO")
        return produto

    def definir_item_cardapio(self, ctx, unidade_id, produto_id, dados):
        v = Validador(exigir_objeto_json(dados))
        preco = v.dinheiro_centavos("preco")
        disponivel = v.booleano("disponivel", obrigatorio=False)
        v.concluir()
        exigir_escopo_unidade(ctx.usuario, unidade_id)
        with transaction(self.conn):
            self.obter_unidade(unidade_id)
            self.obter_produto(produto_id)
            self.produtos.definir_item_cardapio(unidade_id, produto_id, preco, True if disponivel is None else disponivel)
            self.auditar(ctx, "CARDAPIO_ATUALIZADO", "cardapio", f"{unidade_id}/{produto_id}", {"precoCentavos": preco})
        return self.produtos.item_cardapio(unidade_id, produto_id)

    # ---------------------------------------------------------------- estoque
    def movimentar_estoque(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        unidade_id = v.inteiro("unidadeId", minimo=1)
        produto_id = v.inteiro("produtoId", minimo=1)
        tipo = v.enum("tipo", TipoMovimento)
        quantidade = v.inteiro("quantidade", minimo=1, maximo=100000)
        motivo = v.texto("motivo", 3, 120)
        v.concluir()
        exigir_escopo_unidade(ctx.usuario, unidade_id)
        with transaction(self.conn):
            self.obter_unidade(unidade_id)
            self.obter_produto(produto_id)
            if tipo == TipoMovimento.ENTRADA:
                self.estoque.entrada(unidade_id, produto_id, quantidade)
            elif not self.estoque.saida_condicional(unidade_id, produto_id, quantidade):
                raise ConflictError("Saldo insuficiente para a saída solicitada.", code="ESTOQUE_INSUFICIENTE",
                                    details=[{"field": "quantidade", "issue": f"Disponível: {self.estoque.saldo(unidade_id, produto_id)}"}])
            self.estoque.registrar_movimento(unidade_id, produto_id, tipo.value, quantidade, motivo, None, ctx.usuario.id, agora_iso())
            self.auditar(ctx, f"ESTOQUE_{tipo.value}", "estoque", f"{unidade_id}/{produto_id}", {"quantidade": quantidade, "motivo": motivo})
        return {"unidadeId": unidade_id, "produtoId": produto_id, "saldo": self.estoque.saldo(unidade_id, produto_id)}

    # ---------------------------------------------------------------- pedidos
    def _acesso_pedido(self, ctx, pedido: Pedido):
        u = ctx.usuario
        if u.perfil == Perfil.CLIENTE.value:
            if pedido.cliente_id != u.id:
                raise NotFoundError("Pedido não encontrado.", code="PEDIDO_NAO_ENCONTRADO")
        else:
            exigir_escopo_unidade(u, pedido.unidade_id)

    def _pedido_ou_404(self, pid) -> Pedido:
        pedido = self.pedidos.por_id(pid)
        if not pedido:
            raise NotFoundError("Pedido não encontrado.", code="PEDIDO_NAO_ENCONTRADO")
        return pedido

    def criar_pedido(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        canal = v.enum("canalPedido", CanalPedido)
        unidade_id = v.inteiro("unidadeId", minimo=1)
        forma = v.texto("formaPagamento", 3, 20)
        if forma and forma.upper() not in FORMAS_PAGAMENTO:
            v._falha("formaPagamento", "valor inválido. Aceitos: " + ", ".join(FORMAS_PAGAMENTO))
        cliente_id_req = v.inteiro("clienteId", minimo=1, obrigatorio=False)
        codigo = v.texto("codigoPromocao", 3, 30, obrigatorio=False)
        brutos = dados.get("itens")
        itens_validos = []
        if not isinstance(brutos, list) or not brutos:
            v._falha("itens", "deve conter ao menos um item")
        else:
            if len(brutos) > 50:
                v._falha("itens", "máximo de 50 itens por pedido")
            for i, bruto in enumerate(brutos[:50]):
                if not isinstance(bruto, dict):
                    v._falha(f"itens[{i}]", "deve ser um objeto")
                    continue
                sub = Validador(bruto)
                pid, qtd = sub.inteiro("produtoId", minimo=1), sub.inteiro("quantidade", minimo=1, maximo=100)
                v.problemas += [{"field": f"itens[{i}].{p['field']}", "issue": p["issue"]} for p in sub.problemas]
                if pid and qtd:
                    itens_validos.append((i, pid, qtd))
        v.concluir()

        u = ctx.usuario
        if u.perfil == Perfil.CLIENTE.value:
            if cliente_id_req not in (None, u.id):
                raise ForbiddenError("Clientes só podem criar pedidos em seu próprio nome.", code="CLIENTE_DIVERGENTE")
            cliente_id = u.id
        else:
            if cliente_id_req is None:
                raise ValidationError("Informe o cliente do pedido.", [{"field": "clienteId", "issue": "campo obrigatório para a equipe"}])
            cliente_id = cliente_id_req
            exigir_escopo_unidade(u, unidade_id)

        with transaction(self.conn):
            cliente = self.usuarios.por_id(cliente_id)
            if not cliente or cliente.perfil != Perfil.CLIENTE.value or not cliente.ativo:
                raise NotFoundError("Cliente não encontrado.", code="CLIENTE_NAO_ENCONTRADO")
            unidade = self.obter_unidade(unidade_id)
            if not unidade.ativa:
                raise ConflictError("A unidade está inativa.", code="UNIDADE_INATIVA")
            consolidados: dict[int, dict] = {}
            for i, pid, qtd in itens_validos:
                if pid in consolidados:
                    consolidados[pid]["quantidade"] += qtd
                    continue
                self.obter_produto(pid)
                cardapio = self.produtos.item_cardapio(unidade_id, pid)
                if not cardapio:
                    raise NotFoundError("Produto não consta no cardápio da unidade.", code="PRODUTO_FORA_DO_CARDAPIO",
                                        details=[{"field": f"itens[{i}].produtoId", "issue": "inexistente nesta unidade"}])
                if not cardapio.disponivel:
                    raise ConflictError("Produto indisponível nesta unidade.", code="PRODUTO_INDISPONIVEL",
                                        details=[{"field": f"itens[{i}].produtoId", "issue": "indisponível"}])
                consolidados[pid] = {"indice": i, "quantidade": qtd, "preco": cardapio.preco_centavos}
            faltas = []
            for pid, c in consolidados.items():
                saldo = self.estoque.saldo(unidade_id, pid)
                if saldo < c["quantidade"]:
                    faltas.append({"field": f"itens[{c['indice']}].quantidade", "issue": f"Disponível: {saldo}"})
            if faltas:
                raise ConflictError("Não há quantidade suficiente para um ou mais itens.", faltas, code="ESTOQUE_INSUFICIENTE")

            itens = [ItemPedido(pid, c["quantidade"], c["preco"]) for pid, c in consolidados.items()]
            subtotal = sum(i.subtotal_centavos for i in itens)
            desconto, promocao_id = 0, None
            if codigo:
                promocao = self.promocoes.por_codigo(codigo.upper())
                if not promocao:
                    raise NotFoundError("Promoção não encontrada.", code="PROMOCAO_NAO_ENCONTRADA")
                desconto = promocao.calcular_desconto(subtotal, agora_iso())
                promocao_id = promocao.id
            agora = agora_iso()
            pedido = self.pedidos.criar(Pedido(None, cliente_id, unidade_id, canal.value, StatusPedido.AGUARDANDO_PAGAMENTO.value,
                                               subtotal, desconto, subtotal - desconto, promocao_id, forma.upper(), agora, agora, itens))
            for item in itens:
                if not self.estoque.saida_condicional(unidade_id, item.produto_id, item.quantidade):
                    raise ConflictError("Estoque alterado durante a operação.", code="ESTOQUE_INSUFICIENTE")
                self.estoque.registrar_movimento(unidade_id, item.produto_id, TipoMovimento.SAIDA.value, item.quantidade,
                                                 "VENDA", pedido.id, u.id, agora)
            self.auditar(ctx, "PEDIDO_CRIADO", "pedido", pedido.id,
                         {"canalPedido": canal.value, "unidadeId": unidade_id, "totalCentavos": pedido.total_centavos})
        return pedido

    def obter_pedido(self, ctx, pid):
        pedido = self._pedido_ou_404(pid)
        self._acesso_pedido(ctx, pedido)
        return pedido, self.pagamentos.do_pedido(pid)

    def listar_pedidos(self, ctx, args, limit, offset):
        v = Validador({"canalPedido": args.get("canalPedido"), "status": args.get("status"), "unidadeId": args.get("unidadeId")})
        canal = v.enum("canalPedido", CanalPedido, obrigatorio=False)
        status = v.enum("status", StatusPedido, obrigatorio=False)
        unidade_id = v.inteiro_texto("unidadeId", minimo=1) if args.get("unidadeId") else None
        v.concluir()
        filtros = {"canal": canal.value if canal else None, "status": status.value if status else None, "unidade_id": unidade_id}
        u = ctx.usuario
        if u.perfil == Perfil.CLIENTE.value:
            filtros["cliente_id"] = u.id
        elif u.perfil != Perfil.ADMIN.value and u.unidade_id is not None:
            if unidade_id not in (None, u.unidade_id):
                raise ForbiddenError("Seu perfil não tem acesso a esta unidade.", code="UNIDADE_FORA_DO_ESCOPO")
            filtros["unidade_id"] = u.unidade_id
        return self.pedidos.listar(filtros, limit, offset)

    def atualizar_status(self, ctx, pid, dados):
        v = Validador(exigir_objeto_json(dados))
        novo = v.enum("status", StatusPedido)
        motivo = v.texto("motivo", 3, 200, obrigatorio=False)
        v.concluir()
        u = ctx.usuario
        with transaction(self.conn):
            pedido = self._pedido_ou_404(pid)
            self._acesso_pedido(ctx, pedido)
            if novo in (StatusPedido.PAGO, StatusPedido.PAGAMENTO_RECUSADO):
                raise ConflictError("Este status só pode ser definido pelo fluxo de pagamento.", code="STATUS_RESERVADO_AO_PAGAMENTO")
            if novo not in STATUS_PERMITIDOS_POR_PERFIL[Perfil(u.perfil)]:
                raise ForbiddenError(f"O perfil {u.perfil} não pode definir o status {novo.value}.", code="PERFIL_SEM_PERMISSAO_PARA_STATUS")
            if novo == StatusPedido.CANCELADO:
                if u.perfil == Perfil.CLIENTE.value and pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO.value:
                    raise ForbiddenError("O cliente só pode cancelar pedidos que aguardam pagamento.", code="CANCELAMENTO_NAO_PERMITIDO")
                if pedido.status in (StatusPedido.PAGO.value, StatusPedido.EM_PREPARO.value) and u.perfil not in (Perfil.GERENTE.value, Perfil.ADMIN.value):
                    raise ForbiddenError("Cancelar pedido já pago exige perfil GERENTE ou ADMIN.", code="CANCELAMENTO_NAO_PERMITIDO")
            anterior = pedido.status
            pedido.validar_transicao(novo)
            agora = agora_iso()
            self.pedidos.atualizar_status(pid, novo.value, agora)
            if novo == StatusPedido.CANCELADO:
                self._devolver_estoque(pedido, u.id, "ESTORNO_CANCELAMENTO", agora)
            self.auditar(ctx, "PEDIDO_CANCELADO" if novo == StatusPedido.CANCELADO else "PEDIDO_STATUS_ALTERADO", "pedido", pid,
                         {"de": anterior, "para": novo.value, "motivo": motivo,
                          **({"estornoPagamento": "NAO_IMPLEMENTADO"} if novo == StatusPedido.CANCELADO and anterior != "AGUARDANDO_PAGAMENTO" else {})})
        return self.pedidos.por_id(pid)

    def _devolver_estoque(self, pedido: Pedido, usuario_id, motivo, agora):
        for item in pedido.itens:
            self.estoque.entrada(pedido.unidade_id, item.produto_id, item.quantidade)
            self.estoque.registrar_movimento(pedido.unidade_id, item.produto_id, TipoMovimento.ENTRADA.value, item.quantidade,
                                             motivo, pedido.id, usuario_id, agora)

    # ---------------------------------------------------------------- pagamento mock
    def solicitar_pagamento(self, ctx, chave, dados):
        v = Validador(exigir_objeto_json(dados))
        pedido_id = v.inteiro("pedidoId", minimo=1)
        metodo = v.texto("metodo", 3, 20, obrigatorio=False)
        simulacao = v.texto("simulacao", 3, 12, obrigatorio=False)
        if simulacao and simulacao.upper() not in {s.value for s in StatusPagamento}:
            v._falha("simulacao", "valor inválido. Aceitos: APROVADO, RECUSADO, FALHA")
        if not chave or not 8 <= len(chave) <= 100:
            v._falha("Idempotency-Key", "cabeçalho obrigatório (8 a 100 caracteres)")
        v.concluir()
        falha: Optional[GatewayUnavailableError] = None
        with transaction(self.conn):
            pedido = self._pedido_ou_404(pedido_id)
            self._acesso_pedido(ctx, pedido)
            existente = self.pagamentos.por_chave(chave)
            if existente:
                if existente["pedido_id"] != pedido_id:
                    raise ConflictError("Idempotency-Key já utilizada em outro pedido.", code="IDEMPOTENCY_KEY_REUTILIZADA")
                if existente["status"] != StatusPagamento.FALHA.value:
                    return existente, pedido, True
                self.conn.execute("DELETE FROM pagamentos WHERE id=?", (existente["id"],))  # nova tentativa após falha
            if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO.value:
                raise ConflictError("O pedido não está aguardando pagamento.", code="PEDIDO_NAO_AGUARDA_PAGAMENTO",
                                    details=[{"field": "pedidoId", "issue": f"Status atual: {pedido.status}"}])
            forma = (metodo or pedido.forma_pagamento).upper()
            enviado = {"pedidoId": pedido.id, "valor": pedido.total_centavos / 100, "moeda": "BRL", "metodo": forma}
            agora = agora_iso()
            try:
                sim = simulacao if self.settings.allow_payment_simulation else None
                retorno = self.gateway.processar(pedido.id, pedido.total_centavos, forma, sim)
            except GatewayUnavailableError as exc:
                falha = exc
                pagamento = self.pagamentos.criar(pedido.id, chave, forma, StatusPagamento.FALHA.value, pedido.total_centavos,
                                                  enviado, None, exc.message, agora)
                self.auditar(ctx, "PAGAMENTO_FALHA", "pagamento", pagamento["id"], {"pedidoId": pedido.id})
            else:
                status = StatusPagamento(retorno["status"])
                pagamento = self.pagamentos.criar(pedido.id, chave, forma, status.value, pedido.total_centavos, enviado, retorno,
                                                  retorno["mensagem"], agora)
                if status == StatusPagamento.APROVADO:
                    self.pedidos.atualizar_status(pedido.id, StatusPedido.PAGO.value, agora)
                    if self.consentimentos.vigente(pedido.cliente_id) and calcular_pontos(pedido.total_centavos) > 0:
                        self.fidelidade.registrar(pedido.cliente_id, "ACUMULO", calcular_pontos(pedido.total_centavos), pedido.id,
                                                  "Pontos por pedido pago", agora)
                else:
                    self.pedidos.atualizar_status(pedido.id, StatusPedido.PAGAMENTO_RECUSADO.value, agora)
                    self._devolver_estoque(pedido, ctx.usuario.id, "ESTORNO_PAGAMENTO_RECUSADO", agora)
                self.auditar(ctx, f"PAGAMENTO_{status.value}", "pagamento", pagamento["id"], {"pedidoId": pedido.id})
        if falha:
            falha.details = falha.details + [{"field": "pagamentoId", "issue": str(pagamento["id"])}]
            raise falha
        return pagamento, self.pedidos.por_id(pedido_id), False

    def obter_pagamento(self, ctx, pid):
        pagamento = self.pagamentos.por_id(pid)
        if not pagamento:
            raise NotFoundError("Pagamento não encontrado.", code="PAGAMENTO_NAO_ENCONTRADO")
        self._acesso_pedido(ctx, self._pedido_ou_404(pagamento["pedido_id"]))
        return pagamento

    # ---------------------------------------------------------------- fidelização
    def definir_consentimento(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        aceito = v.booleano("aceito")
        v.concluir()
        with transaction(self.conn):
            self.consentimentos.registrar(ctx.usuario.id, aceito, agora_iso())
            self.auditar(ctx, "CONSENTIMENTO_FIDELIDADE_ALTERADO", "usuario", ctx.usuario.id, {"aceito": aceito})
        return {"consentimentoFidelidade": aceito}

    def saldo_fidelidade(self, ctx):
        return {"consentimentoFidelidade": self.consentimentos.vigente(ctx.usuario.id), "saldoPontos": self.fidelidade.saldo(ctx.usuario.id)}

    def historico_fidelidade(self, ctx, limit, offset):
        return self.fidelidade.historico(ctx.usuario.id, limit, offset)

    def resgatar_pontos(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        pontos = v.inteiro("pontos", minimo=PONTOS_MINIMOS_RESGATE, maximo=100000)
        v.concluir()
        with transaction(self.conn):
            if not self.consentimentos.vigente(ctx.usuario.id):
                raise ConflictError("O resgate exige consentimento vigente para o programa de fidelidade.", code="CONSENTIMENTO_AUSENTE")
            saldo = self.fidelidade.saldo(ctx.usuario.id)
            if pontos > saldo:
                raise ConflictError("Saldo de pontos insuficiente.", code="SALDO_PONTOS_INSUFICIENTE",
                                    details=[{"field": "pontos", "issue": f"Disponível: {saldo}"}])
            self.fidelidade.registrar(ctx.usuario.id, "RESGATE", pontos, None, "Resgate de pontos", agora_iso())
            self.auditar(ctx, "FIDELIDADE_RESGATE", "usuario", ctx.usuario.id, {"pontos": pontos})
        return {"pontosResgatados": pontos, "saldoPontos": self.fidelidade.saldo(ctx.usuario.id)}

    # ---------------------------------------------------------------- promoções
    def criar_promocao(self, ctx, dados):
        v = Validador(exigir_objeto_json(dados))
        codigo = v.texto("codigo", 3, 30)
        descricao = v.texto("descricao", 3, 200)
        percentual = v.inteiro("percentual", minimo=1, maximo=100)
        minimo = v.dinheiro_centavos("valorMinimo", obrigatorio=False) or 0
        valido_ate = v.data_iso("validoAte")
        if codigo and not all(c.isalnum() or c in "_-" for c in codigo):
            v._falha("codigo", "use apenas letras, números, '_' e '-'")
        v.concluir()
        with transaction(self.conn):
            if self.promocoes.por_codigo(codigo.upper()):
                raise ConflictError("Já existe uma promoção com este código.", code="PROMOCAO_DUPLICADA")
            promocao = self.promocoes.criar(codigo.upper(), descricao, percentual, minimo, valido_ate, agora_iso())
            self.auditar(ctx, "PROMOCAO_CRIADA", "promocao", promocao.id, {"percentual": percentual})
        return promocao

    def atualizar_promocao(self, ctx, pid, dados):
        v = Validador(exigir_objeto_json(dados))
        ativa = v.booleano("ativa")
        v.concluir()
        with transaction(self.conn):
            if not self.promocoes.por_id(pid):
                raise NotFoundError("Promoção não encontrada.", code="PROMOCAO_NAO_ENCONTRADA")
            self.promocoes.definir_ativa(pid, ativa)
            self.auditar(ctx, "PROMOCAO_ATUALIZADA", "promocao", pid, {"ativa": ativa})
        return self.promocoes.por_id(pid)

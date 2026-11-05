"""Controllers REST. Cada rota delega ao caso de uso correspondente na camada de aplicação."""
from flask import g, jsonify, request

from ..application.validation import paginacao
from ..domain.entities import Perfil
from . import serializers as s
from .registry import TODOS, endpoint

EQUIPE = [Perfil.ATENDENTE.value, Perfil.COZINHA.value, Perfil.GERENTE.value, Perfil.ADMIN.value]
GESTAO = [Perfil.GERENTE.value, Perfil.ADMIN.value]
ADMIN = [Perfil.ADMIN.value]
PEDIDOR = [Perfil.CLIENTE.value, Perfil.ATENDENTE.value, Perfil.GERENTE.value, Perfil.ADMIN.value]
E401 = {401: "TOKEN_AUSENTE | TOKEN_INVALIDO | TOKEN_EXPIRADO"}
E403 = {403: "PERFIL_SEM_PERMISSAO"}


def _body():
    return request.get_json(force=True, silent=True)


def _lista(itens, total, page, limit, mapa):
    return jsonify({"items": [mapa(i) for i in itens], "page": page, "limit": limit, "total": total})


PAGINACAO = [("page", "integer", "Página (>=1). Padrão 1"), ("limit", "integer", "Itens por página (1-100). Padrão 10")]
PEDIDO_EX = {"pedidoId": 9001, "clienteId": 3, "unidadeId": 1, "canalPedido": "TOTEM", "status": "AGUARDANDO_PAGAMENTO",
             "subtotal": 62.5, "desconto": 0.0, "total": 62.5, "formaPagamento": "MOCK", "promocaoId": None,
             "itens": [{"produtoId": 1, "quantidade": 2, "precoUnitario": 18.5}, {"produtoId": 3, "quantidade": 1, "precoUnitario": 25.5}],
             "createdAt": "2026-11-04T12:00:00.000000Z", "updatedAt": "2026-11-04T12:00:00.000000Z"}
USUARIO_EX = {"id": 3, "nome": "Maria Souza", "email": "maria@exemplo.com", "perfil": "CLIENTE", "unidadeId": None,
              "ativo": True, "criadoEm": "2026-11-04T12:00:00.000000Z"}


# ------------------------------------------------------------------ infraestrutura
@endpoint("GET", "/health", tag="Infra", resumo="Verifica a disponibilidade da API e do banco.", publico=True,
          response_ex={"status": "UP", "database": "UP"})
def health():
    g.conn.execute("SELECT 1").fetchone()
    return jsonify({"status": "UP", "database": "UP"})


# ------------------------------------------------------------------ auth
@endpoint("POST", "/auth/register", tag="Auth", resumo="Cadastra um cliente (perfil CLIENTE) com aceite da política de privacidade.",
          publico=True, status=201,
          request_ex={"nome": "Maria Souza", "email": "maria@exemplo.com", "senha": "Senha@123", "aceitePoliticaPrivacidade": True},
          response_ex=USUARIO_EX, erros={409: "EMAIL_JA_CADASTRADO", 422: "VALIDACAO_INVALIDA"})
def registrar():
    return jsonify(s.usuario(g.servicos.registrar_cliente(g.ctx, _body()))), 201


@endpoint("POST", "/auth/login", tag="Auth", resumo="Autentica o usuário e devolve um JWT Bearer.", publico=True,
          request_ex={"email": "cliente@raizes.example", "senha": "Cliente@123"},
          response_ex={"accessToken": "eyJhbGciOi...", "tokenType": "Bearer", "expiresIn": 3600,
                       "user": {"id": 4, "nome": "Cliente Demo", "perfil": "CLIENTE"}},
          erros={401: "CREDENCIAIS_INVALIDAS", 422: "VALIDACAO_INVALIDA"})
def login():
    usuario, token = g.servicos.login(g.ctx, _body())
    return jsonify({"accessToken": token, "tokenType": "Bearer", "expiresIn": g.tokens.expires_seconds,
                    "user": {"id": usuario.id, "nome": usuario.nome, "perfil": usuario.perfil}})


# ------------------------------------------------------------------ usuários
@endpoint("GET", "/usuarios/me", tag="Usuários", resumo="Consulta o próprio perfil (minimização: sem hash de senha).",
          response_ex=USUARIO_EX, erros=E401)
def meu_perfil():
    return jsonify(s.usuario(g.ctx.usuario))


@endpoint("DELETE", "/usuarios/me", tag="Usuários", resumo="Anonimiza a própria conta (direito de eliminação, LGPD art. 18).",
          status=204, erros=E401)
def anonimizar_conta():
    g.servicos.anonimizar_conta(g.ctx)
    return "", 204


@endpoint("GET", "/usuarios", tag="Usuários", resumo="Lista usuários (auditada).", roles=ADMIN, query=PAGINACAO,
          response_ex={"items": [USUARIO_EX], "page": 1, "limit": 10, "total": 1}, erros={**E401, **E403})
def listar_usuarios():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.listar_usuarios(g.ctx, limit, offset)
    return _lista(itens, total, page, limit, s.usuario)


@endpoint("POST", "/usuarios", tag="Usuários", resumo="Cria usuário de equipe (ATENDENTE, COZINHA, GERENTE, ADMIN).", roles=ADMIN, status=201,
          request_ex={"nome": "Ana Cozinha", "email": "ana@raizes.example", "senha": "Cozinha@123", "perfil": "COZINHA", "unidadeId": 1},
          response_ex={**USUARIO_EX, "perfil": "COZINHA", "unidadeId": 1},
          erros={**E401, **E403, 409: "EMAIL_JA_CADASTRADO", 422: "VALIDACAO_INVALIDA"})
def criar_usuario():
    return jsonify(s.usuario(g.servicos.criar_usuario_equipe(g.ctx, _body()))), 201


@endpoint("GET", "/usuarios/<int:id_>", tag="Usuários", resumo="Consulta um usuário (gera registro de auditoria de acesso).", roles=ADMIN,
          response_ex=USUARIO_EX, erros={**E401, **E403, 404: "USUARIO_NAO_ENCONTRADO"})
def obter_usuario(id_):
    return jsonify(s.usuario(g.servicos.obter_usuario(g.ctx, id_)))


# ------------------------------------------------------------------ unidades / cardápio
@endpoint("GET", "/unidades", tag="Unidades", resumo="Lista unidades ativas da rede.", publico=True, query=PAGINACAO,
          response_ex={"items": [{"id": 1, "nome": "Raízes Boa Viagem", "cidade": "Recife", "uf": "PE", "ativa": True}],
                       "page": 1, "limit": 10, "total": 1})
def listar_unidades():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.unidades.listar(limit, offset, somente_ativas=True)
    return _lista(itens, total, page, limit, s.unidade)


@endpoint("POST", "/unidades", tag="Unidades", resumo="Cadastra uma unidade.", roles=ADMIN, status=201,
          request_ex={"nome": "Raízes Pelourinho", "cidade": "Salvador", "uf": "BA"},
          response_ex={"id": 2, "nome": "Raízes Pelourinho", "cidade": "Salvador", "uf": "BA", "ativa": True},
          erros={**E401, **E403, 409: "UNIDADE_DUPLICADA", 422: "VALIDACAO_INVALIDA"})
def criar_unidade():
    return jsonify(s.unidade(g.servicos.criar_unidade(g.ctx, _body()))), 201


@endpoint("GET", "/unidades/<int:id_>", tag="Unidades", resumo="Consulta uma unidade (informa se está ativa).", publico=True,
          response_ex={"id": 1, "nome": "Raízes Boa Viagem", "cidade": "Recife", "uf": "PE", "ativa": True},
          erros={404: "UNIDADE_NAO_ENCONTRADA"})
def obter_unidade(id_):
    return jsonify(s.unidade(g.servicos.obter_unidade(id_)))


@endpoint("PATCH", "/unidades/<int:id_>", tag="Unidades", resumo="Atualiza nome ou situação (ativa) da unidade.", roles=ADMIN,
          request_ex={"ativa": False}, response_ex={"id": 1, "nome": "Raízes Boa Viagem", "cidade": "Recife", "uf": "PE", "ativa": False},
          erros={**E401, **E403, 404: "UNIDADE_NAO_ENCONTRADA", 422: "VALIDACAO_INVALIDA"})
def atualizar_unidade(id_):
    return jsonify(s.unidade(g.servicos.atualizar_unidade(g.ctx, id_, _body())))


@endpoint("GET", "/unidades/<int:id_>/cardapio", tag="Cardápio", resumo="Consulta o cardápio da unidade (preço local e disponibilidade).",
          publico=True, query=PAGINACAO,
          response_ex={"items": [{"produtoId": 1, "nome": "Tapioca de carne de sol", "descricao": "Com queijo coalho", "preco": 18.5,
                                  "disponivel": True, "saldoEstoque": 40}], "page": 1, "limit": 10, "total": 1},
          erros={404: "UNIDADE_NAO_ENCONTRADA"})
def cardapio(id_):
    page, limit, offset = paginacao(request.args)
    g.servicos.obter_unidade(id_)
    itens, total = g.servicos.produtos.cardapio(id_, limit, offset)
    return _lista(itens, total, page, limit, lambda i: {
        "produtoId": i["produto_id"], "nome": i["nome"], "descricao": i["descricao"], "preco": s.reais(i["preco_centavos"]),
        "disponivel": bool(i["disponivel"]) and i["saldo"] > 0, "saldoEstoque": i["saldo"]})


@endpoint("PUT", "/unidades/<int:unidade_id>/cardapio/<int:produto_id>", tag="Cardápio",
          resumo="Define preço e disponibilidade de um produto na unidade.", roles=GESTAO,
          request_ex={"preco": 19.9, "disponivel": True}, response_ex={"unidadeId": 1, "produtoId": 1, "preco": 19.9, "disponivel": True},
          erros={**E401, **E403, 404: "UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO", 422: "VALIDACAO_INVALIDA"})
def definir_cardapio(unidade_id, produto_id):
    item = g.servicos.definir_item_cardapio(g.ctx, unidade_id, produto_id, _body())
    return jsonify({"unidadeId": item.unidade_id, "produtoId": item.produto_id, "preco": s.reais(item.preco_centavos), "disponivel": item.disponivel})


# ------------------------------------------------------------------ produtos
@endpoint("GET", "/produtos", tag="Produtos", resumo="Lista o catálogo de produtos da rede.", publico=True, query=PAGINACAO,
          response_ex={"items": [{"id": 1, "nome": "Tapioca de carne de sol", "descricao": "Com queijo coalho", "precoBase": 18.5}],
                       "page": 1, "limit": 10, "total": 1})
def listar_produtos():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.produtos.listar(limit, offset)
    return _lista(itens, total, page, limit, s.produto)


@endpoint("POST", "/produtos", tag="Produtos", resumo="Cadastra um produto no catálogo.", roles=GESTAO, status=201,
          request_ex={"nome": "Bolo de rolo", "descricao": "Fatia individual", "precoBase": 12.0},
          response_ex={"id": 5, "nome": "Bolo de rolo", "descricao": "Fatia individual", "precoBase": 12.0},
          erros={**E401, **E403, 409: "PRODUTO_DUPLICADO", 422: "VALIDACAO_INVALIDA"})
def criar_produto():
    return jsonify(s.produto(g.servicos.criar_produto(g.ctx, _body()))), 201


@endpoint("GET", "/produtos/<int:id_>", tag="Produtos", resumo="Consulta um produto.", publico=True,
          response_ex={"id": 1, "nome": "Tapioca de carne de sol", "descricao": "Com queijo coalho", "precoBase": 18.5},
          erros={404: "PRODUTO_NAO_ENCONTRADO"})
def obter_produto(id_):
    return jsonify(s.produto(g.servicos.obter_produto(id_)))


# ------------------------------------------------------------------ estoque
@endpoint("GET", "/estoque", tag="Estoque", resumo="Consulta saldos de estoque de uma unidade.", roles=EQUIPE,
          query=[("unidadeId", "integer", "Obrigatório. Unidade consultada")] + PAGINACAO,
          response_ex={"items": [{"unidadeId": 1, "produtoId": 1, "produto": "Tapioca de carne de sol", "saldo": 40}], "page": 1, "limit": 10, "total": 1},
          erros={**E401, **E403, 422: "VALIDACAO_INVALIDA"})
def saldos():
    from ..application.services import exigir_escopo_unidade
    from ..application.validation import Validador
    v = Validador({"unidadeId": request.args.get("unidadeId")})
    unidade_id = v.inteiro_texto("unidadeId", minimo=1) if request.args.get("unidadeId") else v._falha("unidadeId", "campo obrigatório")
    v.concluir()
    exigir_escopo_unidade(g.ctx.usuario, unidade_id)
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.estoque.listar_saldos(unidade_id, limit, offset)
    return _lista(itens, total, page, limit, lambda i: {"unidadeId": i["unidade_id"], "produtoId": i["produto_id"],
                                                         "produto": i["produto"], "saldo": i["quantidade"]})


@endpoint("POST", "/estoque/movimentacoes", tag="Estoque", resumo="Registra entrada ou saída manual de estoque.", roles=GESTAO, status=201,
          request_ex={"unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 20, "motivo": "Reposição semanal"},
          response_ex={"unidadeId": 1, "produtoId": 1, "saldo": 60},
          erros={**E401, **E403, 404: "UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO", 409: "ESTOQUE_INSUFICIENTE", 422: "VALIDACAO_INVALIDA"})
def movimentar_estoque():
    return jsonify(g.servicos.movimentar_estoque(g.ctx, _body())), 201


@endpoint("GET", "/estoque/movimentacoes", tag="Estoque", resumo="Lista movimentações rastreáveis de estoque.", roles=GESTAO,
          query=[("unidadeId", "integer", "Obrigatório"), ("produtoId", "integer", "Opcional")] + PAGINACAO,
          response_ex={"items": [{"id": 1, "unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 20, "motivo": "Reposição semanal",
                                  "pedidoId": None, "usuarioId": 2, "createdAt": "2026-11-04T12:00:00.000000Z"}], "page": 1, "limit": 10, "total": 1},
          erros={**E401, **E403, 422: "VALIDACAO_INVALIDA"})
def listar_movimentacoes():
    from ..application.services import exigir_escopo_unidade
    from ..application.validation import Validador
    v = Validador({"unidadeId": request.args.get("unidadeId"), "produtoId": request.args.get("produtoId")})
    unidade_id = v.inteiro_texto("unidadeId", minimo=1) if request.args.get("unidadeId") else v._falha("unidadeId", "campo obrigatório")
    produto_id = v.inteiro_texto("produtoId", minimo=1) if request.args.get("produtoId") else None
    v.concluir()
    exigir_escopo_unidade(g.ctx.usuario, unidade_id)
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.estoque.listar_movimentos(unidade_id, produto_id, limit, offset)
    return _lista(itens, total, page, limit, s.movimento_estoque)


# ------------------------------------------------------------------ pedidos
@endpoint("POST", "/pedidos", tag="Pedidos", resumo="Cria pedido: valida cardápio e estoque, calcula valores no servidor e baixa o estoque.",
          roles=PEDIDOR, status=201,
          request_ex={"canalPedido": "TOTEM", "unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 2}, {"produtoId": 3, "quantidade": 1}],
                      "formaPagamento": "MOCK", "codigoPromocao": "RAIZES10"},
          response_ex=PEDIDO_EX,
          erros={**E401, **E403, 404: "UNIDADE_NAO_ENCONTRADA | PRODUTO_NAO_ENCONTRADO | PRODUTO_FORA_DO_CARDAPIO | PROMOCAO_NAO_ENCONTRADA",
                 409: "ESTOQUE_INSUFICIENTE | PRODUTO_INDISPONIVEL | UNIDADE_INATIVA | PROMOCAO_*", 422: "VALIDACAO_INVALIDA"})
def criar_pedido():
    return jsonify(s.pedido(g.servicos.criar_pedido(g.ctx, _body()))), 201


@endpoint("GET", "/pedidos", tag="Pedidos", resumo="Lista pedidos com filtros por canal, status e unidade (cliente vê apenas os próprios).",
          query=[("canalPedido", "string", "APP | TOTEM | BALCAO | PICKUP | WEB"), ("status", "string", "Status do pedido"),
                 ("unidadeId", "integer", "Filtra por unidade")] + PAGINACAO,
          response_ex={"items": [PEDIDO_EX], "page": 1, "limit": 10, "total": 1}, erros={**E401, 422: "VALIDACAO_INVALIDA"})
def listar_pedidos():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.listar_pedidos(g.ctx, request.args, limit, offset)
    return _lista(itens, total, page, limit, s.pedido)


@endpoint("GET", "/pedidos/<int:id_>", tag="Pedidos", resumo="Consulta um pedido e seus pagamentos.",
          response_ex={**PEDIDO_EX, "pagamentos": []}, erros={**E401, 403: "UNIDADE_FORA_DO_ESCOPO", 404: "PEDIDO_NAO_ENCONTRADO"})
def obter_pedido(id_):
    pedido, pagamentos = g.servicos.obter_pedido(g.ctx, id_)
    return jsonify({**s.pedido(pedido), "pagamentos": [s.pagamento(p) for p in pagamentos]})


@endpoint("PATCH", "/pedidos/<int:id_>/status", tag="Pedidos",
          resumo="Atualiza o status (cozinha → pronto → entregue) ou cancela, conforme perfil e máquina de estados.",
          request_ex={"status": "EM_PREPARO", "motivo": "Pedido iniciado na chapa"}, response_ex={**PEDIDO_EX, "status": "EM_PREPARO"},
          erros={**E401, 403: "PERFIL_SEM_PERMISSAO_PARA_STATUS | CANCELAMENTO_NAO_PERMITIDO", 404: "PEDIDO_NAO_ENCONTRADO",
                 409: "TRANSICAO_DE_STATUS_INVALIDA | STATUS_RESERVADO_AO_PAGAMENTO", 422: "VALIDACAO_INVALIDA"})
def atualizar_status(id_):
    return jsonify(s.pedido(g.servicos.atualizar_status(g.ctx, id_, _body())))


# ------------------------------------------------------------------ pagamentos (mock)
PAG_EX = {"pagamentoId": 1, "pedidoId": 9001, "metodo": "MOCK", "status": "APROVADO", "valor": 62.5,
          "mensagem": "Pagamento aprovado (simulação).", "payloadEnviado": {"pedidoId": 9001, "valor": 62.5, "moeda": "BRL", "metodo": "MOCK"},
          "payloadRecebido": {"transactionId": "7d1c...", "status": "APROVADO", "motivo": None, "mensagem": "Pagamento aprovado (simulação)."},
          "createdAt": "2026-11-04T12:01:00.000000Z", "pedidoStatus": "PAGO", "reaproveitado": False}


@endpoint("POST", "/pagamentos", tag="Pagamentos",
          resumo="Solicita pagamento ao gateway SIMULADO (campo simulacao: APROVADO, RECUSADO ou FALHA). Exige cabeçalho Idempotency-Key.",
          roles=PEDIDOR, status=201, headers=[("Idempotency-Key", "Obrigatório. 8 a 100 caracteres. Repetir a chave devolve o mesmo resultado (200).")],
          request_ex={"pedidoId": 9001, "metodo": "MOCK", "simulacao": "APROVADO"}, response_ex=PAG_EX,
          erros={**E401, 404: "PEDIDO_NAO_ENCONTRADO", 409: "PEDIDO_NAO_AGUARDA_PAGAMENTO | IDEMPOTENCY_KEY_REUTILIZADA",
                 422: "VALIDACAO_INVALIDA", 502: "GATEWAY_PAGAMENTO_INDISPONIVEL"})
def solicitar_pagamento():
    pagamento, pedido, reaproveitado = g.servicos.solicitar_pagamento(g.ctx, request.headers.get("Idempotency-Key"), _body())
    corpo = {**s.pagamento(pagamento), "pedidoStatus": pedido.status, "reaproveitado": reaproveitado}
    resposta = jsonify(corpo)
    return resposta, (200 if reaproveitado else 201)


@endpoint("GET", "/pagamentos/<int:id_>", tag="Pagamentos", resumo="Consulta um pagamento registrado.", response_ex=PAG_EX,
          erros={**E401, 404: "PAGAMENTO_NAO_ENCONTRADO"})
def obter_pagamento(id_):
    return jsonify(s.pagamento(g.servicos.obter_pagamento(g.ctx, id_)))


# ------------------------------------------------------------------ fidelidade
@endpoint("POST", "/fidelidade/consentimento", tag="Fidelidade", resumo="Concede ou revoga o consentimento para o programa de fidelidade.",
          roles=[Perfil.CLIENTE.value], request_ex={"aceito": True}, response_ex={"consentimentoFidelidade": True},
          erros={**E401, **E403, 422: "VALIDACAO_INVALIDA"})
def consentimento():
    return jsonify(g.servicos.definir_consentimento(g.ctx, _body()))


@endpoint("GET", "/fidelidade/saldo", tag="Fidelidade", resumo="Consulta o saldo de pontos.", roles=[Perfil.CLIENTE.value],
          response_ex={"consentimentoFidelidade": True, "saldoPontos": 62}, erros={**E401, **E403})
def saldo_fidelidade():
    return jsonify(g.servicos.saldo_fidelidade(g.ctx))


@endpoint("GET", "/fidelidade/historico", tag="Fidelidade", resumo="Histórico de acúmulos e resgates.", roles=[Perfil.CLIENTE.value],
          query=PAGINACAO, response_ex={"items": [{"id": 1, "tipo": "ACUMULO", "pontos": 62, "pedidoId": 9001, "descricao": "Pontos por pedido pago",
                                                    "createdAt": "2026-11-04T12:01:00.000000Z"}], "page": 1, "limit": 10, "total": 1},
          erros={**E401, **E403})
def historico_fidelidade():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.historico_fidelidade(g.ctx, limit, offset)
    return _lista(itens, total, page, limit, lambda m: {"id": m["id"], "tipo": m["tipo"], "pontos": m["pontos"], "pedidoId": m["pedido_id"],
                                                         "descricao": m["descricao"], "createdAt": m["criado_em"]})


@endpoint("POST", "/fidelidade/resgates", tag="Fidelidade", resumo="Resgata pontos (mínimo 10) com consentimento vigente.", roles=[Perfil.CLIENTE.value],
          status=201, request_ex={"pontos": 20}, response_ex={"pontosResgatados": 20, "saldoPontos": 42},
          erros={**E401, **E403, 409: "SALDO_PONTOS_INSUFICIENTE | CONSENTIMENTO_AUSENTE", 422: "VALIDACAO_INVALIDA"})
def resgatar():
    return jsonify(g.servicos.resgatar_pontos(g.ctx, _body())), 201


# ------------------------------------------------------------------ promoções
@endpoint("GET", "/promocoes", tag="Promoções", resumo="Lista promoções ativas.", publico=True, query=PAGINACAO,
          response_ex={"items": [{"id": 1, "codigo": "RAIZES10", "descricao": "10% em pedidos acima de R$ 30", "percentual": 10, "valorMinimo": 30.0,
                                  "ativa": True, "validoAte": None}], "page": 1, "limit": 10, "total": 1})
def listar_promocoes():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.promocoes.listar(limit, offset, somente_ativas=True)
    return _lista(itens, total, page, limit, s.promocao)


@endpoint("POST", "/promocoes", tag="Promoções", resumo="Cria regra promocional (desconto percentual com valor mínimo e validade).", roles=GESTAO, status=201,
          request_ex={"codigo": "JUNINA15", "descricao": "15% no período junino", "percentual": 15, "valorMinimo": 25.0, "validoAte": "2027-06-30T23:59:59Z"},
          response_ex={"id": 2, "codigo": "JUNINA15", "descricao": "15% no período junino", "percentual": 15, "valorMinimo": 25.0, "ativa": True,
                       "validoAte": "2027-06-30T23:59:59Z"},
          erros={**E401, **E403, 409: "PROMOCAO_DUPLICADA", 422: "VALIDACAO_INVALIDA"})
def criar_promocao():
    return jsonify(s.promocao(g.servicos.criar_promocao(g.ctx, _body()))), 201


@endpoint("PATCH", "/promocoes/<int:id_>", tag="Promoções", resumo="Ativa ou desativa uma promoção.", roles=GESTAO, request_ex={"ativa": False},
          response_ex={"id": 1, "codigo": "RAIZES10", "descricao": "10% em pedidos acima de R$ 30", "percentual": 10, "valorMinimo": 30.0, "ativa": False, "validoAte": None},
          erros={**E401, **E403, 404: "PROMOCAO_NAO_ENCONTRADA", 422: "VALIDACAO_INVALIDA"})
def atualizar_promocao(id_):
    return jsonify(s.promocao(g.servicos.atualizar_promocao(g.ctx, id_, _body())))


# ------------------------------------------------------------------ auditoria
@endpoint("GET", "/auditoria", tag="Auditoria", resumo="Consulta trilha de auditoria de ações sensíveis.", roles=GESTAO,
          query=[("acao", "string", "Ex.: PEDIDO_CRIADO"), ("entidade", "string", "Ex.: pedido"), ("entidadeId", "string", "Id da entidade")] + PAGINACAO,
          response_ex={"items": [{"id": 7, "usuarioId": 4, "perfil": "CLIENTE", "acao": "PEDIDO_CRIADO", "entidade": "pedido", "entidadeId": "9001",
                                  "detalhes": {"canalPedido": "TOTEM", "unidadeId": 1, "totalCentavos": 6250},
                                  "requestId": "2f0c1a4e-...", "createdAt": "2026-11-04T12:00:00.000000Z"}], "page": 1, "limit": 10, "total": 1},
          erros={**E401, **E403})
def listar_auditoria():
    page, limit, offset = paginacao(request.args)
    itens, total = g.servicos.listar_auditoria(g.ctx, request.args, page, limit, offset)
    return _lista(itens, total, page, limit, s.auditoria)

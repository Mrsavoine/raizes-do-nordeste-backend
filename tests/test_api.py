"""Cenários T01–T25. Os IDs T01–T14 coincidem com a coleção Postman e com o plano de testes do PDF."""
import threading

from app.api.openapi import gerar
from app.api.registry import REGISTRY

from .base import ApiTestCase


class TestAutenticacaoEAutorizacao(ApiTestCase):
    def test_T01_login_valido_retorna_token(self):
        r = self.client.post("/auth/login", json={"email": "cliente@raizes.example", "senha": "Cliente@123"})
        self.assertEqual(r.status_code, 200)
        corpo = r.get_json()
        self.assertEqual(corpo["tokenType"], "Bearer")
        self.assertEqual(corpo["user"]["perfil"], "CLIENTE")
        self.assertTrue(corpo["accessToken"])
        self.assertNotIn("senha", str(corpo).lower().replace("senha_", ""))

    def test_T01b_login_com_senha_errada_retorna_401(self):
        self.assertErro(self.client.post("/auth/login", json={"email": "cliente@raizes.example", "senha": "errada123"}), 401, "CREDENCIAIS_INVALIDAS")

    def test_T02_acesso_sem_token_retorna_401(self):
        self.assertErro(self.client.get("/pedidos"), 401, "TOKEN_AUSENTE")

    def test_T02b_token_adulterado_retorna_401(self):
        h = self.token("cliente")
        h["Authorization"] = h["Authorization"][:-3] + "abc"
        self.assertErro(self.client.get("/pedidos", headers=h), 401, "TOKEN_INVALIDO")

    def test_T03_cliente_sem_permissao_para_estoque_retorna_403(self):
        r = self.client.post("/estoque/movimentacoes", headers=self.token("cliente"),
                             json={"unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 5, "motivo": "Teste"})
        self.assertErro(r, 403, "PERFIL_SEM_PERMISSAO")

    def test_T14_senha_armazenada_com_hash_e_nunca_exposta(self):
        r = self.client.post("/auth/register", json={"nome": "Joana Lima", "email": "joana@exemplo.com", "senha": "Senha@123", "aceitePoliticaPrivacidade": True})
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("senha", " ".join(r.get_json().keys()))
        c = self.db()
        armazenado = c.execute("SELECT senha_hash FROM usuarios WHERE email='joana@exemplo.com'").fetchone()[0]
        c.close()
        self.assertTrue(armazenado.startswith("scrypt:"))
        self.assertNotIn("Senha@123", armazenado)
        me = self.client.get("/usuarios/me", headers=self.token_de("joana@exemplo.com", "Senha@123"))
        self.assertNotIn("senha_hash", me.get_json())

    def token_de(self, email, senha):
        r = self.client.post("/auth/login", json={"email": email, "senha": senha})
        return {"Authorization": f"Bearer {r.get_json()['accessToken']}"}

    def test_T05_cadastro_com_email_invalido_retorna_422(self):
        r = self.client.post("/auth/register", json={"nome": "X Y", "email": "invalido", "senha": "Senha@123", "aceitePoliticaPrivacidade": True})
        self.assertErro(r, 422, "VALIDACAO_INVALIDA")
        self.assertEqual(r.get_json()["details"][0]["field"], "email")

    def test_cadastro_exige_aceite_da_politica(self):
        r = self.client.post("/auth/register", json={"nome": "Sem Aceite", "email": "sa@exemplo.com", "senha": "Senha@123", "aceitePoliticaPrivacidade": False})
        self.assertErro(r, 422, "VALIDACAO_INVALIDA")

    def test_cadastro_com_email_duplicado_retorna_409(self):
        r = self.client.post("/auth/register", json={"nome": "Dup Licado", "email": "cliente@raizes.example", "senha": "Senha@123", "aceitePoliticaPrivacidade": True})
        self.assertErro(r, 409, "EMAIL_JA_CADASTRADO")

    def test_json_malformado_retorna_400(self):
        r = self.client.post("/auth/login", data="{nao-e-json", content_type="application/json")
        self.assertErro(r, 400, "JSON_INVALIDO")

    def test_rota_inexistente_retorna_erro_padronizado(self):
        self.assertErro(self.client.get("/nao-existe"), 404, "RECURSO_NAO_ENCONTRADO")


class TestPedidos(ApiTestCase):
    def test_T04_pedido_sem_canal_retorna_422(self):
        r = self.client.post("/pedidos", headers=self.token("cliente"), json={"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}], "formaPagamento": "MOCK"})
        self.assertErro(r, 422, "VALIDACAO_INVALIDA")
        self.assertIn("canalPedido", [d["field"] for d in r.get_json()["details"]])

    def test_T04b_canal_invalido_e_quantidade_negativa_retornam_422(self):
        r = self.pedido(canal="DRONE", itens=[{"produtoId": 1, "quantidade": -1}])
        self.assertErro(r, 422, "VALIDACAO_INVALIDA")
        campos = [d["field"] for d in r.get_json()["details"]]
        self.assertIn("canalPedido", campos)
        self.assertIn("itens[0].quantidade", campos)

    def test_T06_pedido_valido_calcula_total_no_servidor_e_baixa_estoque(self):
        antes = self.saldo()
        r = self.pedido(itens=[{"produtoId": 1, "quantidade": 2}, {"produtoId": 3, "quantidade": 1}], total=0.01)
        self.assertEqual(r.status_code, 201, r.get_json())
        corpo = r.get_json()
        self.assertEqual(corpo["status"], "AGUARDANDO_PAGAMENTO")
        self.assertEqual(corpo["canalPedido"], "TOTEM")
        self.assertEqual(corpo["total"], 49.0)  # 2 x 18,50 + 1 x 12,00; "total" enviado pelo cliente é ignorado
        self.assertEqual(self.saldo(), antes - 2)

    def test_T07_produto_inexistente_retorna_404(self):
        self.assertErro(self.pedido(itens=[{"produtoId": 999, "quantidade": 1}]), 404, "PRODUTO_NAO_ENCONTRADO")

    def test_T07b_unidade_inexistente_retorna_404(self):
        r = self.client.post("/pedidos", headers=self.token("cliente"), json={"canalPedido": "APP", "unidadeId": 99, "itens": [{"produtoId": 1, "quantidade": 1}], "formaPagamento": "MOCK"})
        self.assertErro(r, 404, "UNIDADE_NAO_ENCONTRADA")

    def test_T07c_produto_fora_do_cardapio_da_unidade_retorna_404(self):
        r = self.client.post("/pedidos", headers=self.token("cliente"), json={"canalPedido": "APP", "unidadeId": 2, "itens": [{"produtoId": 2, "quantidade": 1}], "formaPagamento": "MOCK"})
        self.assertErro(r, 404, "PRODUTO_FORA_DO_CARDAPIO")

    def test_T08_estoque_insuficiente_retorna_409_sem_efeitos_colaterais(self):
        antes = self.saldo()
        r = self.client.post("/pedidos", headers=self.token("cliente"),
                             json={"canalPedido": "WEB", "unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 50}], "formaPagamento": "PIX"})
        self.assertErro(r, 409, "ESTOQUE_INSUFICIENTE")
        self.assertIn("Disponível: 40", r.get_json()["details"][0]["issue"])
        self.assertEqual(self.saldo(), antes)
        c = self.db()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0], 0)
        c.close()

    def test_T13_filtro_por_canal_e_paginacao(self):
        self.pedido(canal="APP")
        self.pedido(canal="TOTEM")
        self.pedido(canal="TOTEM")
        r = self.client.get("/pedidos?canalPedido=TOTEM&page=1&limit=1", headers=self.token("cliente")).get_json()
        self.assertEqual((r["total"], len(r["items"]), r["limit"]), (2, 1, 1))
        self.assertTrue(all(i["canalPedido"] == "TOTEM" for i in r["items"]))
        self.assertErro(self.client.get("/pedidos?canalPedido=XYZ", headers=self.token("cliente")), 422, "VALIDACAO_INVALIDA")
        self.assertErro(self.client.get("/pedidos?limit=1000", headers=self.token("cliente")), 422, "VALIDACAO_INVALIDA")

    def test_T20_cliente_nao_acessa_pedido_de_outro_cliente(self):
        pid = self.pedido().get_json()["pedidoId"]
        self.assertErro(self.client.get(f"/pedidos/{pid}", headers=self.token("cliente2")), 404, "PEDIDO_NAO_ENCONTRADO")
        self.assertEqual(self.client.get("/pedidos", headers=self.token("cliente2")).get_json()["total"], 0)

    def test_T18_promocao_aplica_desconto_e_valida_elegibilidade(self):
        r = self.pedido(itens=[{"produtoId": 2, "quantidade": 2}], codigoPromocao="raizes10")
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual((r.get_json()["subtotal"], r.get_json()["desconto"], r.get_json()["total"]), (44.0, 4.4, 39.6))
        self.assertErro(self.pedido(itens=[{"produtoId": 4, "quantidade": 1}], codigoPromocao="RAIZES10"), 409, "PROMOCAO_NAO_ELEGIVEL")
        self.assertErro(self.pedido(codigoPromocao="NAOEXISTE"), 404, "PROMOCAO_NAO_ENCONTRADA")

    def test_T23_concorrencia_nao_vende_acima_do_estoque(self):
        resultados = []

        def comprar():
            r = self.client.post("/pedidos", headers=self.token("cliente"), json={"canalPedido": "APP", "unidadeId": 2, "itens": [{"produtoId": 1, "quantidade": 1}], "formaPagamento": "MOCK"})
            resultados.append(r.status_code)
        self.token("cliente")
        threads = [threading.Thread(target=comprar) for _ in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(resultados), [201] * 5 + [409] * 5)
        self.assertEqual(self.saldo(unidade=2), 0)


class TestPagamentoEStatus(ApiTestCase):
    def test_T09_pagamento_aprovado_atualiza_status_para_pago(self):
        pid = self.pedido().get_json()["pedidoId"]
        r = self.pagar(pid, simulacao="APROVADO")
        self.assertEqual(r.status_code, 201, r.get_json())
        corpo = r.get_json()
        self.assertEqual((corpo["status"], corpo["pedidoStatus"]), ("APROVADO", "PAGO"))
        self.assertEqual(corpo["payloadEnviado"]["valor"], 37.0)
        self.assertEqual(corpo["payloadRecebido"]["status"], "APROVADO")

    def test_T10_pagamento_recusado_marca_pedido_e_devolve_estoque(self):
        antes = self.saldo()
        pid = self.pedido().get_json()["pedidoId"]
        self.assertEqual(self.saldo(), antes - 2)
        r = self.pagar(pid, simulacao="RECUSADO")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.get_json()["status"], r.get_json()["pedidoStatus"]), ("RECUSADO", "PAGAMENTO_RECUSADO"))
        self.assertIn("recusado", r.get_json()["mensagem"].lower())
        self.assertEqual(self.saldo(), antes)

    def test_T15_idempotencia_repete_a_mesma_resposta_sem_duplicar(self):
        pid = self.pedido().get_json()["pedidoId"]
        a, b = self.pagar(pid, "chave-igual-123"), self.pagar(pid, "chave-igual-123")
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.get_json()["pagamentoId"], b.get_json()["pagamentoId"])
        self.assertTrue(b.get_json()["reaproveitado"])
        c = self.db()
        self.assertEqual(c.execute("SELECT COUNT(*) FROM pagamentos").fetchone()[0], 1)
        c.close()

    def test_idempotency_key_de_outro_pedido_retorna_409(self):
        p1, p2 = (self.pedido().get_json()["pedidoId"] for _ in range(2))
        self.pagar(p1, "chave-compartilhada")
        self.assertErro(self.pagar(p2, "chave-compartilhada"), 409, "IDEMPOTENCY_KEY_REUTILIZADA")

    def test_pagamento_sem_idempotency_key_retorna_422(self):
        pid = self.pedido().get_json()["pedidoId"]
        r = self.client.post("/pagamentos", json={"pedidoId": pid}, headers=self.token("cliente"))
        self.assertErro(r, 422, "VALIDACAO_INVALIDA")

    def test_T16_falha_do_gateway_retorna_502_mantem_pedido_e_permite_nova_tentativa(self):
        pid = self.pedido().get_json()["pedidoId"]
        r = self.pagar(pid, "chave-falha-001", simulacao="FALHA")
        self.assertErro(r, 502, "GATEWAY_PAGAMENTO_INDISPONIVEL")
        self.assertEqual(self.client.get(f"/pedidos/{pid}", headers=self.token("cliente")).get_json()["status"], "AGUARDANDO_PAGAMENTO")
        self.assertEqual(self.client.get(f"/pedidos/{pid}", headers=self.token("cliente")).get_json()["pagamentos"][0]["status"], "FALHA")
        retry = self.pagar(pid, "chave-falha-001", simulacao="APROVADO")
        self.assertEqual((retry.status_code, retry.get_json()["pedidoStatus"]), (201, "PAGO"))

    def test_pagar_pedido_ja_pago_retorna_409(self):
        pid = self.pedido().get_json()["pedidoId"]
        self.pagar(pid, "chave-primeira-1")
        self.assertErro(self.pagar(pid, "chave-segunda-22"), 409, "PEDIDO_NAO_AGUARDA_PAGAMENTO")

    def test_T11_fluxo_de_status_por_perfil_e_transicao_invalida(self):
        pid = self.pedido().get_json()["pedidoId"]
        self.assertErro(self.client.patch(f"/pedidos/{pid}/status", json={"status": "EM_PREPARO"}, headers=self.token("cozinha")), 409, "TRANSICAO_DE_STATUS_INVALIDA")
        self.assertErro(self.client.patch(f"/pedidos/{pid}/status", json={"status": "PAGO"}, headers=self.token("gerente")), 409, "STATUS_RESERVADO_AO_PAGAMENTO")
        self.pagar(pid)
        r = self.client.patch(f"/pedidos/{pid}/status", json={"status": "EM_PREPARO"}, headers=self.token("cozinha"))
        self.assertEqual((r.status_code, r.get_json()["status"]), (200, "EM_PREPARO"))
        self.assertEqual(self.client.patch(f"/pedidos/{pid}/status", json={"status": "PRONTO"}, headers=self.token("cozinha")).status_code, 200)
        self.assertErro(self.client.patch(f"/pedidos/{pid}/status", json={"status": "ENTREGUE"}, headers=self.token("cozinha")), 403, "PERFIL_SEM_PERMISSAO_PARA_STATUS")
        self.assertEqual(self.client.patch(f"/pedidos/{pid}/status", json={"status": "ENTREGUE"}, headers=self.token("atendente")).get_json()["status"], "ENTREGUE")
        self.assertErro(self.client.patch(f"/pedidos/{pid}/status", json={"status": "CANCELADO"}, headers=self.token("gerente")), 409, "TRANSICAO_DE_STATUS_INVALIDA")

    def test_T19_cancelamento_devolve_estoque_e_respeita_regras_do_cliente(self):
        antes = self.saldo()
        pid = self.pedido().get_json()["pedidoId"]
        r = self.client.patch(f"/pedidos/{pid}/status", json={"status": "CANCELADO", "motivo": "Desisti do pedido"}, headers=self.token("cliente"))
        self.assertEqual((r.status_code, r.get_json()["status"]), (200, "CANCELADO"))
        self.assertEqual(self.saldo(), antes)
        pid2 = self.pedido().get_json()["pedidoId"]
        self.pagar(pid2, "chave-pagto-cancel")
        self.assertErro(self.client.patch(f"/pedidos/{pid2}/status", json={"status": "CANCELADO"}, headers=self.token("cliente")), 403, "CANCELAMENTO_NAO_PERMITIDO")
        self.assertErro(self.client.patch(f"/pedidos/{pid2}/status", json={"status": "CANCELADO"}, headers=self.token("atendente")), 403, "CANCELAMENTO_NAO_PERMITIDO")
        self.assertEqual(self.client.patch(f"/pedidos/{pid2}/status", json={"status": "CANCELADO"}, headers=self.token("gerente")).status_code, 200)

    def test_T12_acoes_sensiveis_geram_registro_de_auditoria(self):
        pid = self.pedido().get_json()["pedidoId"]
        self.pagar(pid)
        self.client.patch(f"/pedidos/{pid}/status", json={"status": "EM_PREPARO"}, headers=self.token("cozinha"))
        r = self.client.get(f"/auditoria?entidade=pedido&entidadeId={pid}", headers=self.token("gerente")).get_json()
        acoes = {i["acao"] for i in r["items"]}
        self.assertTrue({"PEDIDO_CRIADO", "PEDIDO_STATUS_ALTERADO"} <= acoes, acoes)
        criado = next(i for i in r["items"] if i["acao"] == "PEDIDO_CRIADO")
        self.assertEqual(criado["perfil"], "CLIENTE")
        self.assertTrue(criado["usuarioId"] and criado["requestId"] and criado["createdAt"])
        self.assertErro(self.client.get("/auditoria", headers=self.token("cliente")), 403, "PERFIL_SEM_PERMISSAO")


class TestEstoqueFidelidadeLgpd(ApiTestCase):
    def test_movimentacao_de_estoque_entrada_saida_e_rastreabilidade(self):
        h = self.token("gerente")
        base = {"unidadeId": 1, "produtoId": 1, "motivo": "Ajuste de inventário"}
        self.assertEqual(self.client.post("/estoque/movimentacoes", headers=h, json={**base, "tipo": "ENTRADA", "quantidade": 10}).get_json()["saldo"], 50)
        self.assertEqual(self.client.post("/estoque/movimentacoes", headers=h, json={**base, "tipo": "SAIDA", "quantidade": 5}).get_json()["saldo"], 45)
        self.assertErro(self.client.post("/estoque/movimentacoes", headers=h, json={**base, "tipo": "SAIDA", "quantidade": 500}), 409, "ESTOQUE_INSUFICIENTE")
        movs = self.client.get("/estoque/movimentacoes?unidadeId=1&produtoId=1", headers=h).get_json()
        self.assertGreaterEqual(movs["total"], 3)
        self.assertEqual(self.client.get("/estoque?unidadeId=1", headers=h).get_json()["items"][0]["saldo"], 45)

    def test_gerente_nao_opera_estoque_de_outra_unidade(self):
        r = self.client.post("/estoque/movimentacoes", headers=self.token("gerente"), json={"unidadeId": 2, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 1, "motivo": "Teste escopo"})
        self.assertErro(r, 403, "UNIDADE_FORA_DO_ESCOPO")

    def test_T17_fidelidade_exige_consentimento_acumula_e_resgata(self):
        h = self.token("cliente")
        p1 = self.pedido().get_json()["pedidoId"]
        self.pagar(p1, "chave-fid-sem-consent")
        self.assertEqual(self.client.get("/fidelidade/saldo", headers=h).get_json(), {"consentimentoFidelidade": False, "saldoPontos": 0})
        self.assertEqual(self.client.post("/fidelidade/consentimento", headers=h, json={"aceito": True}).status_code, 200)
        p2 = self.pedido().get_json()["pedidoId"]
        self.pagar(p2, "chave-fid-com-consent")
        self.assertEqual(self.client.get("/fidelidade/saldo", headers=h).get_json()["saldoPontos"], 37)
        self.assertErro(self.client.post("/fidelidade/resgates", headers=h, json={"pontos": 100}), 409, "SALDO_PONTOS_INSUFICIENTE")
        r = self.client.post("/fidelidade/resgates", headers=h, json={"pontos": 20})
        self.assertEqual((r.status_code, r.get_json()["saldoPontos"]), (201, 17))
        self.assertEqual(self.client.get("/fidelidade/historico", headers=h).get_json()["total"], 2)
        self.client.post("/fidelidade/consentimento", headers=h, json={"aceito": False})
        self.assertErro(self.client.post("/fidelidade/resgates", headers=h, json={"pontos": 10}), 409, "CONSENTIMENTO_AUSENTE")

    def test_T21_anonimizacao_remove_dados_pessoais_e_bloqueia_login(self):
        h = self.token("cliente2")
        self.assertEqual(self.client.delete("/usuarios/me", headers=h).status_code, 204)
        self.assertErro(self.client.post("/auth/login", json={"email": "cliente2@raizes.example", "senha": "Cliente@123"}), 401, "CREDENCIAIS_INVALIDAS")
        c = self.db()
        nome, email, ativo = c.execute("SELECT nome,email,ativo FROM usuarios WHERE id=6").fetchone()
        c.close()
        self.assertEqual((nome, ativo), ("Usuário anonimizado", 0))
        self.assertTrue(email.endswith("@anonimizado.invalid"))
        acoes = [i["acao"] for i in self.client.get("/auditoria?acao=USUARIO_ANONIMIZADO", headers=self.token("admin")).get_json()["items"]]
        self.assertEqual(acoes, ["USUARIO_ANONIMIZADO"])

    def test_consulta_de_dados_de_usuario_por_admin_e_auditada(self):
        self.assertEqual(self.client.get("/usuarios/5", headers=self.token("admin")).status_code, 200)
        itens = self.client.get("/auditoria?acao=DADOS_USUARIO_CONSULTADOS", headers=self.token("admin")).get_json()["items"]
        self.assertEqual((len(itens), itens[0]["entidadeId"]), (1, "5"))
        self.assertErro(self.client.get("/usuarios/5", headers=self.token("cliente")), 403, "PERFIL_SEM_PERMISSAO")


class TestContratoOpenApi(ApiTestCase):
    def test_T22_todas_as_rotas_estao_documentadas_e_vice_versa(self):
        spec = self.client.get("/openapi.json").get_json()
        documentadas = {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops}
        reais = set()
        for regra in self.app.url_map.iter_rules():
            if regra.endpoint in ("static", "openapi", "docs"):
                continue
            import re
            caminho = re.sub(r"<(?:int:)?(\w+)>", lambda m: "{" + (m.group(1).split("_")[0] + "".join(x.capitalize() for x in m.group(1).split("_")[1:])) + "}", regra.rule)
            for metodo in regra.methods - {"HEAD", "OPTIONS"}:
                reais.add((metodo, caminho))
        self.assertEqual(documentadas, reais)
        self.assertGreaterEqual(len(documentadas), 30)

    def test_exemplos_de_request_do_openapi_sao_aceitos_pela_api(self):
        ops = {(e["method"], e["path"]): e for e in REGISTRY}
        login = ops[("post", "/auth/login")]["request"]
        self.assertEqual(self.client.post("/auth/login", json=login).status_code, 200)
        pedido = dict(ops[("post", "/pedidos")]["request"])
        pedido["itens"] = [{"produtoId": 1, "quantidade": 2}, {"produtoId": 3, "quantidade": 1}]
        r = self.client.post("/pedidos", json=pedido, headers=self.token("cliente"))
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(set(ops[("post", "/pedidos")]["response"]) , set(r.get_json()))
        pag = self.client.post("/pagamentos", json=ops[("post", "/pagamentos")]["request"] | {"pedidoId": r.get_json()["pedidoId"]},
                               headers={**self.token("cliente"), "Idempotency-Key": "exemplo-openapi-1"})
        self.assertEqual(pag.status_code, 201)
        self.assertEqual(set(ops[("post", "/pagamentos")]["response"]), set(pag.get_json()))

    def test_health_e_swagger_ui(self):
        self.assertEqual(self.client.get("/health").get_json()["status"], "UP")
        self.assertIn("swagger-ui", self.client.get("/docs").get_data(as_text=True))

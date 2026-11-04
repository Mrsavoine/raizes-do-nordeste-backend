"""Gera a coleção Postman v2.1 a partir de uma única especificação. Uso: python -m scripts.build_collection"""
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PED = {"canalPedido": "TOTEM", "unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 2}], "formaPagamento": "MOCK"}
LOGIN = lambda quem, senha: {"email": f"{quem}@raizes.example", "senha": senha}

# (pasta, nome, método, caminho, token, corpo, status esperado, {variavel: jsonpath}, [(jsonpath, valor)], cabeçalhos extras)
PASSOS = [
    ("Auth", "T01 Login válido (cliente)", "POST", "/auth/login", None, LOGIN("cliente", "Cliente@123"), 200, {"tokenCliente": "accessToken"}, [("tokenType", "Bearer"), ("user.perfil", "CLIENTE")], {}),
    ("Auth", "Login gerente", "POST", "/auth/login", None, LOGIN("gerente", "Gerente@123"), 200, {"tokenGerente": "accessToken"}, [], {}),
    ("Auth", "Login cozinha", "POST", "/auth/login", None, LOGIN("cozinha", "Cozinha@123"), 200, {"tokenCozinha": "accessToken"}, [], {}),
    ("Auth", "Login atendente", "POST", "/auth/login", None, LOGIN("atendente", "Atendente@123"), 200, {"tokenAtendente": "accessToken"}, [], {}),
    ("Auth", "Login admin", "POST", "/auth/login", None, LOGIN("admin", "Admin@123"), 200, {"tokenAdmin": "accessToken"}, [], {}),
    ("Cardápio", "Consultar cardápio da unidade 1 (público)", "GET", "/unidades/1/cardapio?page=1&limit=10", None, None, 200, {}, [("total", 4)], {}),
    ("Pedidos", "T06 Criar pedido válido (canal TOTEM)", "POST", "/pedidos", "tokenCliente", PED, 201, {"pedidoId": "pedidoId"}, [("status", "AGUARDANDO_PAGAMENTO"), ("canalPedido", "TOTEM"), ("total", 37.0)], {}),
    ("Pedidos", "T13 Listar pedidos filtrando por canal", "GET", "/pedidos?canalPedido=TOTEM&page=1&limit=10", "tokenCliente", None, 200, {}, [("items[0].canalPedido", "TOTEM")], {}),
    ("Pagamento", "T09 Pagamento mock aprovado", "POST", "/pagamentos", "tokenCliente", {"pedidoId": "{{pedidoId}}", "metodo": "MOCK", "simulacao": "APROVADO"}, 201, {}, [("status", "APROVADO"), ("pedidoStatus", "PAGO")], {"Idempotency-Key": "{{$guid}}"}),
    ("Pedidos", "T11a Cozinha inicia preparo", "PATCH", "/pedidos/{{pedidoId}}/status", "tokenCozinha", {"status": "EM_PREPARO"}, 200, {}, [("status", "EM_PREPARO")], {}),
    ("Pedidos", "T11b Cozinha marca pronto", "PATCH", "/pedidos/{{pedidoId}}/status", "tokenCozinha", {"status": "PRONTO"}, 200, {}, [("status", "PRONTO")], {}),
    ("Pedidos", "T11c Atendente entrega", "PATCH", "/pedidos/{{pedidoId}}/status", "tokenAtendente", {"status": "ENTREGUE"}, 200, {}, [("status", "ENTREGUE")], {}),
    ("Pedidos", "Criar pedido para recusa", "POST", "/pedidos", "tokenCliente", {**PED, "canalPedido": "APP"}, 201, {"pedidoId2": "pedidoId"}, [("canalPedido", "APP")], {}),
    ("Pagamento", "T10 Pagamento mock recusado", "POST", "/pagamentos", "tokenCliente", {"pedidoId": "{{pedidoId2}}", "simulacao": "RECUSADO"}, 201, {}, [("status", "RECUSADO"), ("pedidoStatus", "PAGAMENTO_RECUSADO")], {"Idempotency-Key": "{{$guid}}"}),
    ("Pedidos", "Criar pedido para falha do gateway", "POST", "/pedidos", "tokenCliente", {**PED, "canalPedido": "WEB"}, 201, {"pedidoId3": "pedidoId"}, [], {}),
    ("Pagamento", "T16 Falha simulada do gateway (502)", "POST", "/pagamentos", "tokenCliente", {"pedidoId": "{{pedidoId3}}", "simulacao": "FALHA"}, 502, {}, [("error", "GATEWAY_PAGAMENTO_INDISPONIVEL")], {"Idempotency-Key": "{{$guid}}"}),
    ("Estoque", "Entrada de estoque (gerente)", "POST", "/estoque/movimentacoes", "tokenGerente", {"unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição semanal"}, 201, {}, [("produtoId", 1)], {}),
    ("Estoque", "Consultar saldo da unidade 1", "GET", "/estoque?unidadeId=1", "tokenGerente", None, 200, {}, [("total", 4)], {}),
    ("Fidelidade", "Conceder consentimento de fidelidade", "POST", "/fidelidade/consentimento", "tokenCliente", {"aceito": True}, 200, {}, [("consentimentoFidelidade", True)], {}),
    ("Fidelidade", "Consultar saldo de pontos", "GET", "/fidelidade/saldo", "tokenCliente", None, 200, {}, [("consentimentoFidelidade", True)], {}),
    ("Auditoria", "T12 Auditoria registra criação e mudanças de status do pedido", "GET", "/auditoria?entidade=pedido&entidadeId={{pedidoId}}", "tokenGerente", None, 200, {}, [("total", 4)], {}),
    ("Erros", "T02 Listar pedidos sem token (401)", "GET", "/pedidos", None, None, 401, {}, [("error", "TOKEN_AUSENTE")], {}),
    ("Erros", "T03 Cliente tenta movimentar estoque (403)", "POST", "/estoque/movimentacoes", "tokenCliente", {"unidadeId": 1, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 5, "motivo": "Teste"}, 403, {}, [("error", "PERFIL_SEM_PERMISSAO")], {}),
    ("Erros", "T04 Pedido sem canalPedido (422)", "POST", "/pedidos", "tokenCliente", {"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}], "formaPagamento": "MOCK"}, 422, {}, [("error", "VALIDACAO_INVALIDA"), ("details[0].field", "canalPedido")], {}),
    ("Erros", "T04b Pedido com quantidade negativa (422)", "POST", "/pedidos", "tokenCliente", {**PED, "itens": [{"produtoId": 1, "quantidade": -1}]}, 422, {}, [("error", "VALIDACAO_INVALIDA")], {}),
    ("Erros", "T05 Cadastro com e-mail inválido (422)", "POST", "/auth/register", None, {"nome": "Maria Souza", "email": "invalido", "senha": "Senha@123", "aceitePoliticaPrivacidade": True}, 422, {}, [("details[0].field", "email")], {}),
    ("Erros", "T07 Pedido com produto inexistente (404)", "POST", "/pedidos", "tokenCliente", {**PED, "itens": [{"produtoId": 999, "quantidade": 1}]}, 404, {}, [("error", "PRODUTO_NAO_ENCONTRADO")], {}),
    ("Erros", "T08 Pedido com estoque insuficiente (409)", "POST", "/pedidos", "tokenCliente", {**PED, "itens": [{"produtoId": 1, "quantidade": 50}]}, 409, {}, [("error", "ESTOQUE_INSUFICIENTE")], {}),
]


def js_valor(v):
    return json.dumps(v)


def item(p):
    pasta, nome, metodo, caminho, token, corpo, status, vars_, asserts, extra = p
    headers = [{"key": "Content-Type", "value": "application/json"}] + [{"key": k, "value": v} for k, v in extra.items()]
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    script = [f'pm.test("{nome}: status {status}", function () {{ pm.response.to.have.status({status}); }});']
    for caminho_json, valor in asserts:
        script.append(f'pm.test("{nome}: {caminho_json}", function () {{ pm.expect(pm.response.json().{caminho_json}).to.eql({js_valor(valor)}); }});')
    for var, caminho_json in vars_.items():
        script.append(f'pm.collectionVariables.set("{var}", pm.response.json().{caminho_json});')
    req = {"method": metodo, "header": headers, "url": {"raw": "{{baseUrl}}" + caminho, "host": ["{{baseUrl}}"], "path": caminho.split("?")[0].strip("/").split("/"),
           "query": [{"key": q.split("=")[0], "value": q.split("=")[1]} for q in (caminho.split("?")[1].split("&") if "?" in caminho else [])]}}
    if corpo is not None:
        bruto = json.dumps(corpo, ensure_ascii=False, indent=2)
        for var in ("pedidoId", "pedidoId2", "pedidoId3"):
            bruto = bruto.replace('"{{' + var + '}}"', "{{" + var + "}}")  # variável numérica: sem aspas (Postman substitui o texto)
        req["body"] = {"mode": "raw", "raw": bruto, "options": {"raw": {"language": "json"}}}
    return pasta, {"name": nome, "request": req, "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": script}}]}


def main():
    pastas: dict[str, list] = {}
    for p in PASSOS:
        pasta, it = item(p)
        pastas.setdefault(pasta, []).append(it)
    colecao = {"info": {"name": "Raízes do Nordeste — Back-End (testes T01–T16)", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                        "description": "Execute as pastas na ordem: Auth → Cardápio → Pedidos → Pagamento → Estoque → Fidelidade → Auditoria → Erros. Requer seed aplicado em banco novo."},
               "item": [{"name": n, "item": its} for n, its in pastas.items()], "variable": [{"key": "baseUrl", "value": "http://localhost:8080"}]}
    # Ordem real de execução precisa respeitar dependências: manter PASSOS linear, agrupando por pasta contígua
    linear, atual = [], None
    for p in PASSOS:
        pasta, it = item(p)
        if atual is None or atual["name"] != pasta:
            atual = {"name": pasta, "item": []}
            linear.append(atual)
        atual["item"].append(it)
    colecao["item"] = linear
    os.makedirs(os.path.join(RAIZ, "postman"), exist_ok=True)
    with open(os.path.join(RAIZ, "postman", "raizes-do-nordeste.postman_collection.json"), "w", encoding="utf-8") as f:
        json.dump(colecao, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RAIZ, "postman", "local.postman_environment.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "Local", "values": [{"key": "baseUrl", "value": "http://localhost:8080", "enabled": True}]}, f, indent=2)
    print(f"Coleção gerada com {len(PASSOS)} requisições.")


if __name__ == "__main__":
    main()

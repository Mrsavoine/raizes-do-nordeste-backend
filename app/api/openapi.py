"""Gera o documento OpenAPI 3.0 a partir do registro de endpoints (contrato sempre igual ao código)."""
from .registry import REGISTRY

ERRO_EX = {"error": "ESTOQUE_INSUFICIENTE", "message": "Não há quantidade suficiente para um ou mais itens.",
           "details": [{"field": "itens[0].quantidade", "issue": "Disponível: 1"}], "timestamp": "2026-11-04T12:00:00.000000Z",
           "path": "/pedidos", "requestId": "2f0c1a4e-6f7e-4b9a-8e55-0d1f2c3b4a5d"}
DESCRICOES = {200: "Sucesso", 201: "Criado", 204: "Sem conteúdo", 400: "Requisição malformada", 401: "Não autenticado",
              403: "Sem permissão", 404: "Não encontrado", 409: "Conflito de regra de negócio", 422: "Validação inválida",
              502: "Gateway de pagamento indisponível"}


def _resposta(status, exemplo=None, codigos=None):
    desc = DESCRICOES.get(status, "Resposta")
    if codigos:
        desc += f" — {codigos}"
    corpo = {"description": desc}
    if status != 204:
        ref = {"$ref": "#/components/schemas/Erro"} if status >= 400 else {"type": "object"}
        corpo["content"] = {"application/json": {"schema": ref, "example": exemplo if exemplo is not None else ERRO_EX}}
    return corpo


def gerar() -> dict:
    caminhos: dict = {}
    for ep in REGISTRY:
        parametros = [{"name": n, "in": "path", "required": True, "schema": {"type": "integer"}}
                      for n in __import__("re").findall(r"\{(\w+)\}", ep["path"])]
        parametros += [{"name": n, "in": "query", "required": False, "schema": {"type": t}, "description": d} for n, t, d in ep["query"]]
        parametros += [{"name": n, "in": "header", "required": True, "schema": {"type": "string"}, "description": d} for n, d in ep["headers"]]
        op = {"tags": [ep["tag"]], "summary": ep["resumo"], "operationId": f"{ep['method']}_{ep['path']}".replace("/", "_").replace("{", "").replace("}", ""),
              "parameters": parametros, "responses": {}}
        if ep["roles"] is not None or not ep["publico"]:
            op["security"] = [{"bearerAuth": []}]
            op["description"] = "Perfis autorizados: " + (", ".join(ep["roles"]) if ep["roles"] else "qualquer usuário autenticado")
        else:
            op["security"] = []
            op["description"] = "Endpoint público."
        if ep["request"] is not None:
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"type": "object"}, "example": ep["request"]}}}
        op["responses"][str(ep["status"])] = _resposta(ep["status"], ep["response"])
        if ep["method"] == "post" and ep["path"] == "/pagamentos":
            op["responses"]["200"] = _resposta(200, {**ep["response"], "reaproveitado": True}, "repetição da mesma Idempotency-Key")
        erros = dict(ep["erros"]) if isinstance(ep["erros"], dict) else {}
        if ep["request"] is not None and 400 not in erros:
            erros[400] = "JSON_INVALIDO"
        for codigo, nomes in sorted(erros.items()):
            op["responses"][str(codigo)] = _resposta(codigo, {**ERRO_EX, "error": nomes.split(" | ")[0].replace("*", "ATIVA"), "path": ep["path"]}, nomes)
        caminhos.setdefault(ep["path"], {})[ep["method"]] = op
    return {
        "openapi": "3.0.3",
        "info": {"title": "Raízes do Nordeste — API Back-End", "version": "1.0.0",
                 "description": "API REST do projeto multidisciplinar (trilha Back-End). Pagamento é SIMULADO (mock). "
                                "Valores monetários em reais (decimal); erros seguem o padrão {error, message, details, timestamp, path, requestId}."},
        "servers": [{"url": "http://localhost:8080"}],
        "paths": caminhos,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
            "schemas": {"Erro": {"type": "object", "required": ["error", "message", "details", "timestamp", "path", "requestId"], "properties": {
                "error": {"type": "string"}, "message": {"type": "string"},
                "details": {"type": "array", "items": {"type": "object", "properties": {"field": {"type": "string"}, "issue": {"type": "string"}}}},
                "timestamp": {"type": "string", "format": "date-time"}, "path": {"type": "string"}, "requestId": {"type": "string", "format": "uuid"}}}},
        },
    }

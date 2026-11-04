"""Gera docs/API_ENDPOINTS.md a partir do registro de endpoints. Uso: python -m scripts.gerar_docs_api"""
import json
import os

os.environ.setdefault("JWT_SECRET", "x" * 40)
from app.api import routes  # noqa: E402,F401
from app.api.registry import REGISTRY  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bloco(titulo, dado):
    return f"**{titulo}**\n\n```json\n{json.dumps(dado, ensure_ascii=False, indent=2)}\n```\n\n"


def main():
    partes = ["# Endpoints da API\n\nGerado automaticamente a partir do código (`python -m scripts.gerar_docs_api`). "
              "Erro padrão em todas as falhas: `{error, message, details[], timestamp, path, requestId}`.\n\n"]
    tag_atual = None
    for ep in REGISTRY:
        if ep["tag"] != tag_atual:
            tag_atual = ep["tag"]
            partes.append(f"## {tag_atual}\n\n")
        auth = "público" if ep["publico"] else ("JWT — " + (", ".join(ep["roles"]) if ep["roles"] else "qualquer perfil autenticado"))
        partes.append(f"### {ep['method'].upper()} {ep['path']}\n\n- **Finalidade:** {ep['resumo']}\n- **Autenticação/perfis:** {auth}\n- **Sucesso:** {ep['status']}\n")
        if ep["query"]:
            partes.append("- **Query:** " + "; ".join(f"`{n}` ({t}) — {d}" for n, t, d in ep["query"]) + "\n")
        if ep["headers"]:
            partes.append("- **Cabeçalhos:** " + "; ".join(f"`{n}` — {d}" for n, d in ep["headers"]) + "\n")
        if ep["erros"]:
            partes.append("- **Erros:** " + "; ".join(f"{c} `{n}`" for c, n in sorted(ep["erros"].items())) + "\n")
        partes.append("\n")
        if ep["request"] is not None:
            partes.append(bloco("Request", ep["request"]))
        if ep["response"] is not None:
            partes.append(bloco(f"Response {ep['status']}", ep["response"]))
    with open(os.path.join(RAIZ, "docs", "API_ENDPOINTS.md"), "w", encoding="utf-8") as f:
        f.write("".join(partes))
    print(f"{len(REGISTRY)} endpoints documentados")


if __name__ == "__main__":
    main()

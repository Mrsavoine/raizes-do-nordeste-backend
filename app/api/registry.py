"""Registro de endpoints: a mesma declaração cria a rota Flask e alimenta o OpenAPI (contrato = código)."""
import re
from functools import wraps

from flask import Blueprint, g, request

from ..domain.entities import Perfil
from ..domain.errors import ForbiddenError, UnauthorizedError
from ..application.services import Contexto

bp = Blueprint("api", __name__)
REGISTRY: list[dict] = []
TODOS = [p.value for p in Perfil]


def _autenticar(roles):
    def decorador(fn):
        @wraps(fn)
        def interno(*args, **kwargs):
            cabecalho = request.headers.get("Authorization", "")
            if not cabecalho.startswith("Bearer ") or len(cabecalho) < 15:
                raise UnauthorizedError("Token de acesso ausente ou malformado.", code="TOKEN_AUSENTE")
            claims = g.tokens.validar(cabecalho[7:])
            usuario = g.servicos.usuarios.por_id(int(claims["sub"]))
            if not usuario or not usuario.ativo:
                raise UnauthorizedError("Usuário inexistente ou inativo.", code="TOKEN_INVALIDO")
            if roles and usuario.perfil not in roles:
                raise ForbiddenError("Seu perfil não tem permissão para esta operação.", code="PERFIL_SEM_PERMISSAO",
                                     details=[{"field": "perfil", "issue": f"Exigido: {', '.join(roles)}"}])
            g.ctx = Contexto(usuario, g.request_id)
            return fn(*args, **kwargs)
        return interno
    return decorador


def endpoint(method, path, *, tag, resumo, roles=None, publico=False, query=None, request_ex=None,
             response_ex=None, status=200, erros=(), headers=None):
    """roles=None e publico=False => qualquer usuário autenticado."""
    def decorador(fn):
        view = fn if publico else _autenticar(roles)(fn)
        bp.add_url_rule(path, endpoint=fn.__name__, view_func=view, methods=[method])
        REGISTRY.append({"method": method.lower(), "path": re.sub(r"<(?:int:)?(\w+)>", lambda m: "{" + _camel(m.group(1)) + "}", path),
                         "tag": tag, "resumo": resumo, "roles": roles, "publico": publico, "query": query or [],
                         "request": request_ex, "response": response_ex, "status": status, "erros": list(erros),
                         "headers": headers or []})
        return fn
    return decorador


def _camel(nome: str) -> str:
    partes = nome.split("_")
    return partes[0] + "".join(p.capitalize() for p in partes[1:])

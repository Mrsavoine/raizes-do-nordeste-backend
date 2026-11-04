"""Fábrica da aplicação Flask: wiring das dependências, tratamento centralizado de erros e Swagger UI."""
import logging
import uuid

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from ..application.services import Contexto, Servicos
from ..config import Settings
from ..domain.errors import DomainError
from ..infrastructure.db import agora_iso, connect, run_migrations
from ..infrastructure.payment_gateway import PaymentGatewayMock
from ..infrastructure.security import TokenService

log = logging.getLogger("raizes")

SWAGGER_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Raízes do Nordeste — Swagger</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"></head>
<body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>window.ui = SwaggerUIBundle({url: '/openapi.json', dom_id: '#swagger-ui', persistAuthorization: true});</script></body></html>"""


def _erro(status, codigo, mensagem, detalhes=None):
    corpo = {"error": codigo, "message": mensagem, "details": detalhes or [], "timestamp": agora_iso(),
             "path": request.path, "requestId": getattr(g, "request_id", str(uuid.uuid4()))}
    return jsonify(corpo), status


def create_app(settings: Settings | None = None) -> Flask:
    from . import routes  # noqa: F401  (registra endpoints)
    from .openapi import gerar
    from .registry import bp

    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config["SETTINGS"] = settings
    tokens, gateway = TokenService(settings.jwt_secret, settings.jwt_expires_seconds), PaymentGatewayMock()

    boot = connect(settings.database_path)
    run_migrations(boot)
    boot.close()

    @app.before_request
    def preparar():
        g.request_id = str(uuid.uuid4())
        g.conn = connect(settings.database_path)
        g.tokens = tokens
        g.ctx = Contexto(None, g.request_id)
        g.servicos = Servicos(g.conn, settings, tokens, gateway)

    @app.teardown_request
    def encerrar(_exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.after_request
    def cabecalhos(resp):
        resp.headers["X-Request-Id"] = getattr(g, "request_id", "-")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(DomainError)
    def dominio(exc):
        return _erro(exc.status, exc.code, exc.message, exc.details)

    @app.errorhandler(HTTPException)
    def http(exc):
        codigos = {404: "RECURSO_NAO_ENCONTRADO", 405: "METODO_NAO_PERMITIDO", 413: "CORPO_MUITO_GRANDE", 415: "TIPO_NAO_SUPORTADO"}
        return _erro(exc.code, codigos.get(exc.code, "ERRO_HTTP"), exc.description if exc.code != 404 else "Recurso não encontrado.")

    @app.errorhandler(Exception)
    def inesperado(exc):
        log.exception("Erro inesperado [%s]", getattr(g, "request_id", "-"))
        return _erro(500, "ERRO_INTERNO", "Erro interno. Informe o requestId ao suporte.")

    app.register_blueprint(bp)
    spec = gerar()
    app.add_url_rule("/openapi.json", "openapi", lambda: jsonify(spec))
    app.add_url_rule("/docs", "docs", lambda: (SWAGGER_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}))
    return app

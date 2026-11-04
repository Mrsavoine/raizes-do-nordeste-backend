"""Exceções de domínio. Cada uma carrega o status HTTP e o código de erro do contrato da API."""


class DomainError(Exception):
    status = 400
    code = "ERRO_DE_DOMINIO"

    def __init__(self, message: str, details: list | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []
        if code:
            self.code = code


class ValidationError(DomainError):
    status = 422
    code = "VALIDACAO_INVALIDA"


class MalformedRequestError(DomainError):
    status = 400
    code = "REQUISICAO_MALFORMADA"


class UnauthorizedError(DomainError):
    status = 401
    code = "NAO_AUTENTICADO"


class ForbiddenError(DomainError):
    status = 403
    code = "ACESSO_NEGADO"


class NotFoundError(DomainError):
    status = 404
    code = "RECURSO_NAO_ENCONTRADO"


class ConflictError(DomainError):
    status = 409
    code = "CONFLITO_DE_REGRA"


class GatewayUnavailableError(DomainError):
    status = 502
    code = "GATEWAY_PAGAMENTO_INDISPONIVEL"

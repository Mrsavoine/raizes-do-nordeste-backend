"""Hash de senha (scrypt via Werkzeug) e emissão/validação de JWT HS256."""
import time

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from ..domain.errors import UnauthorizedError


def hash_senha(senha: str) -> str:
    return generate_password_hash(senha, method="scrypt")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return check_password_hash(senha_hash, senha)


class TokenService:
    def __init__(self, secret: str, expires_seconds: int):
        self._secret = secret
        self.expires_seconds = expires_seconds

    def emitir(self, usuario_id: int, perfil: str) -> str:
        agora = int(time.time())
        payload = {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": agora + self.expires_seconds}
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def validar(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token expirado.", code="TOKEN_EXPIRADO")
        except jwt.PyJWTError:
            raise UnauthorizedError("Token inválido.", code="TOKEN_INVALIDO")

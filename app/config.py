"""Configuração lida exclusivamente de variáveis de ambiente (nenhum segredo no código)."""
import os
from dataclasses import dataclass


def load_dotenv(path: str = ".env") -> None:
    """Carrega pares CHAVE=VALOR de um .env simples, sem sobrescrever o ambiente real."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_path: str
    jwt_secret: str
    jwt_expires_seconds: int
    allow_payment_simulation: bool

    @staticmethod
    def from_env() -> "Settings":
        secret = os.environ.get("JWT_SECRET", "")
        if len(secret) < 32:
            raise RuntimeError(
                "JWT_SECRET ausente ou curto demais (mínimo 32 caracteres). "
                "Copie .env.example para .env e defina um valor próprio."
            )
        return Settings(
            database_path=os.environ.get("DATABASE_PATH", "raizes.db"),
            jwt_secret=secret,
            jwt_expires_seconds=int(os.environ.get("JWT_EXPIRES_SECONDS", "3600")),
            allow_payment_simulation=os.environ.get("MOCK_PAYMENT_ALLOW_SIMULATION", "true").lower() == "true",
        )

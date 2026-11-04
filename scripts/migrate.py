"""Aplica migrations pendentes: python -m scripts.migrate"""
from app.config import Settings, load_dotenv
from app.infrastructure.db import connect, run_migrations

if __name__ == "__main__":
    load_dotenv()
    conn = connect(Settings.from_env().database_path)
    print("Migrations aplicadas:", run_migrations(conn) or "nenhuma pendente")

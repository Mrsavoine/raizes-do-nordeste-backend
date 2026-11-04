"""Carrega dados de demonstração: python -m scripts.seed"""
from app.config import Settings, load_dotenv
from app.infrastructure.db import connect, run_migrations
from app.infrastructure.seed import aplicar_seed

if __name__ == "__main__":
    load_dotenv()
    conn = connect(Settings.from_env().database_path)
    run_migrations(conn)
    print("Seed aplicado." if aplicar_seed(conn) else "Seed ignorado: banco já possui dados.")

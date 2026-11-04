"""Ponto de entrada: python run.py (lê .env, aplica migrations e seed se SEED_ON_START=true)."""
import os

from app.config import Settings, load_dotenv


def main():
    load_dotenv()
    settings = Settings.from_env()
    from app.api import create_app
    from app.infrastructure.db import connect
    from app.infrastructure.seed import aplicar_seed

    app = create_app(settings)
    if os.environ.get("SEED_ON_START", "true").lower() == "true":
        conn = connect(settings.database_path)
        if aplicar_seed(conn):
            print("Seed aplicado (dados de demonstração).")
        conn.close()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")), threaded=True)


if __name__ == "__main__":
    main()

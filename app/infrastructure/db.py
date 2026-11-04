"""Conexão SQLite, transações e execução de migrations versionadas (database/migrations/V<n>__*.sql)."""
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "database", "migrations")


def agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)  # transações explícitas
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """BEGIN IMMEDIATE serializa escritores: evita venda acima do estoque sob concorrência."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def run_migrations(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (versao INTEGER PRIMARY KEY, arquivo TEXT NOT NULL, aplicada_em TEXT NOT NULL)"
    )
    aplicadas = {r["versao"] for r in conn.execute("SELECT versao FROM schema_migrations")}
    novas = []
    arquivos = sorted(
        (f for f in os.listdir(MIGRATIONS_DIR) if re.match(r"V\d+__.+\.sql$", f)),
        key=lambda f: int(re.match(r"V(\d+)__", f).group(1)),
    )
    for arquivo in arquivos:
        versao = int(re.match(r"V(\d+)__", arquivo).group(1))
        if versao in aplicadas:
            continue
        with open(os.path.join(MIGRATIONS_DIR, arquivo), encoding="utf-8") as handle:
            script = handle.read()
        conn.executescript("BEGIN;\n" + script + "\nCOMMIT;")
        conn.execute(
            "INSERT INTO schema_migrations (versao, arquivo, aplicada_em) VALUES (?,?,?)", (versao, arquivo, agora_iso())
        )
        novas.append(arquivo)
    return novas

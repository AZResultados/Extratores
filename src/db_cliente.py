"""
Acesso ao cadastro de clientes.
Compartilha o mesmo arquivo SQLite de db_senha (dados.db) — tabelas separadas.
"""

import os
import sqlite3
from pathlib import Path

from logger import get_logger

log = get_logger("extratores.db")

DB_PATH = Path(os.environ.get("EXTRATORES_DB",
               str(Path.home() / ".extratores" / "dados.db")))


def _conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _garantir_schema():
    with _conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                nome     TEXT PRIMARY KEY,
                base_dir TEXT NOT NULL
            )
        """)


def set_cliente(nome: str, base_dir: str):
    """Cadastra ou atualiza cliente."""
    _garantir_schema()
    with _conectar() as conn:
        conn.execute("""
            INSERT INTO clientes (nome, base_dir) VALUES (?, ?)
            ON CONFLICT(nome) DO UPDATE SET base_dir = excluded.base_dir
        """, (nome, base_dir))
    log.info("Cliente cadastrado | nome=%s | base_dir=%s", nome, base_dir)


def get_cliente(nome: str) -> dict:
    """Retorna {nome, base_dir} ou None se nao encontrado."""
    try:
        with _conectar() as conn:
            row = conn.execute(
                "SELECT nome, base_dir FROM clientes WHERE nome=?", (nome,)
            ).fetchone()
        return {"nome": row[0], "base_dir": row[1]} if row else None
    except Exception:
        return None


def listar_clientes() -> list:
    """Retorna [(nome, base_dir)] ordenado por nome."""
    try:
        with _conectar() as conn:
            return conn.execute(
                "SELECT nome, base_dir FROM clientes ORDER BY nome"
            ).fetchall()
    except Exception:
        return []


def remover_cliente(nome: str):
    _garantir_schema()
    with _conectar() as conn:
        conn.execute("DELETE FROM clientes WHERE nome=?", (nome,))
    log.info("Cliente removido | nome=%s", nome)

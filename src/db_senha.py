"""
Acesso ao banco de senhas dos extratores.
MVP: SQLite local em ~/.extratores/dados.db
Producao: trocar EXTRATORES_DB para apontar para MySQL (sem mudanca de codigo nos extratores)

Schema: (cliente, senha) — PRIMARY KEY garante dedup nativo.
Emissor e identificador nao sao armazenados: o router detecta o emissor
pelo conteudo do PDF apos abrir, independente de qual senha funcionou.
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("EXTRATORES_DB",
               str(Path.home() / ".extratores" / "dados.db")))


def _conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _garantir_schema():
    with _conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS senhas_pdf (
                cliente TEXT NOT NULL,
                senha   TEXT NOT NULL,
                PRIMARY KEY (cliente, senha)
            )
        """)


def set_senha(cliente: str, senha: str) -> bool:
    """
    Cadastra senha para o cliente.
    Retorna True se cadastrada, False se ja existia (duplicata ignorada).
    """
    _garantir_schema()
    with _conectar() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO senhas_pdf (cliente, senha) VALUES (?, ?)",
            (cliente, senha)
        )
        return cur.rowcount == 1


def get_todas_senhas(cliente: str) -> list:
    """Retorna lista de senhas cadastradas para o cliente — para o router ciclar."""
    try:
        with _conectar() as conn:
            rows = conn.execute(
                "SELECT senha FROM senhas_pdf WHERE cliente=?",
                (cliente,)
            ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def remover_senha(cliente: str, senha: str):
    """Remove uma senha especifica do cliente."""
    with _conectar() as conn:
        conn.execute(
            "DELETE FROM senhas_pdf WHERE cliente=? AND senha=?",
            (cliente, senha)
        )


def listar() -> list:
    """Lista clientes e quantidade de senhas — sem expor as senhas."""
    try:
        with _conectar() as conn:
            return conn.execute("""
                SELECT cliente, COUNT(*) as total
                FROM senhas_pdf
                GROUP BY cliente
                ORDER BY cliente
            """).fetchall()
    except Exception:
        return []

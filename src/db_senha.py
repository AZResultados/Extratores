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
        nova = cur.rowcount == 1
    if nova:
        log.info("Senha cadastrada | cliente=%s", cliente)
    else:
        log.debug("Senha duplicada ignorada | cliente=%s", cliente)
    return nova


def get_todas_senhas(cliente: str) -> list:
    """Retorna lista de senhas cadastradas para o cliente — para o router ciclar."""
    try:
        with _conectar() as conn:
            rows = conn.execute(
                "SELECT senha FROM senhas_pdf WHERE cliente=?",
                (cliente,)
            ).fetchall()
        senhas = [r[0] for r in rows]
        log.debug("Senhas consultadas | cliente=%s | total=%d", cliente, len(senhas))
        return senhas
    except Exception as e:
        log.error("Erro ao consultar senhas | cliente=%s | erro=%s", cliente, str(e))
        return []


def remover_senha(cliente: str, senha: str):
    """Remove uma senha especifica do cliente."""
    _garantir_schema()
    with _conectar() as conn:
        conn.execute(
            "DELETE FROM senhas_pdf WHERE cliente=? AND senha=?",
            (cliente, senha)
        )
    log.info("Senha removida | cliente=%s", cliente)


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

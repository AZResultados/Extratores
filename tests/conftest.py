import logging
import sys
from pathlib import Path

import pytest

# Garante que src/ e tests/ estão no path antes de qualquer importação
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# Importa logger para disparar _setup() e depois silencia file handlers
import logger as _logger_mod  # noqa: F401
_extratores_log = logging.getLogger("extratores")
_extratores_log.handlers.clear()
_extratores_log.addHandler(logging.NullHandler())


# ---------------------------------------------------------------------------
# Fixtures de banco de dados isolado
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path):
    """Caminho para SQLite temporário — isolado por teste."""
    return tmp_path / "test.db"


@pytest.fixture()
def patch_db_senha(db_path, monkeypatch):
    import db_senha
    monkeypatch.setattr(db_senha, "DB_PATH", db_path)
    yield db_path


@pytest.fixture()
def patch_db_cliente(db_path, monkeypatch):
    import db_cliente
    monkeypatch.setattr(db_cliente, "DB_PATH", db_path)
    yield db_path


@pytest.fixture()
def db_isolado(db_path, monkeypatch):
    """Patch em ambos os módulos DB para o mesmo banco temporário."""
    import db_senha, db_cliente
    monkeypatch.setattr(db_senha,   "DB_PATH", db_path)
    monkeypatch.setattr(db_cliente, "DB_PATH", db_path)
    yield db_path



"""
Logging centralizado para os extratores.
  Arquivo : ~/.extratores/extrator.log
  Rotacao : 5 MB, 3 backups
  Nivel   : INFO (override via env EXTRATORES_LOG_LEVEL)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Retorna logger filho de 'extratores'. Chamar no topo de cada modulo."""
    return logging.getLogger(name)


def _setup() -> None:
    root = logging.getLogger("extratores")
    if root.handlers:
        return

    level_name = os.environ.get("EXTRATORES_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)
    root.propagate = False

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    try:
        log_dir = Path.home() / ".extratores"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "extrator.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as exc:
        print(f"WARN: logging nao iniciado: {exc}", file=sys.stderr)


_setup()

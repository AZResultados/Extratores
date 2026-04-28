"""
Utilitário compartilhado: descriptografia de PDF in-memory via pikepdf.
Retorna io.BytesIO (sem tocar disco) ou o Path original se sem senha.
"""

import io
import sys
from pathlib import Path


def descriptografar(pdf_path: Path, password: str):
    """Abre com senha e retorna BytesIO. Fatal se senha incorreta (uso nos extratores)."""
    if not password:
        return pdf_path
    import pikepdf
    try:
        with pikepdf.open(pdf_path, password=password) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            buf.seek(0)
        return buf
    except Exception as e:
        print(f"ERRO: falha ao descriptografar {pdf_path.name}: {e}", file=sys.stderr)
        sys.exit(1)


def tentar_descriptografar(pdf_path: Path, password: str):
    """Tenta abrir com senha. Levanta Exception se falhar — uso exclusivo do router."""
    if not password:
        return pdf_path
    import pikepdf
    with pikepdf.open(pdf_path, password=password) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
    return buf

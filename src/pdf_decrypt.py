"""
Utilitário compartilhado: descriptografia de PDF in-memory via pikepdf.
Retorna io.BytesIO (sem tocar disco) ou o Path original se sem senha.
"""

import io
from pathlib import Path


def descriptografar(pdf_path: Path, password: str):
    """Abre pdf_path com pikepdf usando password e retorna BytesIO in-memory.
    Se password for vazio, retorna pdf_path sem modificação.
    Erro de senha propaga como exception → caller faz sys.exit(1).
    """
    if not password:
        return pdf_path
    import pikepdf
    with pikepdf.open(pdf_path, password=password) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
    return buf

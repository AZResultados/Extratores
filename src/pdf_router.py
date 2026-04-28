"""
Detecta o emissor de um PDF e retorna (emissor, source).
Tenta abrir sem senha; se protegido, cicla pelas senhas cadastradas para o cliente.
A senha serve apenas para ABRIR o PDF — o emissor e sempre identificado pelo conteudo.
"""

import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

from pdf_decrypt import tentar_descriptografar
from db_senha import get_todas_senhas

# Fingerprints por emissor — baseados no texto da primeira pagina
# Para adicionar novo emissor: incluir nova entrada aqui
FINGERPRINTS = {
    "mercadopago": ["Mercado Pago", "MercadoPago"],
    "santander":   ["Santander", "SANTANDER"],
}


def detectar_emissor(texto: str) -> str:
    """Identifica o emissor pelo conteudo do PDF. Levanta ValueError se nao reconhecido."""
    for emissor, marcadores in FINGERPRINTS.items():
        if any(m in texto for m in marcadores):
            return emissor
    raise ValueError("Emissor nao reconhecido — layout fora do padrao suportado.")


def _ler_primeira_pagina(source) -> str:
    if hasattr(source, "seek"):
        source.seek(0)
    with pdfplumber.open(source) as pdf:
        texto = pdf.pages[0].extract_text() or ""
    if hasattr(source, "seek"):
        source.seek(0)
    return texto


def rotear(pdf_path: Path, cliente: str) -> tuple:
    """
    Retorna (emissor, source).
    source: Path original (sem senha) ou BytesIO (descriptografado in-memory).
    """
    # Tenta abrir sem senha
    try:
        texto = _ler_primeira_pagina(pdf_path)
        if texto.strip():
            emissor = detectar_emissor(texto)
            return emissor, pdf_path
    except Exception:
        pass

    # Cicla pelas senhas cadastradas para o cliente
    for senha in get_todas_senhas(cliente):
        try:
            source = tentar_descriptografar(pdf_path, senha)
            texto  = _ler_primeira_pagina(source)
            emissor = detectar_emissor(texto)
            return emissor, source
        except Exception:
            continue

    raise ValueError(
        f"{pdf_path.name}: nao foi possivel abrir ou identificar o emissor. "
        f"Verifique se a senha esta cadastrada para o cliente '{cliente}'."
    )

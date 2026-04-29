"""
Extrator de Fatura - Cartão Samsung Itaú
Ordem de leitura: esquerda → direita por página (col e antes de col d).
Fingerprint: "App Samsung Itaú" | id_lote prefix: SM-
Chamado pelo Excel via VBA (CLI: --input-dir, --cliente).
"""

import re
import sys
import io
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

from logger import get_logger
from pdf_decrypt import descriptografar

log = get_logger("extratores.samsung")

X_DIV = 330

RE_DATA  = re.compile(r"^\d{2}/\d{2}$")
RE_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
RE_PARC  = re.compile(r"^(\d{2})/(\d{2})$")
RE_TITUL = re.compile(r"Titular\s+([A-Z][A-Z\s]+)")
RE_CART  = re.compile(r"Cartão\s+\d{4}\.XXXX\.XXXX\.(\d{4})")
RE_VENC  = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})")


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def extrair_texto_pdf(source) -> str:
    partes = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
    return "\n".join(partes)


def extrair_vencimento(texto: str) -> date:
    m = RE_VENC.search(texto)
    if not m:
        raise ValueError("Vencimento não encontrado.")
    return datetime.strptime(m.group(1), "%d/%m/%Y").date()


def extrair_titular(texto: str) -> tuple:
    nome        = "Desconhecido"
    final_cartao = ""

    m = RE_TITUL.search(texto)
    if m:
        # [A-Z\s]+ captura até "C" de "Cartão" na linha seguinte — pega só a 1ª linha
        nome = m.group(1).split("\n")[0].strip()

    m2 = RE_CART.search(texto)
    if m2:
        final_cartao = m2.group(1)

    return nome, final_cartao

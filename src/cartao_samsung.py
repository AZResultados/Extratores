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


# ---------------------------------------------------------------------------
# Extração de segmento (uma coluna de uma página)
# ---------------------------------------------------------------------------

def extrair_segmento(page, col: str) -> list:
    words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)

    if col == "e":
        words_col = [w for w in words if w["x0"] < X_DIV]
    else:
        words_col = [w for w in words if w["x0"] >= X_DIV]

    linhas_dict = defaultdict(list)
    for w in words_col:
        y = round(w["top"] / 4) * 4
        linhas_dict[y].append(w)

    resultado = []
    for y in sorted(linhas_dict.keys()):
        tokens = [w["text"] for w in sorted(linhas_dict[y], key=lambda w: w["x0"])]
        resultado.append((y, tokens))

    return resultado


# ---------------------------------------------------------------------------
# Inferência de ano
# ---------------------------------------------------------------------------

def inferir_ano_parcelado(mes: int, vencimento: date, parcela_atual: int) -> int:
    ano      = vencimento.year
    mes_orig = vencimento.month - (parcela_atual - 1)
    while mes_orig <= 0:
        mes_orig += 12
        ano      -= 1
    mes_ref = mes_orig % 12 or 12
    return ano if mes <= mes_ref else ano - 1


def inferir_ano_avista(mes: int, vencimento: date) -> int:
    return vencimento.year - 1 if mes > vencimento.month else vencimento.year


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

KEYWORDS_OUTROS = ["iof", "juros", "multa", "anuidade", "encargo", "refinanc"]


def classificar_tipo(descricao: str, tem_parcela: bool, secao_atual: str) -> str:
    if secao_atual == "pagamentos":
        return "Pagamento"
    dl = descricao.lower()
    for kw in KEYWORDS_OUTROS:
        if kw in dl:
            return "Outros"
    return "Compra parcelada" if tem_parcela else "Compra à vista"

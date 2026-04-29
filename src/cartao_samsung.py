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


# ---------------------------------------------------------------------------
# Seções do PDF
# ---------------------------------------------------------------------------

SECAO_PAGAMENTOS  = "Pagamentos efetuados"
SECAO_LANCAMENTOS = "Lançamentos: compras e saques"
SECAO_INTER       = "Lançamentos internacionais"
SECAO_PROXIMAS    = "Compras parceladas - próximas faturas"
SECAO_IGNORAR     = {SECAO_PROXIMAS}
_SECOES_LABEL     = {SECAO_PAGAMENTOS, SECAO_LANCAMENTOS, SECAO_INTER, SECAO_PROXIMAS}


# ---------------------------------------------------------------------------
# Parser de lançamentos
# ---------------------------------------------------------------------------

def parsear_lancamentos(caminho: Path, vencimento: date, titular: str, final_cartao: str, source=None) -> list:
    lancamentos = []
    vistos      = set()
    secao_atual = ""

    with pdfplumber.open(source if source is not None else caminho) as pdf:
        for pg_idx in range(len(pdf.pages)):
            page = pdf.pages[pg_idx]
            for col in ("e", "d"):
                segmento = extrair_segmento(page, col)

                for y, tokens in segmento:
                    txt = " ".join(tokens)

                    # Detectar label de seção
                    if txt in _SECOES_LABEL:
                        secao_atual = txt
                        log.debug("Secao detectada | pg=%d col=%s | secao=%s", pg_idx, col, txt)
                        continue

                    # Ignorar seção de próximas faturas
                    if secao_atual in SECAO_IGNORAR:
                        continue

                    # Detectar lançamento
                    t = list(tokens)
                    if len(t) < 3:
                        continue
                    if not RE_DATA.match(t[0]):
                        continue
                    if not RE_VALOR.match(t[-1]):
                        continue

                    data_str  = t[0]
                    valor_str = t[-1]

                    if RE_PARC.match(t[-2]):
                        parcela_str = t[-2]
                        desc_tokens = t[1:-2]
                    else:
                        parcela_str = ""
                        desc_tokens = t[1:-1]

                    descricao = " ".join(desc_tokens).strip()
                    if not descricao:
                        continue

                    dia, mes = map(int, data_str.split("/"))
                    valor    = float(valor_str.replace(".", "").replace(",", "."))

                    tem_parcela = bool(parcela_str)
                    if tem_parcela:
                        pa, pt        = map(int, parcela_str.split("/"))
                        parcela_num   = pa
                        qtde_parcelas = pt
                    else:
                        parcela_num   = 0
                        qtde_parcelas = 0

                    try:
                        if tem_parcela:
                            ano = inferir_ano_parcelado(mes, vencimento, parcela_num)
                        else:
                            ano = inferir_ano_avista(mes, vencimento)
                        data_compra = date(ano, mes, dia).strftime("%d/%m/%Y")
                    except Exception:
                        data_compra = None

                    if secao_atual == SECAO_INTER:
                        tipo = "Outros"
                    else:
                        sec  = "pagamentos" if secao_atual == SECAO_PAGAMENTOS else "lancamentos"
                        tipo = classificar_tipo(descricao, tem_parcela, sec)

                    valor_final = abs(valor) if tipo == "Pagamento" else -abs(valor)

                    if qtde_parcelas > 0:
                        descricao_adaptada = f"{descricao} parc {parcela_num}/{qtde_parcelas}"
                    else:
                        descricao_adaptada = descricao
                    if data_compra:
                        descricao_adaptada += f" {data_compra}"

                    chave = (str(caminho), pg_idx, col, y)
                    if chave in vistos:
                        continue
                    vistos.add(chave)

                    lancamentos.append({
                        "arquivo":            caminho.name,
                        "titular":            titular,
                        "final_cartao":       final_cartao,
                        "tipo":               tipo,
                        "data_compra":        data_compra,
                        "descricao":          descricao,
                        "parcela_num":        parcela_num,
                        "qtde_parcelas":      qtde_parcelas,
                        "vencimento":         vencimento.strftime("%d/%m/%Y"),
                        "descricao_adaptada": descricao_adaptada,
                        "valor":              valor_final,
                    })

    return lancamentos

"""
Extrator de Fatura - Cartão de Crédito Santander
Ordem de leitura linear: 2e → 2d → 3e → 3d → 4e → 4d ...
Titular carrega sequencialmente entre segmentos.
Chamado pelo Excel via VBA (CLI: --input-dir, --cliente).
"""

import re
import sys
import json
import io
import argparse
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

from pdf_decrypt import descriptografar

X_DIV = 250  # divisão entre coluna esq e dir


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
    m = re.search(r"Vencimento.{0,60}?(\d{2}/\d{2}/\d{4})", texto, re.DOTALL)
    if not m:
        raise ValueError("Vencimento não encontrado.")
    return datetime.strptime(m.group(1), "%d/%m/%Y").date()


RE_DATA  = re.compile(r"^\d{2}/\d{2}$")
RE_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
RE_PARC  = re.compile(r"^\d{2}/\d{2}$")
RE_TITUL = re.compile(
    r"@?\s*([A-ZÀ-Ú][A-ZÀ-Ú\s]+?)\s*-\s*\d{4}\s+XXXX\s+XXXX\s+(\d{4})"
)


# ---------------------------------------------------------------------------
# Inferência de ano
# ---------------------------------------------------------------------------

def inferir_ano_parcelado(dia: int, mes: int, vencimento: date, parcela_atual: int) -> int:
    ano      = vencimento.year
    mes_orig = vencimento.month - (parcela_atual - 1)
    while mes_orig <= 0:
        mes_orig += 12
        ano      -= 1
    mes_ref = mes_orig % 12 or 12
    return ano if mes == mes_ref else (ano if mes < mes_ref else ano - 1)


def inferir_ano_avista(dia: int, mes: int, vencimento: date) -> int:
    return vencimento.year - 1 if mes > vencimento.month else vencimento.year


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

KEYWORDS_PAGAMENTO = ["deb autom de fatura", "pagamento"]
KEYWORDS_OUTROS    = ["iof", "juros", "multa", "anuidade"]
LIMITE_AJUSTE      = 1.00


def classificar_tipo(descricao: str, valor: float, tem_parcela: bool) -> str:
    dl = descricao.lower()
    if valor < 0 and abs(valor) < LIMITE_AJUSTE:
        if not any(kw in dl for kw in KEYWORDS_PAGAMENTO):
            return "Ajuste"
    for kw in KEYWORDS_PAGAMENTO:
        if kw in dl:
            return "Pagamento"
    for kw in KEYWORDS_OUTROS:
        if kw in dl:
            return "Outros"
    return "Compra parcelada" if tem_parcela else "Compra à vista"


# ---------------------------------------------------------------------------
# Extração de segmento (uma coluna de uma página)
# ---------------------------------------------------------------------------

def extrair_segmento(page, col: str) -> list:
    """
    Extrai words de uma coluna (col='e' ou 'd') de uma página.
    Retorna lista de (y, [tokens]) ordenada por y.
    """
    words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)

    # Filtrar por coluna
    if col == "e":
        words_col = [w for w in words if w["x0"] < X_DIV]
    else:
        words_col = [w for w in words if w["x0"] >= X_DIV]

    # Agrupar por Y (granularidade 4)
    linhas_dict = defaultdict(list)
    for w in words_col:
        y = round(w["top"] / 4) * 4
        linhas_dict[y].append(w)

    resultado = []
    ys = sorted(linhas_dict.keys())
    i = 0
    while i < len(ys):
        y = ys[i]
        tokens = [w["text"] for w in sorted(linhas_dict[y], key=lambda w: w["x0"])]

        # Funde prefixo solitário ('3' ou '2') com linha seguinte
        if tokens in (["3"], ["2"]) and i + 1 < len(ys):
            tokens_next = [w["text"] for w in sorted(linhas_dict[ys[i+1]], key=lambda w: w["x0"])]
            if tokens_next and RE_DATA.match(tokens_next[0]):
                tokens = tokens + tokens_next
                i += 1

        resultado.append((y, tokens))
        i += 1

    return resultado


# ---------------------------------------------------------------------------
# Parsing completo — ordem linear 2e→2d→3e→3d...
# ---------------------------------------------------------------------------

def parsear_lancamentos(caminho: Path, vencimento: date, source=None) -> list:
    lancamentos  = []
    vistos       = set()
    titular_atual = "Desconhecido"

    with pdfplumber.open(source if source is not None else caminho) as pdf:
        paginas = list(range(len(pdf.pages)))

        # Ordem linear: pe, pd para cada página
        for pg_idx in paginas:
            page = pdf.pages[pg_idx]
            for col in ("e", "d"):
                segmento = extrair_segmento(page, col)

                for y, tokens in segmento:
                    txt = " ".join(tokens)

                    # Detectar titular
                    m = RE_TITUL.search(txt)
                    if m:
                        nome = " ".join(m.group(1).split())
                        cartao = m.group(2)
                        titular_atual = f"{nome} - {cartao}"
                        continue

                    # Detectar lançamento
                    t = list(tokens)
                    if t and re.match(r"^\d$", t[0]):
                        t = t[1:]
                    if len(t) < 3:
                        continue
                    if not RE_DATA.match(t[0]):
                        continue
                    if not RE_VALOR.match(t[-1]):
                        continue

                    data_str  = t[0]
                    valor_str = t[-1]

                    # Parcela
                    if len(t) >= 3 and RE_PARC.match(t[-2]):
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
                        pa, pt  = map(int, parcela_str.split("/"))
                        parcela = f"{pa:02d}/{pt:02d}"
                    else:
                        parcela = None

                    tipo        = classificar_tipo(descricao, valor, tem_parcela)
                    valor_final = abs(valor) if tipo in ("Pagamento", "Ajuste") else -abs(valor)

                    chave = (str(caminho), pg_idx, col, y)
                    if chave in vistos:
                        continue
                    vistos.add(chave)

                    lancamentos.append({
                        "arquivo":        caminho.name,
                        "vencimento":     vencimento.strftime("%d/%m/%Y"),
                        "descricao":      descricao,
                        "parcela":        parcela,
                        "valor":          valor_final,
                        "tipo":           tipo,
                        "titular_cartao": titular_atual,
                    })

    return lancamentos


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def validar_total(lancamentos: list, texto: str):
    m = re.search(r"\(=\)\s*Saldo Desta Fatura\s+([\d.]+,\d{2})", texto)
    if not m:
        return False, 0.0, 0.0
    total_pdf  = float(m.group(1).replace(".", "").replace(",", "."))
    tipos_db   = {"Compra parcelada", "Compra à vista", "Outros"}
    total_calc = sum(abs(l["valor"]) for l in lancamentos if l["tipo"] in tipos_db)
    return abs(total_pdf - total_calc) < 0.10, total_pdf, total_calc


# ---------------------------------------------------------------------------
# Processar pasta
# ---------------------------------------------------------------------------

def processar_arquivo(pdf_path: Path, source) -> list:
    """Processa um PDF já aberto (source = Path ou BytesIO). Chamado pelo extrator.py."""
    texto = extrair_texto_pdf(source)
    if isinstance(source, io.BytesIO):
        source.seek(0)
    venc        = extrair_vencimento(texto)
    lancamentos = parsear_lancamentos(pdf_path, venc, source)
    ok, total_pdf, total_calc = validar_total(lancamentos, texto)
    if not ok:
        raise ValueError(
            f"{pdf_path.name}: divergencia R$ {abs(total_pdf - total_calc):.2f} "
            f"(PDF={total_pdf:.2f} / calculado={total_calc:.2f})"
        )
    for l in lancamentos:
        l["emissor"] = "santander"
    return lancamentos


def processar_pasta(pasta: Path, password: str = "") -> list:
    pdfs_vistos = {}
    for p in pasta.glob("*"):
        if p.suffix.lower() == ".pdf":
            pdfs_vistos[p.name.lower()] = p

    pdfs = sorted(pdfs_vistos.values())
    if not pdfs:
        raise FileNotFoundError("Nenhum PDF encontrado na pasta.")

    todos = []
    for pdf_path in pdfs:
        source = descriptografar(pdf_path, password)
        todos.extend(processar_arquivo(pdf_path, source))

    return todos


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--cliente",   required=True)
    parser.add_argument("--password",  default="")
    args = parser.parse_args()

    # Standalone: usa --password ou stdin. Producao: extrator.py gerencia senha via router.
    password = args.password
    if not sys.stdin.isatty():
        linha = sys.stdin.readline().strip()
        if linha:
            password = linha

    avisos     = []
    input_path = Path(args.input_dir)

    if not input_path.exists():
        print(f"ERRO: Pasta não encontrada: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.name != args.cliente:
        avisos.append(
            f"AVISO: Nome da pasta ({input_path.name}) diverge do --cliente "
            f"({args.cliente}). Verifique isolamento de dados."
        )

    ts      = datetime.now()
    id_lote = f"SA-{ts.strftime('%Y%m%d-%H%M%S')}"

    try:
        lancamentos = processar_pasta(input_path, password)
        envelope = {
            "id_lote":            id_lote,
            "data_processamento": ts.isoformat(timespec="seconds"),
            "emissor":            "santander",
            "cliente":            args.cliente,
            "avisos":             avisos,
            "lancamentos": [
                {
                    "cliente":        args.cliente,
                    "id_lote":        id_lote,
                    "arquivo":        l["arquivo"],
                    "vencimento":     l["vencimento"],
                    "descricao":      l["descricao"],
                    "parcela":        l["parcela"],
                    "valor":          l["valor"],
                    "tipo":           l["tipo"],
                    "titular_cartao": l["titular_cartao"],
                }
                for l in lancamentos
            ],
        }
        print(json.dumps(envelope, ensure_ascii=False))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

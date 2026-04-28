"""
Extrator de Fatura - Cartão de Crédito Mercado Pago
Chamado pelo Excel via VBA (CLI: --input-dir, --cliente).
"""

import re
import sys
import json
import io
import argparse
from datetime import date, datetime
from pathlib import Path

# Força UTF-8 no stdout (evita CP850/CP1252 no cmd do Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")



# ---------------------------------------------------------------------------
# Extração de texto do PDF
# ---------------------------------------------------------------------------

def extrair_texto_pdf(caminho_pdf: Path) -> str:
    texto = []
    with pdfplumber.open(str(caminho_pdf)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texto.append(t)
    return "\n".join(texto)


# ---------------------------------------------------------------------------
# Parsing do cabeçalho
# ---------------------------------------------------------------------------

def extrair_vencimento(texto: str) -> date:
    m = re.search(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", texto)
    if not m:
        raise ValueError("Data de vencimento não encontrada.")
    return datetime.strptime(m.group(1), "%d/%m/%Y").date()


def extrair_titular_cartao(texto: str) -> str:
    """Extrai nome do titular e últimos 4 dígitos do cartão.
    Formato saída: 'James William da Costa - 7863'
    """
    import re as _re
    # Nome do titular: primeira linha não vazia
    nome = "Desconhecido"
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha:
            nome = linha
            break

    # Últimos 4 dígitos: padrão "Cartão Visa [************XXXX]"
    m = _re.search(r"Cartão\s+\w+\s+\[[\*\s]*(\d{4})\]", texto)
    if m:
        return f"{nome} - {m.group(1)}"
    return nome


# ---------------------------------------------------------------------------
# Inferência de ano
# ---------------------------------------------------------------------------

def inferir_ano_parcelado(dia: int, mes: int, vencimento: date,
                           parcela_atual: int, parcela_total: int) -> int:
    """
    Retrocede (parcela_atual - 1) meses a partir do mês de vencimento
    para encontrar o mês/ano da transação original.
    """
    ano  = vencimento.year
    m    = vencimento.month - (parcela_atual - 1)
    while m <= 0:
        m   += 12
        ano -= 1
    # Ajusta para o mês/dia correto da transação
    if mes != m % 12 or (m % 12 == 0 and mes != 12):
        # Mês calculado difere do mês do PDF — usa mês do PDF e ajusta ano
        ano_calc = ano
        if mes > m % 12 if m % 12 != 0 else mes > 12:
            ano_calc -= 1
        return ano_calc
    return ano


def inferir_ano_avista(dia: int, mes: int, vencimento: date) -> int:
    """Para compras à vista: se mês da transação > mês do vencimento, é ano anterior."""
    if mes > vencimento.month:
        return vencimento.year - 1
    return vencimento.year


# ---------------------------------------------------------------------------
# Classificação de tipo
# ---------------------------------------------------------------------------

RE_PARCELA = re.compile(r"Parcela\s+(\d+)\s+de\s+(\d+)", re.IGNORECASE)

KEYWORDS_PAGAMENTO = ["pagamento"]
KEYWORDS_OUTROS    = ["iof", "juros", "multa"]


def classificar_tipo(descricao: str, tem_parcela: bool = False) -> str:
    desc_lower = descricao.lower()
    for kw in KEYWORDS_PAGAMENTO:
        if kw in desc_lower:
            return "Pagamento"
    for kw in KEYWORDS_OUTROS:
        if kw in desc_lower:
            return "Outros"
    return "Compra parcelada" if tem_parcela else "Compra à vista"


# ---------------------------------------------------------------------------
# Parsing dos lançamentos
# ---------------------------------------------------------------------------

RE_LANCAMENTO = re.compile(
    r"^(\d{2}/\d{2})\s+(.+?)\s+R\$\s*([\d.]+,\d{2})\s*$",
    re.MULTILINE,
)

LINHAS_IGNORAR = {"total", "data movimentações valor em r$", "movimentações"}


def parsear_lancamentos(texto: str, vencimento: date, caminho_pdf: Path) -> list:
    lancamentos = []
    vistos = set()

    for m in RE_LANCAMENTO.finditer(texto):
        data_str, descricao, valor_str = m.groups()
        descricao = descricao.strip()

        if descricao.lower() in LINHAS_IGNORAR:
            continue

        dia, mes = map(int, data_str.split("/"))
        valor    = float(valor_str.replace(".", "").replace(",", "."))

        mp = RE_PARCELA.search(descricao)
        if mp:
            parcela_atual = int(mp.group(1))
            parcela_total = int(mp.group(2))
            parcela    = f"{parcela_atual:02d}/{parcela_total:02d}"
            desc_clean = RE_PARCELA.sub("", descricao).strip()
            tem_parcela = True
        else:
            parcela    = None
            desc_clean = descricao.strip()
            tem_parcela = False

        chave = m.start()
        if chave in vistos:
            continue
        vistos.add(chave)

        tipo_final = classificar_tipo(desc_clean, tem_parcela)
        # Créditos positivos, débitos negativos
        if tipo_final == "Pagamento":
            valor_final = valor
        else:
            valor_final = -valor

        lancamentos.append({
            "arquivo":        caminho_pdf.name,
            "vencimento":     vencimento.strftime("%d/%m/%Y"),
            "descricao":      desc_clean,
            "parcela":        parcela,
            "valor":          valor_final,
            "tipo":           tipo_final,
            "titular_cartao": "",
        })

    return lancamentos


# ---------------------------------------------------------------------------
# Validação de total
# ---------------------------------------------------------------------------

def validar_total(lancamentos: list, texto: str):
    m = re.search(r"^Total\s+R\$\s*([\d.]+,\d{2})", texto, re.MULTILINE)
    if not m:
        return False, 0.0, 0.0
    total_pdf  = float(m.group(1).replace(".", "").replace(",", "."))
    # Soma absoluta dos débitos para comparar com total do PDF
    tipos_debito = {"Compra parcelada", "Compra à vista", "Outros"}
    total_calc = sum(abs(l["valor"]) for l in lancamentos if l["tipo"] in tipos_debito)
    return abs(total_pdf - total_calc) < 0.05, total_pdf, total_calc


# ---------------------------------------------------------------------------
# Processar pasta
# ---------------------------------------------------------------------------

def processar_pasta(pasta: Path) -> list:
    pdfs_vistos = {}
    for p in pasta.glob("*"):
        if p.suffix.lower() == ".pdf":
            pdfs_vistos[p.name.lower()] = p

    pdfs = sorted(pdfs_vistos.values())

    if not pdfs:
        raise FileNotFoundError("Nenhum PDF encontrado na pasta.")

    todos_lancamentos = []

    for pdf_path in pdfs:
        texto          = extrair_texto_pdf(pdf_path)
        venc           = extrair_vencimento(texto)
        titular_cartao = extrair_titular_cartao(texto)
        lancamentos    = parsear_lancamentos(texto, venc, pdf_path)
        ok, total_pdf, total_calc = validar_total(lancamentos, texto)

        if not ok:
            raise ValueError(
                f"{pdf_path.name}: divergência R$ {abs(total_pdf - total_calc):.2f} "
                f"(PDF={total_pdf:.2f} / calculado={total_calc:.2f})"
            )

        for l in lancamentos:
            l["titular_cartao"] = titular_cartao
        todos_lancamentos.extend(lancamentos)

    return todos_lancamentos


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--cliente",   required=True)
    parser.add_argument("--password",  default="")
    args = parser.parse_args()

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
    id_lote = f"MP-{ts.strftime('%Y%m%d-%H%M%S')}"

    try:
        lancamentos = processar_pasta(input_path)
        envelope = {
            "id_lote":            id_lote,
            "data_processamento": ts.isoformat(timespec="seconds"),
            "emissor":            "mercadopago",
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
"""
Extrator de Fatura - Cartão de Crédito Mercado Pago
Chamado pelo Excel via VBA (CLI: --input-dir, --cliente).
"""

import re
import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

from pdf_decrypt import descriptografar


# ---------------------------------------------------------------------------
# Extração de texto do PDF
# ---------------------------------------------------------------------------

def extrair_texto_pdf(source) -> str:
    texto = []
    with pdfplumber.open(source) as pdf:
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


def extrair_titular_cartao(texto: str) -> tuple:
    """Retorna (titular, final_cartao) extraídos do PDF."""
    nome = "Desconhecido"
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha:
            nome = linha
            break
    m = re.search(r"Cartão\s+\w+\s+\[[\*\s]*(\d{4})\]", texto)
    if m:
        return nome, m.group(1)
    return nome, ""


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
    return ano if mes <= mes_ref else ano - 1


def inferir_ano_avista(dia: int, mes: int, vencimento: date) -> int:
    return vencimento.year - 1 if mes > vencimento.month else vencimento.year


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
            parcela_num   = int(mp.group(1))
            qtde_parcelas = int(mp.group(2))
            desc_clean    = RE_PARCELA.sub("", descricao).strip()
            tem_parcela   = True
        else:
            parcela_num   = 0
            qtde_parcelas = 0
            desc_clean    = descricao.strip()
            tem_parcela   = False

        chave = m.start()
        if chave in vistos:
            continue
        vistos.add(chave)

        try:
            if tem_parcela:
                ano = inferir_ano_parcelado(dia, mes, vencimento, parcela_num)
            else:
                ano = inferir_ano_avista(dia, mes, vencimento)
            data_compra = date(ano, mes, dia).strftime("%d/%m/%Y")
        except Exception:
            data_compra = None

        tipo_final  = classificar_tipo(desc_clean, tem_parcela)
        valor_final = valor if tipo_final == "Pagamento" else -valor

        if qtde_parcelas > 0:
            descricao_adaptada = f"{desc_clean} parc {parcela_num}/{qtde_parcelas}"
        else:
            descricao_adaptada = desc_clean
        if data_compra:
            descricao_adaptada += f" {data_compra}"

        lancamentos.append({
            "arquivo":            caminho_pdf.name,
            "titular":            "",
            "final_cartao":       "",
            "tipo":               tipo_final,
            "data_compra":        data_compra,
            "descricao":          desc_clean,
            "parcela_num":        parcela_num,
            "qtde_parcelas":      qtde_parcelas,
            "vencimento":         vencimento.strftime("%d/%m/%Y"),
            "descricao_adaptada": descricao_adaptada,
            "valor":              valor_final,
        })

    return lancamentos


# ---------------------------------------------------------------------------
# Validação de total
# ---------------------------------------------------------------------------

def validar_total(lancamentos: list, texto: str):
    m = re.search(r"^Total\s+R\$\s*([\d.]+,\d{2})", texto, re.MULTILINE)
    if not m:
        return False, 0.0, 0.0
    total_pdf    = float(m.group(1).replace(".", "").replace(",", "."))
    tipos_debito = {"Compra parcelada", "Compra à vista", "Outros"}
    total_calc   = sum(abs(l["valor"]) for l in lancamentos if l["tipo"] in tipos_debito)
    return abs(total_pdf - total_calc) < 0.05, total_pdf, total_calc


# ---------------------------------------------------------------------------
# Processar arquivo / pasta
# ---------------------------------------------------------------------------

def processar_arquivo(pdf_path: Path, source) -> list:
    """Processa um PDF já aberto (source = Path ou BytesIO). Chamado pelo extrator.py."""
    texto                 = extrair_texto_pdf(source)
    venc                  = extrair_vencimento(texto)
    titular, final_cartao = extrair_titular_cartao(texto)
    lancamentos           = parsear_lancamentos(texto, venc, pdf_path)
    ok, total_pdf, total_calc = validar_total(lancamentos, texto)
    if not ok:
        raise ValueError(
            f"{pdf_path.name}: divergencia R$ {abs(total_pdf - total_calc):.2f} "
            f"(PDF={total_pdf:.2f} / calculado={total_calc:.2f})"
        )
    for l in lancamentos:
        l["titular"]      = titular
        l["final_cartao"] = final_cartao
        l["emissor"]      = "mercadopago"
    return lancamentos


def processar_pasta(pasta: Path, password: str = "") -> list:
    pdfs_vistos = {}
    for p in pasta.glob("*"):
        if p.suffix.lower() == ".pdf":
            pdfs_vistos[p.name.lower()] = p

    pdfs = sorted(pdfs_vistos.values())
    if not pdfs:
        raise FileNotFoundError("Nenhum PDF encontrado na pasta.")

    todos_lancamentos = []
    for pdf_path in pdfs:
        source = descriptografar(pdf_path, password)
        todos_lancamentos.extend(processar_arquivo(pdf_path, source))

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
    id_lote = f"MP-{ts.strftime('%Y%m%d-%H%M%S')}"

    try:
        lancamentos = processar_pasta(input_path, password)
        envelope = {
            "id_lote":            id_lote,
            "data_processamento": ts.isoformat(timespec="seconds"),
            "emissor":            "mercadopago",
            "cliente":            args.cliente,
            "avisos":             avisos,
            "lancamentos": [
                {
                    "cliente":            args.cliente,
                    "id_lote":            id_lote,
                    "arquivo":            l["arquivo"],
                    "titular":            l["titular"],
                    "final_cartao":       l["final_cartao"],
                    "tipo":               l["tipo"],
                    "data_compra":        l["data_compra"],
                    "descricao":          l["descricao"],
                    "parcela_num":        l["parcela_num"],
                    "qtde_parcelas":      l["qtde_parcelas"],
                    "vencimento":         l["vencimento"],
                    "descricao_adaptada": l["descricao_adaptada"],
                    "valor":              l["valor"],
                }
                for l in lancamentos
            ],
        }
        print(json.dumps(envelope, ensure_ascii=False))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

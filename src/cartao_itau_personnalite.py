"""
Extrator de Fatura - Cartão Itaú Personnalitê
Fingerprint: ["40044828", "ITAUUNIBANCOHOLDING"] | id_lote prefix: ITP-
Suporta múltiplos titulares (cartões adicionais por bloco intermediário).
"""

import re
import sys
import io
import json
import argparse
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

log = get_logger("extratores.itau_personnalite")

X_DIV = 355

RE_DATA  = re.compile(r"^\d{2}/\d{2}$")
RE_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
RE_PARC  = re.compile(r"^(\d{2})/(\d{2})$")
RE_TITUL = re.compile(r"Titular\s+([A-Z][A-Z\s]+)")
RE_CART  = re.compile(r"Cart[aã]o\s+\d{4}\.XXXX\.XXXX\.(\d{4})")
RE_VENC  = re.compile(r"Vencimento\s+(\d{2}/\d{2}/\d{4})")
RE_BLOCO = re.compile(r"\(final(\d{4})\)$")
RE_TOTAL = re.compile(r"L?Totaldoslançamentosatuais\s+([\d.]+,\d{2})")

SECAO_LANCAMENTOS = "Lançamentos:comprasesaques"
SECAO_PROXIMAS    = "Comprasparceladas-próximasfaturas"


# ---------------------------------------------------------------------------
# Utilitários de extração de texto
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


def extrair_titular_cartao(texto: str) -> tuple:
    nome = "Desconhecido"
    final = ""
    m = RE_TITUL.search(texto)
    if m:
        nome = m.group(1).split("\n")[0].strip()
    m2 = RE_CART.search(texto)
    if m2:
        final = m2.group(1)
    return nome, final


# ---------------------------------------------------------------------------
# Extração de segmento (uma coluna de uma página)
# ---------------------------------------------------------------------------

def extrair_segmento(page, col: str) -> list:
    words = page.extract_words(keep_blank_chars=False, x_tolerance=1, y_tolerance=3)
    words_col = [w for w in words if (w["x0"] < X_DIV if col == "e" else w["x0"] >= X_DIV)]
    linhas = defaultdict(list)
    for w in words_col:
        y = round(w["top"] / 4) * 4
        linhas[y].append(w)

    resultado = []
    for y in sorted(linhas.keys()):
        tokens = [w["text"] for w in sorted(linhas[y], key=lambda w: w["x0"])]
        # Reagrupar '-' isolado seguido de número: '-' '0,02' → '-0,02'
        merged = []
        i = 0
        while i < len(tokens):
            if tokens[i] == "-" and i + 1 < len(tokens) and re.match(r"^\d[\d.]*,\d{2}$", tokens[i + 1]):
                merged.append("-" + tokens[i + 1])
                i += 2
            else:
                merged.append(tokens[i])
                i += 1
        resultado.append((y, merged))
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

def classificar_tipo(descricao: str, tem_parcela: bool, valor: float) -> str:
    if "pagamento" in descricao.lower():
        return "Pagamento"
    if valor < 0:
        return "Ajuste"
    return "Compra parcelada" if tem_parcela else "Compra à vista"


# ---------------------------------------------------------------------------
# Helpers de detecção de linhas especiais
# ---------------------------------------------------------------------------

def _is_bloco_header(tokens: list) -> tuple:
    """(True, final_4d) se a linha é cabeçalho de bloco multi-titular.

    Com x_tolerance=1, o token pode estar fragmentado em múltiplas partes
    (ex: ['MONICA', 'D', 'KULLIAN', '(final', '6318)']). A detecção usa
    o texto unido sem espaços, que reconstitui o padrão original.
    """
    txt = "".join(tokens)
    if txt.startswith("Lançamentos"):
        return False, ""
    m = RE_BLOCO.search(txt)
    if m and not RE_DATA.match(txt) and not RE_VALOR.match(txt):
        return True, m.group(1)
    return False, ""


def _is_subtotal(tokens: list) -> bool:
    """True se é linha de subtotal de bloco (Lançamentosnocartão...)."""
    return "".join(tokens).startswith("Lançamentosnocar")


# ---------------------------------------------------------------------------
# Parser de lançamentos
# ---------------------------------------------------------------------------

def parsear_lancamentos(
    caminho: Path,
    vencimento: date,
    titular_inicial: str,
    final_inicial: str,
    source=None,
) -> list:
    lancamentos   = []
    ignorar_col_d = False
    titular_ativo = titular_inicial
    final_ativo   = final_inicial

    with pdfplumber.open(source if source is not None else caminho) as pdf:
        for pg_idx, page in enumerate(pdf.pages):
            for col in ("e", "d"):
                if col == "d" and ignorar_col_d:
                    continue

                segmento = extrair_segmento(page, col)

                for _y, tokens in segmento:
                    # txt_det: tokens unidos sem espaço — usado para detecção de padrões
                    # (reconstitui os tokens originais de x_tolerance=3)
                    txt_det = "".join(tokens)

                    # Seção "próximas faturas" — aparece em ambas as colunas na pág. de transição
                    if txt_det == SECAO_PROXIMAS:
                        ignorar_col_d = True
                        log.debug("Proximas faturas | pg=%d col=%s | parando coluna", pg_idx, col)
                        break  # para esta coluna; col_d bloqueada nas páginas seguintes

                    # Header de seção de lançamentos — pular linha
                    if txt_det == SECAO_LANCAMENTOS:
                        continue

                    # Subtotal de bloco — pular
                    if _is_subtotal(tokens):
                        continue

                    # Linha do total de validação — pular (processada em validar_total)
                    if "Totaldoslançamentos" in txt_det:
                        continue

                    # Cabeçalho de bloco multi-titular: "NOME(finalNNNN)"
                    is_bloco, final_bloco = _is_bloco_header(tokens)
                    if is_bloco:
                        # Extrair nome com espaços: tokens antes do fragmento "(final..."
                        idx = next((i for i, t in enumerate(tokens) if "(final" in t), None)
                        titular_ativo = " ".join(tokens[:idx]).strip() if idx else txt_det.split("(final")[0]
                        final_ativo   = final_bloco
                        log.debug("Titular | pg=%d | nome=%s | final=%s", pg_idx, titular_ativo, final_ativo)
                        continue

                    # Lançamento: requer pelo menos DATA + DESCRICAO + VALOR
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

                    tipo = classificar_tipo(descricao, tem_parcela, valor)

                    # Ajuste e Pagamento são créditos → positivos; compras são débitos → negativos
                    if tipo in ("Ajuste", "Pagamento"):
                        valor_final = abs(valor)
                    else:
                        valor_final = -abs(valor)

                    if qtde_parcelas > 0:
                        desc_adaptada = f"{descricao} parc {parcela_num}/{qtde_parcelas}"
                    else:
                        desc_adaptada = descricao
                    if data_compra:
                        desc_adaptada += f" {data_compra}"

                    lancamentos.append({
                        "arquivo":            caminho.name,
                        "titular":            titular_ativo,
                        "final_cartao":       final_ativo,
                        "tipo":               tipo,
                        "data_compra":        data_compra,
                        "descricao":          descricao,
                        "parcela_num":        parcela_num,
                        "qtde_parcelas":      qtde_parcelas,
                        "vencimento":         vencimento.strftime("%d/%m/%Y"),
                        "descricao_adaptada": desc_adaptada,
                        "valor":              valor_final,
                    })

    return lancamentos


# ---------------------------------------------------------------------------
# Validação de total
# ---------------------------------------------------------------------------

def validar_total(lancamentos: list, texto: str):
    m = RE_TOTAL.search(texto)
    if not m:
        log.warning("'Totaldoslançamentosatuais' não encontrado — validação ignorada")
        return None, 0.0, 0.0

    total_pdf  = float(m.group(1).replace(".", "").replace(",", "."))
    # Compras são negativas, ajustes são positivos → -sum = compras - ajustes = líquido debitado
    total_calc = -sum(l["valor"] for l in lancamentos if l["tipo"] not in {"Pagamento"})
    diff       = abs(total_pdf - total_calc)

    if diff > 0.10:
        log.warning("Divergência | pdf=%.2f | calc=%.2f | diff=%.2f", total_pdf, total_calc, diff)

    return diff <= 0.10, total_pdf, total_calc


# ---------------------------------------------------------------------------
# Processar arquivo / pasta
# ---------------------------------------------------------------------------

def processar_arquivo(pdf_path: Path, source) -> list:
    log.info("Iniciando extração | arquivo=%s", pdf_path.name)
    texto = extrair_texto_pdf(source)
    if isinstance(source, io.BytesIO):
        source.seek(0)

    venc                  = extrair_vencimento(texto)
    titular, final_cartao = extrair_titular_cartao(texto)
    lancamentos           = parsear_lancamentos(pdf_path, venc, titular, final_cartao, source)
    ok, total_pdf, total_calc = validar_total(lancamentos, texto)

    if ok is False:
        log.error("Divergência crítica | arquivo=%s | pdf=%.2f | calc=%.2f | diff=%.2f",
                  pdf_path.name, total_pdf, total_calc, abs(total_pdf - total_calc))
        raise ValueError(
            f"{pdf_path.name}: divergência R$ {abs(total_pdf - total_calc):.2f} "
            f"(PDF={total_pdf:.2f} / calculado={total_calc:.2f})"
        )

    log.info("Extração OK | arquivo=%s | lançamentos=%d | total=%.2f",
             pdf_path.name, len(lancamentos), total_pdf if total_pdf else 0.0)
    return lancamentos


def processar_pasta(pasta: Path, password: str = "") -> list:
    pdfs = sorted(p for p in pasta.glob("*") if p.suffix.lower() == ".pdf")
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
    id_lote = f"ITP-{ts.strftime('%Y%m%d-%H%M%S')}"

    try:
        lancamentos = processar_pasta(input_path, password)
        envelope = {
            "id_lote":            id_lote,
            "data_processamento": ts.isoformat(timespec="seconds"),
            "emissor":            "itau_personnalite",
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
        sys.stdout.write(json.dumps(envelope, ensure_ascii=True))
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

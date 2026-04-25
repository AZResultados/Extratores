"""
Extrator de Fatura - Cartão de Crédito Mercado Pago
Abre janela para seleção de pasta, processa PDFs e grava resultado em JSON.
Chamado pelo Excel via VBA.
"""

import re
import sys
import json
import io
from datetime import date, datetime
from pathlib import Path

# Força UTF-8 no stdout (evita CP850/CP1252 no cmd do Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None


# ---------------------------------------------------------------------------
# Seleção de pasta via janela
# ---------------------------------------------------------------------------

def selecionar_pasta() -> Path:
    if tk is None:
        sys.exit("ERRO: tkinter não disponível.")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    pasta = filedialog.askdirectory(title="Selecione a pasta com os PDFs do Mercado Pago")
    root.destroy()
    if not pasta:
        sys.exit("Nenhuma pasta selecionada.")
    return Path(pasta)


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


def classificar_tipo(descricao: str) -> str:
    desc_lower = descricao.lower()
    for kw in KEYWORDS_PAGAMENTO:
        if kw in desc_lower:
            return "Pagamento"
    for kw in KEYWORDS_OUTROS:
        if kw in desc_lower:
            return "Outros"
    if RE_PARCELA.search(descricao):
        return "Compra parcelada"
    return "Compra à vista"


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

        # Inferência de ano e montagem de descrição final
        mp = RE_PARCELA.search(descricao)
        if mp:
            parcela_atual = int(mp.group(1))
            parcela_total = int(mp.group(2))

            # Retrocede (parcela_atual - 1) meses
            ano  = vencimento.year
            mes_orig = vencimento.month - (parcela_atual - 1)
            while mes_orig <= 0:
                mes_orig += 12
                ano      -= 1

            # Se o mês calculado diverge do mês do PDF, usa mês do PDF e ajusta ano
            if mes_orig % 12 == 0:
                mes_ref = 12
            else:
                mes_ref = mes_orig % 12

            if mes != mes_ref:
                ano_final = ano if mes < mes_ref else ano - 1
            else:
                ano_final = ano

            data_transacao = f"{dia:02d}/{mes:02d}/{ano_final}"
            # Substitui "Parcela X de Y" por "Parcela X de Y DD/MM/AAAA"
            desc_final = RE_PARCELA.sub(
                f"Parcela {parcela_atual} de {parcela_total} {data_transacao}",
                descricao,
            ).strip()
        else:
            ano_final      = inferir_ano_avista(dia, mes, vencimento)
            data_transacao = f"{dia:02d}/{mes:02d}/{ano_final}"
            desc_final     = f"{descricao} {data_transacao}"

        chave = m.start()
        if chave in vistos:
            continue
        vistos.add(chave)

        tipo_final = classificar_tipo(desc_final)
        # Créditos positivos, débitos negativos
        if tipo_final == "Pagamento":
            valor_final = valor
        else:
            valor_final = -valor

        lancamentos.append({
            "arquivo_origem":  str(caminho_pdf),
            "data_vencimento": vencimento.strftime("%Y-%m-%d"),
            "descricao":       desc_final,
            "valor_brl":       valor_final,
            "tipo":            tipo_final,
            "titular_cartao":  "",
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
    total_calc = sum(abs(l["valor_brl"]) for l in lancamentos if l["tipo"] in tipos_debito)
    return abs(total_pdf - total_calc) < 0.05, total_pdf, total_calc


# ---------------------------------------------------------------------------
# Processar pasta
# ---------------------------------------------------------------------------

def processar_pasta(pasta: Path) -> dict:
    pdfs_vistos = {}
    for p in pasta.glob("*"):
        if p.suffix.lower() == ".pdf":
            pdfs_vistos[p.name.lower()] = p

    pdfs = sorted(pdfs_vistos.values())

    if not pdfs:
        return {"lancamentos": [], "erros": ["Nenhum PDF encontrado na pasta."]}

    todos_lancamentos = []
    erros = []

    for pdf_path in pdfs:
        try:
            texto          = extrair_texto_pdf(pdf_path)
            venc           = extrair_vencimento(texto)
            titular_cartao = extrair_titular_cartao(texto)
            lancamentos    = parsear_lancamentos(texto, venc, pdf_path)
            ok, total_pdf, total_calc = validar_total(lancamentos, texto)

            if not ok:
                erros.append(
                    f"{pdf_path.name}: divergência R$ {abs(total_pdf - total_calc):.2f} "
                    f"(PDF={total_pdf:.2f} / calculado={total_calc:.2f})"
                )

            for l in lancamentos:
                l["titular_cartao"] = titular_cartao
            todos_lancamentos.extend(lancamentos)

        except Exception as e:
            erros.append(f"{pdf_path.name}: {e}")

    return {"lancamentos": todos_lancamentos, "erros": erros}


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Aceita pasta como argumento (chamada VBA) ou abre janela (execução direta)
    if len(sys.argv) >= 2:
        pasta = Path(sys.argv[1])
        if not pasta.exists():
            print(json.dumps({"erro": f"Pasta não encontrada: {pasta}"}))
            sys.exit(1)
    else:
        pasta = selecionar_pasta()

    resultado = processar_pasta(pasta)
    print(json.dumps(resultado, ensure_ascii=False))
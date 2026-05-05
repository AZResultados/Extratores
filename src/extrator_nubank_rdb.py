"""
Extrator de Extrato Nubank RDB (Caixinhas PJ) - Resgate Imediato
"""

import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    sys.exit("ERRO: instale pdfplumber -> pip install pdfplumber")

from logger import get_logger

log = get_logger("extratores.nubank_rdb")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RE_V = r'R\$\s*([\d.]+,\d{2})'


def _v(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


# ---------------------------------------------------------------------------
# Extração de texto
# ---------------------------------------------------------------------------

def extrair_texto_pdf(source) -> str:
    partes = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------

def extrair_titular(texto: str) -> str:
    """Razão social da empresa beneficiária (linha após o marcador de cabeçalho)."""
    m = re.search(
        r'Empresa benefici\xe1ria dos rendimentos\s+CNPJ\s*\n([^\n]+)',
        texto,
    )
    if not m:
        raise ValueError("Raz\xe3o social da empresa benefici\xe1ria n\xe3o encontrada no PDF.")
    linha = m.group(1).strip()
    # Remove CNPJ XX.XXX.XXX/XXXX-XX do final da linha
    return re.sub(r'\s+\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\s*$', '', linha).strip()


def extrair_saldo_final(texto: str) -> float:
    """Saldo no final do período informado no PDF."""
    m = re.search(r'Saldo no final do per\xedodo:\s*R\$\s*([\d.]+,\d{2})', texto)
    if not m:
        raise ValueError("Saldo no final do per\xedodo n\xe3o encontrado no PDF.")
    return _v(m.group(1))


# ---------------------------------------------------------------------------
# Patterns de linha
# ---------------------------------------------------------------------------

# Resgate: DD/MM/YYYY Resgate R$ bruto R$ IR R$ IOF R$ saldo_liq
_RE_RESGATE = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+Resgate\s+'
    + _RE_V + r'\s+' + _RE_V + r'\s+' + _RE_V + r'\s+' + _RE_V,
    re.MULTILINE,
)

# Compra por aplicação / data sem descrição inline — 4 valores
_RE_DATA_4V = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+'
    + _RE_V + r'\s+' + _RE_V + r'\s+' + _RE_V + r'\s+' + _RE_V
)

# Rendimento — apenas 1 valor
_RE_DATA_1V = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+' + _RE_V + r'\s*$'
)


# ---------------------------------------------------------------------------
# Parsing dos lançamentos
# ---------------------------------------------------------------------------

def _lcto(pdf_path, titular, data_fmt, descricao, tipo, valor):
    return {
        "arquivo":            pdf_path.name,
        "titular":            titular,
        "final_cartao":       None,
        "tipo":               tipo,
        "data_compra":        data_fmt,
        "descricao":          descricao,
        "parcela_num":        0,
        "qtde_parcelas":      0,
        "vencimento":         data_fmt,
        "descricao_adaptada": descricao,
        "valor":              valor,
    }


def parsear_lancamentos(texto: str, pdf_path: Path) -> list:
    titular = extrair_titular(texto)
    lancamentos = []
    pendente = None  # "aplicacao" | "rendimento"

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # Detecta início de movimentação multilinha
        if linha == "Compra por":
            pendente = "aplicacao"
            continue
        if linha == "Rendimento at\xe9":
            pendente = "rendimento"
            continue

        # Resgate (tudo em uma linha)
        m = _RE_RESGATE.match(linha)
        if m:
            data_str, vb, ir, iof, _sl = m.groups()
            data_fmt = datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            vb_f  = _v(vb)
            ir_f  = _v(ir)
            iof_f = _v(iof)
            lancamentos.append(_lcto(
                pdf_path, titular, data_fmt, "Resgate RDB", "Sa\xedda", -vb_f
            ))
            if ir_f > 0:
                lancamentos.append(_lcto(
                    pdf_path, titular, data_fmt, "IR s/ Resgate RDB", "Sa\xedda", -ir_f
                ))
            if iof_f > 0:
                lancamentos.append(_lcto(
                    pdf_path, titular, data_fmt, "IOF s/ Resgate RDB", "Sa\xedda", -iof_f
                ))
            pendente = None
            continue

        # Linhas de data sem descrição inline — aguarda contexto pendente
        if not re.match(r'^\d{2}/\d{2}/\d{4}', linha):
            continue

        if pendente == "aplicacao":
            m2 = _RE_DATA_4V.match(linha)
            if m2:
                data_str, vb, _ir, _iof, _sl = m2.groups()
                data_fmt = datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%Y")
                lancamentos.append(_lcto(
                    pdf_path, titular, data_fmt,
                    "Aplica\xe7\xe3o RDB", "Entrada", _v(vb)
                ))
                pendente = None
            continue

        if pendente == "rendimento":
            m3 = _RE_DATA_1V.match(linha)
            if m3:
                data_str, rv = m3.groups()
                data_fmt = datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%Y")
                lancamentos.append(_lcto(
                    pdf_path, titular, data_fmt, "Rendimento RDB", "Entrada", _v(rv)
                ))
                pendente = None
            continue

    return lancamentos


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def validar(lancamentos: list, texto: str):
    """
    Para cada resgate: confirma valor_bruto - IR - IOF = saldo_líquido (tolerância R$ 0,10).
    Essa é a única verificação aritmética possível a partir do extrato —
    o saldo_final do período é o saldo da conta investida e não pode ser
    recalculado a partir das movimentações do período sem o saldo de abertura.
    """
    saldo_final = extrair_saldo_final(texto)

    for m in _RE_RESGATE.finditer(texto):
        data_str, vb, ir, iof, sl = m.groups()
        vb_f  = _v(vb)
        ir_f  = _v(ir)
        iof_f = _v(iof)
        sl_f  = _v(sl)
        esperado = vb_f - ir_f - iof_f
        diff = abs(esperado - sl_f)
        if diff > 0.10:
            raise ValueError(
                f"Diverg\xeancia de integridade no resgate de {data_str}: "
                f"bruto {vb_f:.2f} - IR {ir_f:.2f} - IOF {iof_f:.2f} "
                f"= {esperado:.2f} ≠ saldo_l\xedq {sl_f:.2f} "
                f"(diff={diff:.2f} > R$ 0,10)"
            )

    log.info(
        "Valida\xe7\xe3o OK | saldo_final_pdf=R$%.2f | lancamentos=%d",
        saldo_final, len(lancamentos),
    )


# ---------------------------------------------------------------------------
# Processar arquivo / pasta
# ---------------------------------------------------------------------------

def processar_arquivo(pdf_path: Path, source) -> list:
    """Processa um PDF já aberto (source = Path ou BytesIO). Chamado pelo extrator.py."""
    log.info("Iniciando extra\xe7\xe3o | arquivo=%s", pdf_path.name)
    texto = extrair_texto_pdf(source)
    lancamentos = parsear_lancamentos(texto, pdf_path)
    validar(lancamentos, texto)
    log.info("Extra\xe7\xe3o OK | arquivo=%s | lancamentos=%d",
             pdf_path.name, len(lancamentos))
    return lancamentos


# ---------------------------------------------------------------------------
# Ponto de entrada standalone
# ---------------------------------------------------------------------------

def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--cliente",   required=True)
    parser.add_argument("--password",  default="")  # ignorado: PDF sem senha
    args = parser.parse_args(args)

    avisos     = []
    input_path = Path(args.input_dir)

    if not input_path.exists():
        print(f"ERRO: Pasta n\xe3o encontrada: {input_path}", file=sys.stderr)
        sys.exit(1)

    partes_caminho = [p.name for p in input_path.parents] + [input_path.name]
    if args.cliente not in partes_caminho:
        avisos.append(
            f"AVISO: '{args.cliente}' n\xe3o encontrado no caminho '{input_path}'. "
            f"Verifique isolamento de dados."
        )

    pdfs = sorted(p for p in input_path.glob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        print("ERRO: Nenhum PDF encontrado na pasta.", file=sys.stderr)
        sys.exit(1)

    ts      = datetime.now()
    id_lote = f"NRD-{ts.strftime('%Y%m%d-%H%M%S')}"
    todos_lancamentos = []

    try:
        for pdf_path in pdfs:
            todos_lancamentos.extend(processar_arquivo(pdf_path, pdf_path))
    except Exception as e:
        log.error("Falha | erro=%s", str(e))
        print(str(e), file=sys.stderr)
        sys.exit(1)

    envelope = {
        "id_lote":            id_lote,
        "data_processamento": ts.isoformat(timespec="seconds"),
        "emissor":            "nubank_rdb",
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
            for l in todos_lancamentos
        ],
    }
    sys.stdout.write(json.dumps(envelope, ensure_ascii=True))


if __name__ == "__main__":
    main()

"""
Testes do extrator Samsung Itaú — 8 testes mínimos (T1–T8).
T8 requer PDF real em OneDrive + senha cadastrada via setup_senha.py (TASK-S09).
"""

import io
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import cartao_samsung as sm
from helpers import CAMPOS_LANCAMENTO, TIPOS_VALIDOS

# ---------------------------------------------------------------------------
# Fixtures de texto sintético (sem PDF real)
# ---------------------------------------------------------------------------

TEXTO_PG1_JAN = (
    "Vencimento: 27/01/2026\n"
    "Titular JAMES WILLIAM DA COSTA\n"
    "Cart\xe3o 4101.XXXX.XXXX.4121\n"
)

TEXTO_FEV = (
    "Vencimento: 27/02/2026\n"
    "Encargos (Financiamento + morat\xf3rio) 38,72\n"
    "Titular JAMES WILLIAM DA COSTA\n"
    "Cart\xe3o 4101.XXXX.XXXX.4121\n"
    "Total dos lan\xe7amentos atuais 1.023,24\n"
    "Repasse de IOF em R$ 3,66\n"
)

# ---------------------------------------------------------------------------
# Fixture de PDF real (T8) — skip se indisponível ou senha não cadastrada
# ---------------------------------------------------------------------------

_PDF_DIR = Path(
    "C:/Users/jwcos/OneDrive - Azmid/Documentos/Clientes/JW/Extratos/Cartão - Samsung"
)
_PDF_JAN = _PDF_DIR / "Fatura_VISA_102020861664_27-01-2026.pdf"


@pytest.fixture
def samsung_jan_source():
    if not _PDF_JAN.exists():
        pytest.skip("PDF Samsung 01/2026 não encontrado (OneDrive não montado)")
    try:
        import db_senha
        senhas = db_senha.get_todas_senhas("JW")
    except Exception:
        senhas = []
    if not senhas:
        pytest.skip("Senha Samsung não cadastrada — execute setup_senha.py (TASK-S09)")
    import pikepdf
    for senha in senhas:
        try:
            with pikepdf.open(_PDF_JAN, password=senha) as pdf:
                buf = io.BytesIO()
                pdf.save(buf)
                buf.seek(0)
            return _PDF_JAN, buf
        except Exception:
            continue
    pytest.skip("Nenhuma senha cadastrada abre o PDF Samsung 01/2026")


# ---------------------------------------------------------------------------
# Helpers de mock para parsear_lancamentos
# ---------------------------------------------------------------------------

def _make_words(rows: list) -> list:
    words = []
    for row in rows:
        for text, x0, top in row:
            words.append({"text": text, "x0": x0, "top": top})
    return words


def _patch_pdfplumber(mocker, rows_por_pagina: list):
    pages = []
    for rows in rows_por_pagina:
        page = MagicMock()
        page.extract_words.return_value = _make_words(rows)
        page.extract_text.return_value = ""
        pages.append(page)

    fake_pdf = MagicMock()
    fake_pdf.__enter__ = lambda s: s
    fake_pdf.__exit__ = MagicMock(return_value=False)
    fake_pdf.pages = pages
    mocker.patch("cartao_samsung.pdfplumber.open", return_value=fake_pdf)


# ---------------------------------------------------------------------------
# T1 — extrair_vencimento → date(2026, 1, 27)
# ---------------------------------------------------------------------------

class TestExtrairVencimento:
    def test_jan_2026(self):
        assert sm.extrair_vencimento(TEXTO_PG1_JAN) == date(2026, 1, 27)

    def test_raise_se_nao_encontrado(self):
        with pytest.raises(ValueError):
            sm.extrair_vencimento("sem data aqui")


# ---------------------------------------------------------------------------
# T2 e T3 — extrair_titular
# ---------------------------------------------------------------------------

class TestExtrairTitular:
    def test_nome_e_final_cartao(self):
        nome, final = sm.extrair_titular(TEXTO_PG1_JAN)
        assert nome == "JAMES WILLIAM DA COSTA"
        assert final == "4121"

    def test_sem_residual_nc_no_nome(self):
        nome, _ = sm.extrair_titular(TEXTO_PG1_JAN)
        assert "\nC" not in nome

    def test_defaults_quando_nao_encontrado(self):
        assert sm.extrair_titular("") == ("Desconhecido", "")


# ---------------------------------------------------------------------------
# T4 — Parcela via penúltimo token (NAT*Natura Pag 02/06)
# ---------------------------------------------------------------------------

class TestParcelaViaTokens:
    def test_nat_natura_pag_02_06(self, mocker):
        rows = [
            [
                ("Lançamentos:", 10, 100), ("compras", 90, 100),
                ("e", 140, 100), ("saques", 155, 100),
            ],
            [
                ("15/02", 10, 120), ("NAT*Natura", 60, 120),
                ("Pag", 140, 120), ("02/06", 180, 120), ("53,34", 250, 120),
            ],
        ]
        _patch_pdfplumber(mocker, [rows])

        result = sm.parsear_lancamentos(
            Path("fake.pdf"), date(2026, 2, 27), "JOAO", "1234"
        )
        assert len(result) == 1
        l = result[0]
        assert l["parcela_num"] == 2
        assert l["qtde_parcelas"] == 6
        assert l["descricao"] == "NAT*Natura Pag"


# ---------------------------------------------------------------------------
# T5 — Seção "próximas faturas" não gera lançamentos
# ---------------------------------------------------------------------------

class TestSecaoProximasIgnorada:
    def test_nenhum_lancamento_da_secao_proximas(self, mocker):
        rows = [
            [
                ("Compras", 10, 100), ("parceladas", 70, 100), ("-", 140, 100),
                ("pr\xf3ximas", 150, 100), ("faturas", 210, 100),
            ],
            [
                ("15/03", 10, 120), ("LOJA", 70, 120),
                ("XYZ", 120, 120), ("50,00", 250, 120),
            ],
        ]
        _patch_pdfplumber(mocker, [rows])

        result = sm.parsear_lancamentos(
            Path("fake.pdf"), date(2026, 3, 27), "JOAO", "1234"
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# T6 — classificar_tipo com secao_atual
# ---------------------------------------------------------------------------

class TestClassificarTipo:
    def test_pagamento_com_secao_pagamentos(self):
        assert sm.classificar_tipo("PAGAMENTO PIX", False, "pagamentos") == "Pagamento"

    def test_iof_retorna_outros(self):
        assert sm.classificar_tipo("IOF OPERACAO", False, "lancamentos") == "Outros"

    def test_parcelado(self):
        assert sm.classificar_tipo("NAT*Natura Pag", True, "lancamentos") == "Compra parcelada"

    def test_avista(self):
        assert sm.classificar_tipo("correio*Correios CelSAO", False, "lancamentos") == "Compra \xe0 vista"


# ---------------------------------------------------------------------------
# T7 — validar_total amostra 02/2026 (encargos + repasse IOF)
# ---------------------------------------------------------------------------

class TestValidarTotal:
    def _lancamentos_fev(self):
        itens = [
            ("Compra \xe0 vista", -915.00),
            ("Outros",            -104.58),
            ("Outros",             -38.72),
            ("Pagamento",        1139.85),
        ]
        return [{"tipo": t, "valor": v} for t, v in itens]

    def test_usa_total_atuais_e_compensa_encargos_e_repasse(self):
        lcts = self._lancamentos_fev()
        ok, total_pdf, total_calc = sm.validar_total(lcts, TEXTO_FEV)
        assert ok
        assert abs(total_pdf - 1023.24) < 0.01

    def test_sem_label_retorna_false(self):
        ok, _, _ = sm.validar_total([], "sem totais aqui")
        assert not ok


# ---------------------------------------------------------------------------
# T8 — processar_arquivo amostra 01/2026 (PDF real, zero disco)
# ---------------------------------------------------------------------------

class TestProcessarArquivoReal:
    def test_jan_2026_17_lancamentos_zero_disco(self, samsung_jan_source, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf_path, buf = samsung_jan_source

        result = sm.processar_arquivo(pdf_path, buf)

        assert len(result) == 17
        tipos_debito = {"Compra parcelada", "Compra \xe0 vista", "Outros"}
        total = sum(abs(l["valor"]) for l in result if l["tipo"] in tipos_debito)
        assert abs(total - 1139.85) < 0.10
        assert list(tmp_path.iterdir()) == []

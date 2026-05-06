"""
Testes para cartao_itau_personnalite:
parsear_lancamentos com páginas fake (mock pdfplumber) e validar_total com texto fixo.
"""
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import cartao_itau_personnalite as itp

VENC    = date(2026, 4, 15)
ARQUIVO = Path("fatura_itau.pdf")

# Posições x0 que espelham o layout real do PDF Itaú Personnalitê
X_DATA_E, X_DESC_E, X_PARC_E, X_VAL_E = 151, 178, 225, 320   # coluna esq (x0 < 355)
X_DATA_D, X_DESC_D, X_VAL_D           = 367, 394, 535          # coluna dir (x0 >= 355)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word(text, x0, top):
    return {"text": text, "x0": float(x0), "top": float(top)}


def _page(words):
    p = MagicMock()
    p.extract_words.return_value = words
    return p


def _mock_pdf(mocker, pages):
    """Substitui pdfplumber.open para retornar páginas fake."""
    ctx = MagicMock()
    ctx.__enter__.return_value = ctx
    ctx.__exit__.return_value = False
    ctx.pages = pages
    mocker.patch("cartao_itau_personnalite.pdfplumber.open", return_value=ctx)


# ---------------------------------------------------------------------------
# 1. Titular único — contagem e campos
# ---------------------------------------------------------------------------

class TestTitularUnico:
    def test_conta_lancamentos_corretamente(self, mocker):
        page = _page([
            # seção
            _word("Lançamentos:", X_DATA_E, 80), _word("compras", 200, 80),
            _word("e", 240, 80), _word("saques", 270, 80),
            # lançamento 1 — à vista
            _word("15/03", X_DATA_E, 100), _word("SUPERMERCADO", X_DESC_E, 100),
            _word("XYZ", 240, 100), _word("150,00", X_VAL_E, 100),
            # lançamento 2 — parcelado
            _word("20/03", X_DATA_E, 120), _word("LOJA", X_DESC_E, 120),
            _word("ABC", 210, 120), _word("01/06", X_PARC_E, 120),
            _word("99,90", X_VAL_E, 120),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO SILVA", "1234")
        assert len(result) == 2

    def test_schema_campos_obrigatorios(self, mocker):
        page = _page([
            _word("10/03", X_DATA_E, 100), _word("FARMACIA", X_DESC_E, 100),
            _word("80,00", X_VAL_E, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO SILVA", "1234")
        assert len(result) == 1
        l = result[0]
        campos = ["arquivo", "titular", "final_cartao", "tipo", "data_compra",
                  "descricao", "parcela_num", "qtde_parcelas", "vencimento",
                  "descricao_adaptada", "valor"]
        for campo in campos:
            assert campo in l, f"Campo ausente: {campo}"
        assert l["titular"] == "JOAO SILVA"
        assert l["final_cartao"] == "1234"
        assert l["arquivo"] == "fatura_itau.pdf"
        assert l["tipo"] == "Compra à vista"
        assert isinstance(l["valor"], float)
        assert l["valor"] < 0

    def test_parcelado_campos_corretos(self, mocker):
        page = _page([
            _word("22/12", X_DATA_E, 100), _word("LOJA", X_DESC_E, 100),
            _word("04/06", X_PARC_E, 100), _word("398,12", X_VAL_E, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        assert len(result) == 1
        l = result[0]
        assert l["tipo"] == "Compra parcelada"
        assert l["parcela_num"] == 4
        assert l["qtde_parcelas"] == 6
        assert "parc 4/6" in l["descricao_adaptada"]
        assert l["valor"] == -398.12

    def test_descricao_com_espacos_preservados(self, mocker):
        # Tokens separados pelo pdfplumber (x_tolerance=1) devem ser unidos com espaço
        page = _page([
            _word("14/01", X_DATA_E, 100),
            _word("TIMAX", X_DESC_E, 100), _word("PIEDADE", 200, 100),
            _word("90,00", X_VAL_E, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        assert result[0]["descricao"] == "TIMAX PIEDADE"


# ---------------------------------------------------------------------------
# 2. Multi-titular
# ---------------------------------------------------------------------------

class TestMultiTitular:
    def test_atualiza_titular_e_final_ao_encontrar_bloco(self, mocker):
        page = _page([
            # bloco 1: MARIA SILVA (final9999)
            _word("MARIA", X_DATA_E, 80), _word("SILVA", 165, 80),
            _word("(final", 185, 80), _word("9999)", 205, 80),
            _word("10/03", X_DATA_E, 100), _word("MERCADO", X_DESC_E, 100),
            _word("200,00", X_VAL_E, 100),
            # bloco 2: PEDRO COSTA (final8888)
            _word("PEDRO", X_DATA_E, 140), _word("COSTA", 165, 140),
            _word("(final", 185, 140), _word("8888)", 205, 140),
            _word("12/03", X_DATA_E, 160), _word("FARMACIA", X_DESC_E, 160),
            _word("50,00", X_VAL_E, 160),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "TITULAR INICIAL", "0000")
        assert len(result) == 2
        assert result[0]["titular"] == "MARIA SILVA"
        assert result[0]["final_cartao"] == "9999"
        assert result[1]["titular"] == "PEDRO COSTA"
        assert result[1]["final_cartao"] == "8888"

    def test_titular_inicial_usado_antes_do_primeiro_bloco(self, mocker):
        page = _page([
            _word("05/03", X_DATA_E, 100), _word("POSTO", X_DESC_E, 100),
            _word("100,00", X_VAL_E, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "TITULAR INICIAL", "0000")
        assert result[0]["titular"] == "TITULAR INICIAL"
        assert result[0]["final_cartao"] == "0000"


# ---------------------------------------------------------------------------
# 3. Linhas especiais
# ---------------------------------------------------------------------------

class TestLinhasEspeciais:
    def test_subtotal_de_bloco_nao_vira_lancamento(self, mocker):
        page = _page([
            _word("10/03", X_DATA_E, 100), _word("MERCADO", X_DESC_E, 100),
            _word("200,00", X_VAL_E, 100),
            # subtotal — deve ser ignorado
            _word("Lançamentosnocartão(final1234)", X_DATA_E, 120),
            _word("200,00", X_VAL_E, 120),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        assert len(result) == 1
        assert result[0]["descricao"] == "MERCADO"

    def test_ajuste_negativo_tipo_correto_e_valor_positivo(self, mocker):
        page = _page([
            _word("08/03", X_DATA_E, 100), _word("FARMACIA", X_DESC_E, 100),
            _word("-0,04", X_VAL_E, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        assert len(result) == 1
        assert result[0]["tipo"] == "Ajuste"
        assert result[0]["valor"] == pytest.approx(0.04)

    def test_secao_proximas_faturas_para_coluna_e_ignora_itens_seguintes(self, mocker):
        page = _page([
            # lançamento válido (antes da seção a ignorar)
            _word("10/03", X_DATA_E, 100), _word("MERCADO", X_DESC_E, 100),
            _word("200,00", X_VAL_E, 100),
            # header da seção "próximas faturas" na coluna esquerda
            _word("Compras", X_DATA_E, 140), _word("parceladas", 195, 140),
            _word("-", 245, 140), _word("próximas", 255, 140),
            _word("faturas", 310, 140),
            # item após a seção — NÃO deve ser capturado
            _word("20/03", X_DATA_E, 160), _word("LOJA", X_DESC_E, 160),
            _word("99,00", X_VAL_E, 160),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        assert len(result) == 1
        assert result[0]["descricao"] == "MERCADO"

    def test_coluna_dir_ignorada_apos_proximas_faturas(self, mocker):
        page = _page([
            # coluna esq: lançamento válido + header próximas
            _word("10/03", X_DATA_E, 100), _word("MERCADO", X_DESC_E, 100),
            _word("200,00", X_VAL_E, 100),
            _word("Compras", X_DATA_E, 140), _word("parceladas", 195, 140),
            _word("-", 245, 140), _word("próximas", 255, 140),
            _word("faturas", 310, 140),
            # coluna dir: item que NÃO deve ser capturado
            _word("15/03", X_DATA_D, 100), _word("LOJA", X_DESC_D, 100),
            _word("50,00", X_VAL_D, 100),
        ])
        _mock_pdf(mocker, [page])
        result = itp.parsear_lancamentos(ARQUIVO, VENC, "JOAO", "1234")
        # Só o da coluna esquerda antes do header
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 4. Validação de total
# ---------------------------------------------------------------------------

class TestValidarTotal:
    def test_total_correto_retorna_ok(self):
        lancamentos = [
            {"tipo": "Compra à vista", "valor": -100.0},
            {"tipo": "Compra à vista", "valor":  -50.0},
        ]
        ok, total_pdf, total_calc = itp.validar_total(lancamentos,
                                                       "LTotaldoslançamentosatuais 150,00")
        assert ok is True
        assert total_pdf == pytest.approx(150.0)
        assert total_calc == pytest.approx(150.0)

    def test_total_ausente_retorna_none_sem_excecao(self):
        lancamentos = [{"tipo": "Compra à vista", "valor": -100.0}]
        ok, total_pdf, total_calc = itp.validar_total(lancamentos, "sem campo de total aqui")
        assert ok is None
        assert total_pdf == 0.0

    def test_ajuste_reduz_total_calculado(self):
        lancamentos = [
            {"tipo": "Compra à vista", "valor": -100.0},
            {"tipo": "Ajuste",         "valor":   +0.04},
        ]
        # total_calc = -( -100 + 0.04 ) = 99.96
        ok, total_pdf, total_calc = itp.validar_total(lancamentos,
                                                       "LTotaldoslançamentosatuais 99,96")
        assert ok is True
        assert total_calc == pytest.approx(99.96)

    def test_divergencia_acima_010_retorna_false(self):
        lancamentos = [{"tipo": "Compra à vista", "valor": -100.0}]
        ok, total_pdf, total_calc = itp.validar_total(lancamentos,
                                                       "LTotaldoslançamentosatuais 200,00")
        assert ok is False

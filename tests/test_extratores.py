"""
Testes dos extratores: parsear_lancamentos com texto fixo (MP)
e processar_arquivo com mocks de pdfplumber (SA e MP).
Valida schema de saída dos lançamentos.
"""
from datetime import date
from pathlib import Path

import pytest

import cartao_mercadopago as mp
import cartao_santander   as sa
from helpers import CAMPOS_LANCAMENTO, TIPOS_VALIDOS, lancamento_valido


# ---------------------------------------------------------------------------
# Texto fixture para Mercado Pago (sem pdfplumber)
# ---------------------------------------------------------------------------

TEXTO_MP = """\
James William da Costa
Fatura Mercado Pago Visa
Cartão Visa [************7863]
Vencimento: 10/05/2026
Data Movimentações Valor em R$
15/04 SUPERMERCADO XYZ R$ 150,00
20/04 FARMACIA ABC R$ 89,90
Total R$ 239,90
"""

TEXTO_MP_COM_PARCELA = """\
James William da Costa
Cartão Visa [************7863]
Vencimento: 10/05/2026
Data Movimentações Valor em R$
15/02 LOJA ELETRONICOS Parcela 2 de 6 R$ 100,00
Total R$ 100,00
"""

TEXTO_MP_SEM_CARTAO = """\
James William da Costa
Vencimento: 10/05/2026
15/04 SUPERMERCADO XYZ R$ 50,00
Total R$ 50,00
"""


# ---------------------------------------------------------------------------
# Helper de validação de schema
# ---------------------------------------------------------------------------

def assert_schema(lancamento: dict):
    for campo in CAMPOS_LANCAMENTO:
        assert campo in lancamento, f"Campo ausente: {campo}"
    assert lancamento["tipo"] in TIPOS_VALIDOS
    assert isinstance(lancamento["valor"], float)
    assert isinstance(lancamento["parcela_num"], int)
    assert isinstance(lancamento["qtde_parcelas"], int)
    assert lancamento["parcela_num"] >= 0
    assert lancamento["qtde_parcelas"] >= 0


# ---------------------------------------------------------------------------
# Mercado Pago — parsear_lancamentos (função pura, sem mock)
# ---------------------------------------------------------------------------

class TestParsearLancamentosMP:
    def test_retorna_dois_lancamentos(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        assert len(resultado) == 2

    def test_schema_cada_lancamento(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        for l in resultado:
            assert_schema(l)

    def test_valores_negativos_para_debitos(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        assert all(l["valor"] < 0 for l in resultado)

    def test_descricoes_corretas(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        descricoes = {l["descricao"] for l in resultado}
        assert "SUPERMERCADO XYZ" in descricoes
        assert "FARMACIA ABC" in descricoes

    def test_data_compra_inferida(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        datas = {l["data_compra"] for l in resultado}
        assert "15/04/2026" in datas
        assert "20/04/2026" in datas

    def test_lancamento_parcelado(self):
        resultado = mp.parsear_lancamentos(
            TEXTO_MP_COM_PARCELA, date(2026, 5, 10), Path("fatura.pdf")
        )
        assert len(resultado) == 1
        l = resultado[0]
        assert l["tipo"] == "Compra parcelada"
        assert l["parcela_num"] == 2
        assert l["qtde_parcelas"] == 6
        assert "parc 2/6" in l["descricao_adaptada"]

    def test_nao_parcelado_tem_zero(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("fatura.pdf"))
        for l in resultado:
            assert l["parcela_num"] == 0
            assert l["qtde_parcelas"] == 0

    def test_arquivo_nome_correto(self):
        resultado = mp.parsear_lancamentos(TEXTO_MP, date(2026, 5, 10), Path("minha_fatura.pdf"))
        assert all(l["arquivo"] == "minha_fatura.pdf" for l in resultado)

    def test_final_cartao_sem_numero_retorna_vazio(self):
        # Quando padrão do cartão não casa, final_cartao deve ser ""
        resultado = mp.parsear_lancamentos(
            TEXTO_MP_SEM_CARTAO, date(2026, 5, 10), Path("fatura.pdf")
        )
        assert all(l["final_cartao"] == "" for l in resultado)


# ---------------------------------------------------------------------------
# Mercado Pago — processar_arquivo (mock extrair_texto_pdf)
# ---------------------------------------------------------------------------

class TestProcessarArquivoMP:
    def test_schema_completo(self, mocker):
        mocker.patch("cartao_mercadopago.extrair_texto_pdf", return_value=TEXTO_MP)
        resultado = mp.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))
        assert len(resultado) == 2
        for l in resultado:
            assert_schema(l)

    def test_divergencia_levanta_value_error(self, mocker):
        mocker.patch("cartao_mercadopago.extrair_texto_pdf", return_value=TEXTO_MP)
        mocker.patch("cartao_mercadopago.validar_total", return_value=(False, 300.0, 239.90))
        with pytest.raises(ValueError, match="divergencia"):
            mp.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))

    def test_titular_preenchido(self, mocker):
        mocker.patch("cartao_mercadopago.extrair_texto_pdf", return_value=TEXTO_MP)
        resultado = mp.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))
        assert all(l["titular"] != "" for l in resultado)

    def test_final_cartao_preenchido(self, mocker):
        mocker.patch("cartao_mercadopago.extrair_texto_pdf", return_value=TEXTO_MP)
        resultado = mp.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))
        assert all(l["final_cartao"] == "7863" for l in resultado)


# ---------------------------------------------------------------------------
# Santander — classificar_tipo
# ---------------------------------------------------------------------------

class TestClassificarTipoSantander:
    def test_pagamento_por_keyword(self):
        assert sa.classificar_tipo("deb autom de fatura", False) == "Pagamento"
        assert sa.classificar_tipo("PAGAMENTO RECEBIDO", False) == "Pagamento"

    def test_outros_por_keyword(self):
        assert sa.classificar_tipo("IOF OPERACAO", False) == "Outros"
        assert sa.classificar_tipo("JUROS ROTATIVO", False) == "Outros"
        assert sa.classificar_tipo("ANUIDADE CARTAO", False) == "Outros"

    def test_compra_avista(self):
        assert sa.classificar_tipo("MERCADO XYZ", False) == "Compra à vista"

    def test_compra_parcelada(self):
        assert sa.classificar_tipo("LOJA ABC", True) == "Compra parcelada"

    def test_ajuste_nao_existe_mais(self):
        # "Ajuste" foi removido do domínio — não deve ser retornado
        resultado = sa.classificar_tipo("credito pequeno", False)
        assert resultado != "Ajuste"
        assert resultado in TIPOS_VALIDOS


# ---------------------------------------------------------------------------
# Santander — inferir_ano_avista e inferir_ano_parcelado
# ---------------------------------------------------------------------------

class TestInferirAnoSantander:
    def test_avista_mesmo_mes(self):
        assert sa.inferir_ano_avista(5, date(2026, 5, 10)) == 2026

    def test_avista_mes_anterior(self):
        assert sa.inferir_ano_avista(3, date(2026, 5, 10)) == 2026

    def test_avista_mes_posterior_ano_anterior(self):
        assert sa.inferir_ano_avista(8, date(2026, 5, 10)) == 2025

    def test_parcelado_mes_referencia(self):
        # venc=maio/2026, parcela 2/6: mes_ref = 5-(2-1) = 4 (abril)
        assert sa.inferir_ano_parcelado(4, date(2026, 5, 10), 2) == 2026

    def test_parcelado_mes_anterior_mesmo_ano(self):
        # mes=3 < mes_ref=4 → mesmo ano
        assert sa.inferir_ano_parcelado(3, date(2026, 5, 10), 2) == 2026

    def test_parcelado_mes_posterior_ano_anterior(self):
        # mes=11 > mes_ref=4 → ano anterior
        assert sa.inferir_ano_parcelado(11, date(2026, 5, 10), 2) == 2025

    def test_parcelado_wrap_dezembro(self):
        # venc=jan/2026, parcela 2/6: mes_ref = 1-(2-1) = 0 → 12 (dez/2025)
        assert sa.inferir_ano_parcelado(12, date(2026, 1, 10), 2) == 2025


# ---------------------------------------------------------------------------
# Santander — processar_arquivo (mocks totais)
# ---------------------------------------------------------------------------

class TestProcessarArquivoSA:
    def test_schema_completo(self, mocker):
        l = lancamento_valido()
        mocker.patch("cartao_santander.extrair_texto_pdf",
                     return_value="Vencimento 10/04/2026")
        mocker.patch("cartao_santander.parsear_lancamentos", return_value=[l])
        mocker.patch("cartao_santander.validar_total", return_value=(True, 50.0, 50.0))

        resultado = sa.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))
        assert len(resultado) == 1
        for r in resultado:
            assert_schema(r)

    def test_divergencia_levanta_value_error(self, mocker):
        mocker.patch("cartao_santander.extrair_texto_pdf",
                     return_value="Vencimento 10/04/2026")
        mocker.patch("cartao_santander.parsear_lancamentos",
                     return_value=[lancamento_valido()])
        mocker.patch("cartao_santander.validar_total",
                     return_value=(False, 100.0, 50.0))

        with pytest.raises(ValueError, match="divergencia"):
            sa.processar_arquivo(Path("fatura.pdf"), Path("fatura.pdf"))

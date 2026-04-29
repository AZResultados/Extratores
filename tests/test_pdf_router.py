"""Testes para pdf_router: detecção de emissor e roteamento com mocks."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pdf_router


class TestDetectarEmissor:
    def test_mercadopago_por_marcador_principal(self):
        assert pdf_router.detectar_emissor("Mercado Pago fatura") == "mercadopago"

    def test_mercadopago_variante(self):
        assert pdf_router.detectar_emissor("MercadoPago Visa") == "mercadopago"

    def test_santander_maiusculo(self):
        assert pdf_router.detectar_emissor("SANTANDER Elite Mastercard") == "santander"

    def test_santander_mixed_case(self):
        assert pdf_router.detectar_emissor("Santander cartao") == "santander"

    def test_emissor_desconhecido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Emissor nao reconhecido"):
            pdf_router.detectar_emissor("Banco do Brasil fatura")

    def test_texto_vazio_levanta_value_error(self):
        with pytest.raises(ValueError):
            pdf_router.detectar_emissor("")


class TestRotear:
    def test_sem_senha_mercadopago(self, mocker):
        mocker.patch("pdf_router._ler_primeira_pagina",
                     return_value="Mercado Pago fatura Vencimento 2026")
        emissor, source = pdf_router.rotear(Path("fake.pdf"), "cliente")
        assert emissor == "mercadopago"
        assert source == Path("fake.pdf")

    def test_sem_senha_santander(self, mocker):
        mocker.patch("pdf_router._ler_primeira_pagina",
                     return_value="SANTANDER Elite Mastercard")
        emissor, source = pdf_router.rotear(Path("fake.pdf"), "cliente")
        assert emissor == "santander"

    def test_com_senha_abre_corretamente(self, mocker):
        mock_source = MagicMock()
        mocker.patch("pdf_router._ler_primeira_pagina",
                     side_effect=[Exception("encrypted"), "SANTANDER fatura"])
        mocker.patch("pdf_router.get_todas_senhas", return_value=["12345"])
        mocker.patch("pdf_router.tentar_descriptografar", return_value=mock_source)

        emissor, source = pdf_router.rotear(Path("fake.pdf"), "cliente")
        assert emissor == "santander"
        assert source is mock_source

    def test_senha_errada_tenta_proxima(self, mocker):
        mock_source = MagicMock()
        mocker.patch("pdf_router._ler_primeira_pagina",
                     side_effect=[
                         Exception("encrypted"),   # sem senha
                         Exception("wrong key"),   # senha1
                         "Mercado Pago fatura",    # senha2 ok
                     ])
        mocker.patch("pdf_router.get_todas_senhas", return_value=["errada", "certa"])
        mocker.patch("pdf_router.tentar_descriptografar", return_value=mock_source)

        emissor, _ = pdf_router.rotear(Path("fake.pdf"), "cliente")
        assert emissor == "mercadopago"

    def test_sem_senhas_cadastradas_levanta(self, mocker):
        mocker.patch("pdf_router._ler_primeira_pagina",
                     side_effect=Exception("encrypted"))
        mocker.patch("pdf_router.get_todas_senhas", return_value=[])

        with pytest.raises(ValueError, match="nao foi possivel"):
            pdf_router.rotear(Path("fake.pdf"), "cliente")

    def test_todas_senhas_erradas_levanta(self, mocker):
        mocker.patch("pdf_router._ler_primeira_pagina",
                     side_effect=Exception("encrypted"))
        mocker.patch("pdf_router.get_todas_senhas", return_value=["s1", "s2"])
        mocker.patch("pdf_router.tentar_descriptografar",
                     side_effect=Exception("bad password"))

        with pytest.raises(ValueError, match="nao foi possivel"):
            pdf_router.rotear(Path("fake.pdf"), "cliente")

    def test_texto_vazio_sem_senha_tenta_com_senhas(self, mocker):
        # Abre sem senha mas extrai texto vazio → deve tentar com senhas
        mock_source = MagicMock()
        mocker.patch("pdf_router._ler_primeira_pagina",
                     side_effect=["", "Mercado Pago fatura"])
        mocker.patch("pdf_router.get_todas_senhas", return_value=["senha"])
        mocker.patch("pdf_router.tentar_descriptografar", return_value=mock_source)

        emissor, _ = pdf_router.rotear(Path("fake.pdf"), "cliente")
        assert emissor == "mercadopago"

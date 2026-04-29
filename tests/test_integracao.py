"""
Testes de integração:
  - subprocess: valida exit codes e mensagens de erro
  - main() in-process: valida schema do envelope JSON com mocks
"""
import json
import sys
import subprocess
from pathlib import Path

import pytest

import extrator
from helpers import lancamento_valido, CAMPOS_LANCAMENTO

PYTHON   = sys.executable
EXTRATOR = str(Path(__file__).parent.parent / "src" / "extrator.py")


# ---------------------------------------------------------------------------
# Subprocess — exit codes e mensagens de erro
# ---------------------------------------------------------------------------

class TestSubprocessExitCodes:
    def test_sem_args_exit_nao_zero(self):
        r = subprocess.run([PYTHON, EXTRATOR], capture_output=True)
        assert r.returncode != 0

    def test_pasta_nao_encontrada_exit_1(self, tmp_path):
        r = subprocess.run(
            [PYTHON, EXTRATOR,
             "--cliente", "TESTE",
             "--input-dir", str(tmp_path / "nao_existe")],
            capture_output=True, text=True,
        )
        assert r.returncode == 1
        assert "ERRO" in r.stderr

    def test_pasta_sem_pdfs_exit_1(self, tmp_path):
        r = subprocess.run(
            [PYTHON, EXTRATOR,
             "--cliente", "TESTE",
             "--input-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1
        assert "PDF" in r.stderr


# ---------------------------------------------------------------------------
# main() in-process — schema do envelope JSON
# ---------------------------------------------------------------------------

class TestEnvelopeSchema:
    def _setup_client_dir(self, tmp_path, nome="CLIENTE-TEST"):
        d = tmp_path / nome
        d.mkdir()
        (d / "fatura.pdf").write_bytes(b"%PDF-1.4 fake")
        return d

    def _patch_extrator(self, monkeypatch, lancamentos):
        """Patcha rotear e EXTRATORES no namespace de extrator.py."""
        monkeypatch.setattr(extrator, "rotear",
                            lambda pdf_path, cliente: ("mercadopago", pdf_path))
        monkeypatch.setattr(extrator, "EXTRATORES",
                            {"mercadopago": lambda pdf_path, source: lancamentos})

    def test_envelope_campos_obrigatorios(self, tmp_path, monkeypatch, capsys):
        client_dir = self._setup_client_dir(tmp_path)
        self._patch_extrator(monkeypatch, [lancamento_valido()])

        extrator.main(["--cliente", "CLIENTE-TEST",
                       "--input-dir", str(client_dir)])

        out = capsys.readouterr().out
        envelope = json.loads(out)

        assert "id_lote"            in envelope
        assert "data_processamento" in envelope
        assert "emissor"            in envelope
        assert "cliente"            in envelope
        assert "avisos"             in envelope
        assert "lancamentos"        in envelope

    def test_envelope_cliente_correto(self, tmp_path, monkeypatch, capsys):
        client_dir = self._setup_client_dir(tmp_path)
        self._patch_extrator(monkeypatch, [lancamento_valido()])

        extrator.main(["--cliente", "CLIENTE-TEST",
                       "--input-dir", str(client_dir)])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["cliente"] == "CLIENTE-TEST"

    def test_lancamento_tem_todos_os_campos(self, tmp_path, monkeypatch, capsys):
        client_dir = self._setup_client_dir(tmp_path)
        self._patch_extrator(monkeypatch, [lancamento_valido()])

        extrator.main(["--cliente", "CLIENTE-TEST",
                       "--input-dir", str(client_dir)])

        envelope = json.loads(capsys.readouterr().out)
        assert len(envelope["lancamentos"]) == 1
        l = envelope["lancamentos"][0]
        for campo in CAMPOS_LANCAMENTO + ["cliente", "id_lote"]:
            assert campo in l, f"Campo ausente no lancamento: {campo}"

    def test_id_lote_formato(self, tmp_path, monkeypatch, capsys):
        import re
        client_dir = self._setup_client_dir(tmp_path)
        self._patch_extrator(monkeypatch, [lancamento_valido()])

        extrator.main(["--cliente", "CLIENTE-TEST",
                       "--input-dir", str(client_dir)])

        envelope = json.loads(capsys.readouterr().out)
        assert re.match(r"^(MP|SA|EXT)-\d{8}-\d{6}$", envelope["id_lote"])

    def test_aviso_cliente_fora_do_caminho(self, tmp_path, monkeypatch, capsys):
        other_dir = tmp_path / "outra_pasta"
        other_dir.mkdir()
        (other_dir / "fatura.pdf").write_bytes(b"%PDF-1.4 fake")
        self._patch_extrator(monkeypatch, [lancamento_valido()])

        extrator.main(["--cliente", "CLIENTE-TEST",
                       "--input-dir", str(other_dir)])

        envelope = json.loads(capsys.readouterr().out)
        assert len(envelope["avisos"]) > 0
        assert any("AVISO" in av for av in envelope["avisos"])

    def test_falha_no_extrator_exit_1(self, tmp_path, monkeypatch):
        client_dir = self._setup_client_dir(tmp_path)
        monkeypatch.setattr(extrator, "rotear",
                            lambda p, c: ("mercadopago", p))
        monkeypatch.setattr(extrator, "EXTRATORES",
                            {"mercadopago": lambda p, s: (_ for _ in ()).throw(
                                ValueError("erro de teste"))})

        with pytest.raises(SystemExit) as exc:
            extrator.main(["--cliente", "CLIENTE-TEST",
                           "--input-dir", str(client_dir)])
        assert exc.value.code == 1

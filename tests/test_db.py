"""Testes de CRUD para db_senha e db_cliente com SQLite :memory: (via tmp_path)."""
import pytest
import db_senha
import db_cliente


class TestDbSenha:
    def test_cadastrar_nova_senha(self, patch_db_senha):
        assert db_senha.set_senha("cliente1", "s1") is True

    def test_duplicata_ignorada(self, patch_db_senha):
        db_senha.set_senha("c1", "s1")
        assert db_senha.set_senha("c1", "s1") is False

    def test_get_todas_senhas(self, patch_db_senha):
        db_senha.set_senha("c1", "s1")
        db_senha.set_senha("c1", "s2")
        senhas = db_senha.get_todas_senhas("c1")
        assert len(senhas) == 2
        assert set(senhas) == {"s1", "s2"}

    def test_cliente_sem_senhas(self, patch_db_senha):
        assert db_senha.get_todas_senhas("nao_existe") == []

    def test_isolamento_entre_clientes(self, patch_db_senha):
        db_senha.set_senha("c1", "s1")
        db_senha.set_senha("c2", "s2")
        assert db_senha.get_todas_senhas("c1") == ["s1"]
        assert db_senha.get_todas_senhas("c2") == ["s2"]

    def test_remover_senha(self, patch_db_senha):
        db_senha.set_senha("c1", "s1")
        db_senha.remover_senha("c1", "s1")
        assert db_senha.get_todas_senhas("c1") == []

    def test_remover_senha_inexistente_nao_falha(self, patch_db_senha):
        db_senha.remover_senha("c1", "nao_existe")  # não deve levantar

    def test_listar_sem_senhas(self, patch_db_senha):
        assert db_senha.listar() == []

    def test_listar_com_senhas(self, patch_db_senha):
        db_senha.set_senha("c1", "s1")
        db_senha.set_senha("c1", "s2")
        db_senha.set_senha("c2", "s3")
        rows = db_senha.listar()
        assert len(rows) == 2
        totais = {r[0]: r[1] for r in rows}
        assert totais["c1"] == 2
        assert totais["c2"] == 1


class TestDbCliente:
    def test_cadastrar_cliente(self, patch_db_cliente):
        db_cliente.set_cliente("ACME", "/path/acme")
        c = db_cliente.get_cliente("ACME")
        assert c == {"nome": "ACME", "base_dir": "/path/acme"}

    def test_upsert_atualiza_base_dir(self, patch_db_cliente):
        db_cliente.set_cliente("ACME", "/v1")
        db_cliente.set_cliente("ACME", "/v2")
        assert db_cliente.get_cliente("ACME")["base_dir"] == "/v2"

    def test_cliente_inexistente_retorna_none(self, patch_db_cliente):
        assert db_cliente.get_cliente("nao_existe") is None

    def test_listar_clientes_ordenado(self, patch_db_cliente):
        db_cliente.set_cliente("B", "/b")
        db_cliente.set_cliente("A", "/a")
        lista = db_cliente.listar_clientes()
        assert lista[0] == ("A", "/a")
        assert lista[1] == ("B", "/b")

    def test_remover_cliente(self, patch_db_cliente):
        db_cliente.set_cliente("X", "/x")
        db_cliente.remover_cliente("X")
        assert db_cliente.get_cliente("X") is None

    def test_remover_cliente_inexistente_nao_falha(self, patch_db_cliente):
        db_cliente.remover_cliente("nao_existe")

    def test_listar_vazio(self, patch_db_cliente):
        assert db_cliente.listar_clientes() == []

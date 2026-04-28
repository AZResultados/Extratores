"""
Gerenciamento de senhas de PDF no banco local.
Banco: ~/.extratores/dados.db (override via env var EXTRATORES_DB)

Uso interativo (terminal):
  python src/setup_senha.py add    <cliente>           # le senha via getpass
  python src/setup_senha.py remove <cliente>           # le senha via getpass
  python src/setup_senha.py list

Uso programatico (VBA via stdin):
  python src/setup_senha.py add    <cliente> --stdin   # le senha da primeira linha do stdin
  python src/setup_senha.py remove <cliente> --stdin
"""

import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db_senha import set_senha, remover_senha, listar, DB_PATH


def ler_senha(prompt: str, via_stdin: bool) -> str:
    if via_stdin:
        linha = sys.stdin.readline().strip()
        if not linha:
            sys.exit("ERRO: senha nao recebida via stdin.")
        return linha
    return getpass.getpass(prompt)


def cmd_add(args):
    if not args:
        sys.exit("Uso: setup_senha.py add <cliente> [--stdin]")
    cliente   = args[0].strip()
    via_stdin = "--stdin" in args
    senha = ler_senha(f"Senha do PDF para '{cliente}': ", via_stdin)
    if not senha:
        sys.exit("ERRO: senha nao pode ser vazia.")
    adicionada = set_senha(cliente, senha)
    if adicionada:
        print(f"Senha cadastrada para '{cliente}'.")
    else:
        print(f"Senha ja existente para '{cliente}'. Nenhuma alteracao.")


def cmd_remove(args):
    if not args:
        sys.exit("Uso: setup_senha.py remove <cliente> [--stdin]")
    cliente   = args[0].strip()
    via_stdin = "--stdin" in args
    senha = ler_senha(f"Senha a remover para '{cliente}': ", via_stdin)
    remover_senha(cliente, senha)
    print(f"Senha removida para '{cliente}' (se existia).")


def cmd_list():
    rows = listar()
    if not rows:
        print("Nenhuma senha cadastrada.")
        return
    print(f"\n{'Cliente':<30} Senhas cadastradas")
    print("-" * 50)
    for cliente, total in rows:
        print(f"{cliente:<30} {total}")
    print()


CMDS = {"add": cmd_add, "remove": cmd_remove, "list": cmd_list}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    else:
        CMDS[cmd](sys.argv[2:])

"""
Gerenciamento de clientes no banco local.
Banco: ~/.extratores/dados.db (override via env var EXTRATORES_DB)

Uso:
  python src/setup_cliente.py add    <nome> <base_dir>
  python src/setup_cliente.py remove <nome>
  python src/setup_cliente.py list                     # saida: nome|base_dir por linha
  python src/setup_cliente.py get    <nome>            # saida: base_dir

Exemplo:
  python src/setup_cliente.py add "CLIENTE-A" "C:\\input\\CLIENTE-A"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db_cliente import set_cliente, get_cliente, listar_clientes, remover_cliente, DB_PATH


def cmd_add(args):
    if len(args) < 2:
        sys.exit("Uso: setup_cliente.py add <nome> <base_dir>")
    nome     = args[0].strip()
    base_dir = args[1].strip()
    if not Path(base_dir).exists():
        print(f"AVISO: pasta nao encontrada: {base_dir}", file=sys.stderr)
    set_cliente(nome, base_dir)
    print(f"Cliente cadastrado: {nome}")
    print(f"Pasta raiz: {base_dir}")


def cmd_remove(args):
    if not args:
        sys.exit("Uso: setup_cliente.py remove <nome>")
    remover_cliente(args[0].strip())
    print(f"Cliente removido: {args[0].strip()}")


def cmd_list():
    """Saida parseaval pelo VBA: nome|base_dir por linha."""
    clientes = listar_clientes()
    if not clientes:
        print("VAZIO")
        return
    for nome, base_dir in clientes:
        print(f"{nome}|{base_dir}")


def cmd_get(args):
    """Retorna apenas o base_dir do cliente — usado pelo VBA apos selecao."""
    if not args:
        sys.exit("Uso: setup_cliente.py get <nome>")
    cliente = get_cliente(args[0].strip())
    if not cliente:
        sys.exit(f"Cliente nao encontrado: {args[0].strip()}")
    print(cliente["base_dir"])


CMDS = {"add": cmd_add, "remove": cmd_remove, "list": cmd_list, "get": cmd_get}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    else:
        CMDS[cmd](sys.argv[2:])

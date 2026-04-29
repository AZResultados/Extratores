"""
Ponto de entrada unico — detecta emissor por PDF e roteia para o extrator correto.
Uso: python extrator.py --input-dir <path> --cliente <nome>
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from logger import get_logger
from pdf_router import rotear
import cartao_mercadopago as mp
import cartao_santander   as sa

log = get_logger("extratores.extrator")

# Registro de extratores — adicionar nova entrada ao incluir novo emissor
EXTRATORES = {
    "mercadopago": mp.processar_arquivo,
    "santander":   sa.processar_arquivo,
}

PREFIXOS_LOTE = {
    "mercadopago": "MP",
    "santander":   "SA",
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--cliente",   required=True)
    args = parser.parse_args()

    log.info("Iniciando | cliente=%s | pasta=%s", args.cliente, args.input_dir)

    avisos     = []
    input_path = Path(args.input_dir)

    if not input_path.exists():
        print(f"ERRO: Pasta nao encontrada: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Verifica se o nome do cliente aparece em algum nivel do caminho
    partes_caminho = [p.name for p in input_path.parents] + [input_path.name]
    if args.cliente not in partes_caminho:
        avisos.append(
            f"AVISO: '{args.cliente}' nao encontrado no caminho '{input_path}'. "
            f"Verifique isolamento de dados."
        )

    pdfs = sorted(p for p in input_path.glob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        print("ERRO: Nenhum PDF encontrado na pasta.", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now()
    todos_lancamentos = []
    emissores_vistos  = set()

    try:
        for pdf_path in pdfs:
            emissor, source = rotear(pdf_path, args.cliente)
            processar = EXTRATORES.get(emissor)
            if not processar:
                raise ValueError(f"Extrator nao implementado para emissor: {emissor}")
            lancamentos = processar(pdf_path, source)
            log.info("PDF processado | arquivo=%s | emissor=%s | lancamentos=%d",
                     pdf_path.name, emissor, len(lancamentos))
            emissores_vistos.add(emissor)
            todos_lancamentos.extend(lancamentos)

    except Exception as e:
        log.error("Falha no processamento | cliente=%s | erro=%s", args.cliente, str(e))
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if len(emissores_vistos) == 1:
        emissor_envelope = emissores_vistos.pop()
        prefixo = PREFIXOS_LOTE.get(emissor_envelope, "EXT")
    else:
        emissor_envelope = "multi"
        prefixo = "EXT"

    id_lote = f"{prefixo}-{ts.strftime('%Y%m%d-%H%M%S')}"
    log.info("Lote concluido | cliente=%s | total=%d | lote=%s",
             args.cliente, len(todos_lancamentos), id_lote)

    envelope = {
        "id_lote":            id_lote,
        "data_processamento": ts.isoformat(timespec="seconds"),
        "emissor":            emissor_envelope,
        "cliente":            args.cliente,
        "avisos":             avisos,
        "lancamentos": [
            {"cliente": args.cliente, "id_lote": id_lote, **l}
            for l in todos_lancamentos
        ],
    }
    print(json.dumps(envelope, ensure_ascii=False))

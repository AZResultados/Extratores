"""Constantes e factories compartilhadas pelos testes."""

CAMPOS_LANCAMENTO = [
    "arquivo", "titular", "final_cartao", "tipo",
    "data_compra", "descricao", "parcela_num", "qtde_parcelas",
    "vencimento", "descricao_adaptada", "valor",
]

TIPOS_VALIDOS = {"Compra à vista", "Compra parcelada", "Pagamento", "Outros"}


def lancamento_valido(arquivo="fatura.pdf", tipo="Compra à vista", valor=-50.0,
                      parcela_num=0, qtde_parcelas=0):
    """Retorna dict de lançamento com todos os campos obrigatórios."""
    return {
        "arquivo":            arquivo,
        "titular":            "JOAO SILVA",
        "final_cartao":       "1234",
        "tipo":               tipo,
        "data_compra":        "15/03/2026",
        "descricao":          "MERCADO X",
        "parcela_num":        parcela_num,
        "qtde_parcelas":      qtde_parcelas,
        "vencimento":         "10/04/2026",
        "descricao_adaptada": "MERCADO X 15/03/2026",
        "valor":              valor,
    }

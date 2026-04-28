# Extratores — AZ Resultados

Automatiza a consolidação de faturas de cartão de crédito (PDF) em dados estruturados para análise financeira B2B.

## Status

MVP funcional. Dois extratores em produção: Mercado Pago e Santander.

## Estrutura

```
src/
  cartao_mercadopago.py   — extrator Mercado Pago Visa
  cartao_santander.py     — extrator Santander Elite Mastercard
vba/
  ModComum.bas            — orquestrador VBA (ProcessarExtrator)
  ModMP.bas               — botão Mercado Pago
  ModSantander.bas        — botão Santander
docs/
  Requiriments_*.md       — regras de negócio (BR-01 a BR-08)
  SnapShot_Tecnico_*.md   — estado atual do código e gaps documentados
  Checkpoint_*.md         — decisões de arquitetura acordadas
requirements.txt          — dependências Python
```

## Stack

- Python 3.13.7 + virtualenv
- pdfplumber — extração de texto de PDF
- pikepdf — descriptografia de PDF protegido por senha
- python-dateutil — cálculo retroativo de datas de parcelas
- Excel 365 + VBA — interface de operação e destino dos dados

## Instalação

```powershell
cd C:\Dev\projetos\Extratores
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

1. Abrir `Extratores.xlsm` (localizado em OneDrive\Documentos\Automações\)
2. Clicar no botão do extrator desejado
3. Selecionar a pasta com os PDFs (já descriptografados para o Santander)
4. Dados são gravados na aba `LctosTratados` — modo sobrescrita

## PDFs protegidos por senha (Santander)

Senha de abertura = CPF/CNPJ do titular do cartão.
Descriptografar manualmente com pikepdf antes de processar:

```python
import pikepdf
pikepdf.open("fatura.pdf", password="00000000000").save("Livre-fatura.pdf")
```

## Saída — aba LctosTratados

| Coluna | Conteúdo |
|---|---|
| Arquivo Origem | Caminho absoluto do PDF fonte |
| Data Vencimento | Data da fatura (dd/mm/yyyy) |
| Descrição | Lançamento + parcela + data da compra |
| Valor (R$) | Numérico com sinal (débitos negativos) |
| Tipo | Pagamento / Compra parcelada / Compra à vista / Outros / Ajuste |
| Titular - Cartão | NOME TITULAR - XXXX (4 últimos dígitos) |

## Emissores suportados

| Emissor | Script | Observação |
|---|---|---|
| Mercado Pago Visa | cartao_mercadopago.py | PDF sem senha |
| Santander Elite Mastercard | cartao_santander.py | PDF requer descriptografia prévia |

## Gaps conhecidos (backlog pós-MVP)

- G1: sem campo Cliente — isolamento por cliente depende de disciplina do operador
- G2: pikepdf não integrado aos scripts — etapa manual
- G3: sem ID_Lote — rollback de lotes com erro não é rastreável
- G5: credenciais em texto claro na aba Senhas do Excel (OneDrive)

## Requisitos de negócio

Ver `docs/Requiriments_*.md` — regras BR-01 a BR-08.

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
3. Informar pasta de entrada no formato `input/NOME_CLIENTE/`
4. Dados são gravados na aba `LctosTratados` — **modo append acumulativo**

## PDFs protegidos por senha (Santander)

Senha de abertura = CPF/CNPJ do titular do cartão.
Integração in-memory via pikepdf (arg `--password`) — sem arquivo descriptografado em disco.

## Saída — aba LctosTratados

| Col | Campo | Conteúdo |
|-----|-------|----------|
| A | Cliente | Nome do cliente (arg --cliente) |
| B | ID_Lote | Identificador do lote: `{EMISSOR}-{AAAAMMDD}-{HHMMSS}` |
| C | Arquivo Origem | Nome do arquivo PDF (sem caminho absoluto) |
| D | Data Vencimento | Data serial Excel (dd/mm/yyyy) |
| E | Descrição | Nome do estabelecimento (sem parcela embutida) |
| F | Parcela | Ex: "02/06" ou vazio se não parcelado |
| G | Valor (R$) | Numérico com sinal (débitos negativos) |
| H | Tipo | Pagamento / Compra parcelada / Compra à vista / Outros / Ajuste |
| I | Titular - Cartão | NOME TITULAR - XXXX (4 últimos dígitos) |

**Rollback de lote:** deletar todas as linhas onde Col B = ID_Lote do lote a reverter.

## Emissores suportados

| Emissor | Script | Observação |
|---|---|---|
| Mercado Pago Visa | cartao_mercadopago.py | PDF sem senha |
| Santander Elite Mastercard | cartao_santander.py | PDF requer descriptografia prévia |

## Gaps conhecidos (backlog pós-MVP)

- G2: pikepdf não integrado aos scripts — etapa ainda manual (TASK-03)
- G5: credenciais em texto claro na aba Senhas do Excel (OneDrive) — conforme BR-08 para MVP; mitigação obrigatória antes de distribuição a terceiros

> G1 (campo Cliente) e G3 (ID_Lote) resolvidos no design v1.5 — implementação pendente nas TASKs.

## Requisitos de negócio

Ver `docs/Requiriments_*.md` — regras BR-01 a BR-08.

## Convenção de nomenclatura de arquivos

Arquivos versionados seguem o padrão: `nome_AAAAMMDD_HHMM`

- `AAAAMMDD` = data de geração
- `HHMM` = horário de geração (24h) — **não é número de versão**

Exemplo: `Checkpoint_Sinc_20260428_0444.md` = gerado em 28/04/2026 às 04:44.

---

## ⚠️ Regras de segurança para contribuidores

Este repositório é **público**. Todo o histórico de commits é visível permanentemente.

**Nunca incluir em commits, mensagens de commit ou arquivos versionados:**
- Nomes de clientes da AZ Resultados
- CPF, CNPJ ou qualquer dado pessoal
- Senhas de PDF ou credenciais de qualquer natureza
- Dados financeiros reais de clientes

**Antes de commitar, verificar:**
- O conteúdo dos arquivos modificados não contém dados sensíveis
- A mensagem do commit é genérica e descritiva — sem referência a clientes ou operações específicas
- Arquivos de configuração local (aba Senhas, Config) nunca são adicionados ao repositório

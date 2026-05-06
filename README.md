# Extratores — AZ Resultados

Automatiza a consolidação de faturas de cartão de crédito (PDF) em dados estruturados para análise financeira B2B.

## Status

MVP v1.7 funcional. Cinco emissores suportados: Mercado Pago, Santander, Samsung Itaú, Itaú Personnalitê e NuBank RDB.

## Estrutura

```
src/
  extrator.py                    — entry point único de produção
  pdf_router.py                  — detecta emissor e roteia para o extrator correto
  pdf_decrypt.py                 — descriptografia in-memory (pikepdf, zero disco)
  logger.py                      — logging centralizado (RotatingFileHandler)
  cartao_mercadopago.py          — extrator Mercado Pago Visa
  cartao_santander.py            — extrator Santander Elite Mastercard
  cartao_samsung.py              — extrator Samsung Itaú Mastercard
  cartao_itau_personnalite.py    — extrator Itaú Personnalitê
  extrator_nubank_rdb.py         — extrator NuBank RDB
  db_senha.py                    — banco de senhas SQLite
  db_cliente.py                  — cadastro de clientes SQLite
  setup_senha.py                 — CLI para gestão de senhas
  setup_cliente.py               — CLI para gestão de clientes
tests/
  conftest.py                    — fixtures: DB isolado, logging suprimido
  helpers.py                     — factory e constantes de schema
  test_db.py                     — testes CRUD (15)
  test_extratores.py             — testes de parsing e schema (27)
  test_pdf_router.py             — testes de roteamento (13)
  test_integracao.py             — testes de integração (9)
  test_samsung.py                — testes Samsung Itaú
  test_itau_personnalite.py      — testes Itaú Personnalitê
vba/
  ModConfig.bas                  — caminhos do projeto (BASE_DIR)
  ModComum.bas                   — orquestrador VBA + utilitários compartilhados
  ModProcessar.bas               — botão Processar
  ModClientes.bas                — cadastro de clientes
  ModSenhas.bas                  — cadastro de senhas PDF
  Inativos/                      — módulos obsoletos
docs/
  SDD/                           — requisitos, design doc e tasks
  Esquema_LctosTratados_20260429_0148.md — schema completo da aba de saída
  Checkpoint_Sinc_20260506_0236.md       — estado do projeto e decisões
requirements.txt                 — dependências de produção
requirements-dev.txt             — dependências de desenvolvimento (pytest)
pytest.ini                       — configuração pytest
```

## Stack

- Python 3.13.7 + virtualenv
- pdfplumber — extração de texto de PDF
- pikepdf — descriptografia de PDF protegido por senha
- Excel 365 + VBA — interface de operação e destino dos dados (MVP)

## Instalação

```powershell
cd C:\Dev\projetos\Extratores
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

1. Abrir `Extratores.xlsm` (localizado em OneDrive\Documentos\Automações\)
2. Na primeira execução: [Cadastrar Cliente] e [Cadastrar Senha] para cada emissor com PDF protegido
3. Clicar em [Processar], selecionar cliente e pasta com os PDFs do mês
4. Dados são gravados na aba `LctosTratados` — **modo append acumulativo**

## PDFs protegidos por senha

Senhas armazenadas em banco SQLite local (`~/.extratores/dados.db`) — sem texto claro em planilha.  
O VBA entrega a senha ao Python via stdin; ela nunca aparece em linha de comando.

## Saída — aba LctosTratados

Schema completo (13 colunas, regras de formação, exemplos):  
[`docs/Esquema_LctosTratados_20260429_0148.md`](docs/Esquema_LctosTratados_20260429_0148.md)

**Rollback de lote:** deletar todas as linhas onde `ID_Lote` = id_lote a reverter.

## Logging

Arquivo de log: `~/.extratores/extrator.log` (rotativo, 5 MB, 3 backups)  
Nível padrão: INFO — override via variável de ambiente:

```powershell
$env:EXTRATORES_LOG_LEVEL = "DEBUG"   # ativa log de parsing detalhado
$env:EXTRATORES_LOG_LEVEL = "WARNING" # apenas avisos e erros
```

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

93 testes cobrindo: CRUD de banco, parsing de PDF com texto fixo, roteamento de emissor, schema do envelope JSON, exit codes de integração.

## Emissores suportados

| Emissor | Script | Observação |
|---|---|---|
| Mercado Pago Visa | cartao_mercadopago.py | PDF sem senha |
| Santander Elite Mastercard | cartao_santander.py | PDF requer senha cadastrada |
| Samsung Itaú Mastercard | cartao_samsung.py | PDF requer senha cadastrada |
| Itaú Personnalitê | cartao_itau_personnalite.py | PDF requer senha cadastrada |
| NuBank RDB | extrator_nubank_rdb.py | PDF sem senha |

## Requisitos de negócio

Ver `docs/SDD/Requiriments_20260428_1631.md` — regras BR-01 a BR-08.

## Convenção de nomenclatura de arquivos

Arquivos versionados seguem o padrão: `nome_AAAAMMDD_HHMM`

- `AAAAMMDD` = data de geração
- `HHMM` = horário de geração (24h) — **não é número de versão**

Exemplo: `Checkpoint_Sinc_20260506_0236.md` = gerado em 06/05/2026 às 02:36.

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
- Arquivos de configuração local (banco de senhas, planilhas) nunca são adicionados ao repositório

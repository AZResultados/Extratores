# Snapshot Técnico — Sistema Extratores AZ Resultados
**Versão:** 0.2-MVP | **Data:** 2026-04-28 | **Status:** Dois extratores funcionais em produção

---

## 1. Árvore de Diretórios

```
C:\Dev\projetos\Extratores\          ← raiz do projeto / repositório Git
├── .git\
├── .gitignore                        ← exclui: venv/, output/, __pycache__/, *.pyc, *.pyo, C:\Temp\extratores_output.json
├── output\                           ← pasta de saída (em .gitignore — não versionada)
├── src\
│   ├── cartao_mercadopago.py         ← extrator Mercado Pago (10.399 bytes)
│   └── cartao_santander.py           ← extrator Santander (10.923 bytes)
└── venv\                             ← virtualenv Python (não versionado)
    └── Scripts\
        └── python.exe

C:\Users\jwcos\OneDrive - Azmid\Documentos\Automações\
└── Extratores.xlsm                   ← hub de controle + destino dos dados
    ├── VBA: ModComum                 ← orquestrador (ProcessarExtrator)
    ├── VBA: ModMP                    ← ProcessarMP → chama ModComum("B2")
    ├── VBA: ModSantander             ← ProcessarSantander → chama ModComum("B3")
    ├── Aba: LctosTratados            ← destino único de todos os lançamentos
    ├── Aba: Config (oculta)          ← caminhos do ambiente
    └── Aba: Senhas                   ← credenciais de abertura de PDF

Arquivo intermediário (runtime, não persistido):
└── C:\Temp\extratores_output.json    ← JSON temporário Python→VBA (deletado após uso)

Pastas de entrada (definidas pelo operador no momento do uso — não são fixas no projeto):
└── [qualquer pasta] com *.pdf / *.PDF
```

---

## 2. Fluxo de Dados

```
[Operador clica botão no Excel]
        │
        ▼
ModMP ou ModSantander
        │ Call ProcessarExtrator("B2" ou "B3", nome)
        ▼
ModComum.ProcessarExtrator()
        ├── Lê Config!B1 → python_exe
        ├── Lê Config!B2 ou B3 → scriptPath
        ├── Abre tkinter filedialog (janela de seleção de pasta)  ← dentro do Python
        └── Executa via WScript.Shell:
            cmd /c chcp 65001 && python.exe script.py > C:\Temp\extratores_output.json
                    │
                    ▼
        cartao_mercadopago.py  OU  cartao_santander.py
                    │
                    ├── pdfplumber.open() → extrai texto bruto
                    ├── extrair_vencimento() → regex "Vencimento: DD/MM/YYYY"
                    ├── extrair_titular_cartao() / RE_TITUL → nome + 4 dígitos
                    ├── parsear_lancamentos() → regex/word-level por linha
                    ├── inferir_ano_*() → lógica de retroação por parcelas
                    ├── classificar_tipo() → Pagamento/Compra parcelada/Compra à vista/Outros/Ajuste
                    ├── validar_total() → soma vs. total do PDF (tolerância R$0,05 MP / R$0,10 Santander)
                    └── json.dumps() → stdout → C:\Temp\extratores_output.json
                    │
                    ▼
        ModComum (retoma após wsh.Run)
                    ├── ADODB.Stream lê JSON em UTF-8
                    ├── Apaga linhas 2:N de LctosTratados   ← SOBRESCRITA
                    ├── Parse manual do JSON (InStr/Mid — sem biblioteca)
                    ├── Grava linhas em LctosTratados (A→F)
                    └── Kill C:\Temp\extratores_output.json  ← descarte do temporário
```

**Aba de destino: `LctosTratados`**

| Col | Campo | Tipo gravado | Observação |
|-----|-------|-------------|------------|
| A | Arquivo Origem | String | Caminho absoluto completo do PDF |
| B | Data Vencimento | Date (serial Excel) | `CDate(fVenc)` + format `dd/mm/yyyy` |
| C | Descrição | String | Inclui parcela e data da compra embutidas |
| D | Valor (R$) | Double | Débitos negativos, créditos positivos |
| E | Tipo | String | Pagamento / Compra parcelada / Compra à vista / Outros / Ajuste |
| F | Titular - Cartão | String | `NOME TITULAR - XXXX` (últimos 4 dígitos) |

**Modo de escrita:** **Sobrescrita total** — `wsDados.Rows("2:" & lastRow).Delete` antes de cada execução.

---

## 3. Stack

| Componente | Detalhe |
|---|---|
| Python | 3.13.7 (Windows, venv em `C:\Dev\projetos\Extratores\venv\`) |
| pdfplumber | Extração de texto e words com coordenadas (MP e Santander) |
| python-dateutil | Cálculo retroativo de datas de parcelas |
| pikepdf | Instalado no venv — usado manualmente para descriptografar PDFs Santander antes do processamento; **não integrado aos scripts** — etapa pré-processamento manual do operador |
| tkinter | Seletor de pasta (nativo Python) — acionado dentro do script quando chamado sem argumento CLI |
| io / re / json / pathlib / collections | Stdlib — sem dependências adicionais |
| VBA (Excel 365) | WScript.Shell, ADODB.Stream, FileDialog, módulos separados por extrator |
| Git | Repositório privado `AZResultados/Extratores` no GitHub |

**Arquivo de dependências:** ausente — nenhum `requirements.txt` ou `pyproject.toml` no repositório.

---

## 4. Credenciais — Armazenamento e Uso

| Item | Situação atual |
|---|---|
| **Mecanismo** | Aba `Senhas` no `Extratores.xlsm` — texto claro, sem proteção de sheet |
| **Conteúdo** | Santander: CPF/CNPJ numérico do titular; Mercado Pago: `ND`; Samsung: CPF parcial |
| **Uso atual** | **Manual** — o operador lê a senha na aba e a informa ao pikepdf separadamente, antes de rodar o extrator |
| **Integração com scripts** | Nenhuma — `cartao_santander.py` e `cartao_mercadopago.py` recebem PDFs já descriptografados |
| **Risco** | Arquivo em OneDrive (`C:\Users\jwcos\OneDrive - Azmid\...`) — credenciais sincronizadas para a nuvem em texto claro |
| **Enquadramento BR-08** | Conforme para MVP (operador único = proprietário AZ Resultados). Torna-se violação crítica em qualquer distribuição para terceiros |
| **Natureza da credencial** | Senha de abertura de PDF (CPF/CNPJ do titular) — não é senha de acesso bancário |

---

## 5. Violações dos Requisitos — Gaps Concretos

### BR-02 — Isolamento de Dados ❌

**Requisito:** lançamentos de clientes distintos não podem ser expostos ou misturados.

**Gap 1 — Sem campo `Cliente` no schema de saída.**
A aba `LctosTratados` não tem coluna identificando o cliente da AZ Resultados. O campo `Titular - Cartão` identifica o portador do cartão dentro de uma fatura, mas não a qual cliente (pessoa física ou jurídica contratante) aquele dado pertence. Quando o sistema escalar para múltiplos clientes, a separação dependerá 100% de disciplina manual do operador.

**Gap 2 — Pasta de entrada livre.**
O operador seleciona qualquer pasta no momento do uso. Nada impede (sistematicamente) que PDFs de dois clientes diferentes estejam na mesma pasta e sejam processados juntos no mesmo lote, gerando mistura silenciosa.

**Gap 3 — Sobrescrita não resolve o problema.**
O modo sobrescrita atual protege contra acúmulo de lotes, mas não contra mistura dentro do mesmo lote.

---

### BR-03 — Fail-Fast em Falhas ❌

**Requisito:** falha em qualquer arquivo deve interromper todo o lote e não persistir dados.

**Gap — continue-on-error em ambos os scripts.**

```python
# cartao_mercadopago.py e cartao_santander.py — mesmo padrão
for pdf_path in pdfs:
    try:
        ...
        todos.extend(lancamentos)      # ← dados do PDF atual já acumulados
    except Exception as e:
        erros.append(f"{pdf_path.name}: {e}")  # ← loga e CONTINUA
```

Se o arquivo 3 de 5 falhar, os lançamentos dos arquivos 1 e 2 já estão em `todos_lancamentos` e serão gravados no Excel normalmente. O operador recebe um aviso (`MsgBox`) mas os dados parciais persistem.

**Agravante:** a divergência de totais (`validar_total`) também não interrompe — gera aviso mas prossegue com os dados divergentes.

---

### Gaps Adicionais para Registrar no SDD

| # | Gap | BR | Severidade |
|---|---|---|---|
| G1 | Sem campo `Cliente` na saída | BR-02 | Alta |
| G2 | pikepdf não integrado — etapa manual não auditável | BR-04 | Média |
| G3 | Sem `ID_Lote` / `DataProcessamento` — rollback inviável | BR-04 | Alta |
| G4 | Sem `requirements.txt` — ambiente não reproduzível | — | Média |
| G5 | Credenciais de PDF em texto claro no OneDrive | BR-08 (futuro) | Alta (latente) |
| G6 | Tolerâncias de validação diferentes por extrator (R$0,05 vs R$0,10) sem documentação de critério | BR-05 | Baixa |
| G7 | `C:\Temp` hardcoded no VBA — quebra em ambientes sem essa pasta ou sem permissão de escrita | — | Média |

---

*Snapshot gerado a partir de leitura direta dos arquivos fonte: `cartao_mercadopago.py`, `cartao_santander.py`, `ModComum.bas`, `ModMP.bas`, `ModSantander.bas`, print da estrutura de pastas, e confirmação manual das abas `Config` e `Senhas`.*
# CHECKPOINT_SINC — Extratores AZ Resultados
**Gerado:** 2026-04-28T02:00Z | **Versão:** 0.3-MVP | **Para:** Claude Code / Gemini / DeepSeek

---

## 1. STATUS ATUAL

| Item | Estado |
|------|--------|
| Repo | PUBLIC — https://github.com/AZResultados/Extratores |
| Branch | main (único) |
| Extratores em produção | 2: `cartao_mercadopago.py` + `cartao_santander.py` |
| Interface operacional | `Extratores.xlsm` (OneDrive) com botões VBA |
| G4 `requirements.txt` | **RESOLVIDO** — commitado no repo (ver §2) |
| pikepdf integração | **NÃO RESOLVIDO** — etapa ainda manual |
| Campo Cliente | **NÃO RESOLVIDO** — ausente do schema de saída |
| Fail-Fast (BR-03) | **NÃO RESOLVIDO** — continue-on-error em ambos os scripts |
| ID_Lote (BR-04) | **NÃO RESOLVIDO** — sem rastreabilidade de lote |

---

## 2. STACK COMPLETA COM VERSÕES

```
Python         3.13.7   (Windows, venv em C:\Dev\projetos\Extratores\venv\)
pdfplumber     0.11.9   pip — extração texto/words com coordenadas
pikepdf        10.5.1   pip — descriptografia PDF (manual, não integrado)
python-dateutil 2.9.0.post0  pip — cálculo retroativo datas parcelas
tkinter        nativo Python — seletor pasta (fallback sem arg CLI)
io / re / json / pathlib / collections  stdlib
VBA            Excel 365 — WScript.Shell, ADODB.Stream, FileDialog
Git            repo público AZResultados/Extratores (4 commits)
```

`requirements.txt` (commitado):
```
pdfplumber==0.11.9
pikepdf==10.5.1
python-dateutil==2.9.0.post0
```

---

## 3. ESTRUTURA DE ARQUIVOS DO REPOSITÓRIO

```
AZResultados/Extratores/          ← raiz Git (PUBLIC)
├── .gitignore                    ← exclui: venv/, output/, __pycache__/, C:\Temp\*.json
├── README.md
├── requirements.txt              ← NOVO — G4 resolvido
├── src/
│   ├── cartao_mercadopago.py     ← extrator MP Visa (~10.4 KB)
│   └── cartao_santander.py       ← extrator Santander Elite MC (~10.9 KB)
├── vba/
│   ├── ModComum.bas              ← orquestrador ProcessarExtrator()
│   ├── ModMP.bas                 ← botão MP → chama ModComum("B2")
│   └── ModSantander.bas          ← botão Santander → chama ModComum("B3")
└── docs/
    ├── Requiriments_*.md         ← BR-01 a BR-08 (LOCKED v1.0)
    ├── SnapShot_Tecnico_*.md     ← estado código + gaps
    └── Checkpoint_*.md           ← decisões arquitetura

Fora do repo (não versionado):
C:\Users\[user]\OneDrive - Azmid\Documentos\Automações\
└── Extratores.xlsm              ← hub controle + destino dados
    ├── VBA: ModComum / ModMP / ModSantander
    ├── Aba: LctosTratados       ← destino único lançamentos
    ├── Aba: Config (oculta)     ← caminhos ambiente (python_exe, scriptPath)
    └── Aba: Senhas              ← credenciais PDF texto claro

Runtime (não persistido):
C:\Temp\extratores_output.json   ← JSON intermediário Python→VBA (deletado após uso)
```

---

## 4. FLUXO DE DADOS

```
[Operador → botão Excel]
        │
        ▼
ModMP.bas / ModSantander.bas
  └─ Call ProcessarExtrator("B2"|"B3", nomeExtrator)
        │
        ▼
ModComum.ProcessarExtrator()
  ├─ Lê Config!B1 → python_exe path
  ├─ Lê Config!B2|B3 → scriptPath
  └─ WScript.Shell.Run:
     cmd /c chcp 65001 && python.exe <script> [sem args CLI no MVP atual]
        │
        ▼  [dentro do Python]
cartao_mercadopago.py | cartao_santander.py
  ├─ tkinter.filedialog → operador seleciona pasta PDFs
  ├─ [MANUAL PRÉ-PROCESSAMENTO Santander: pikepdf descriptografa PDF → salva Livre-*.pdf]
  ├─ pdfplumber.open(pdf) → texto bruto
  ├─ extrair_vencimento() → regex "Vencimento: DD/MM/YYYY"
  ├─ extrair_titular_cartao() → RE_TITUL → "NOME - XXXX"
  ├─ parsear_lancamentos() → regex/word-level por linha
  ├─ inferir_ano_*() → retroação por contagem de parcelas
  ├─ classificar_tipo() → enum 5 valores
  ├─ validar_total() → soma vs total PDF (tol: R$0,05 MP / R$0,10 Santander)
  └─ json.dumps(lista_lancamentos) → stdout → C:\Temp\extratores_output.json
        │
        ▼
ModComum (retoma após wsh.Run)
  ├─ ADODB.Stream.LoadFromFile → lê JSON UTF-8
  ├─ wsDados.Rows("2:" & lastRow).Delete  ← SOBRESCRITA TOTAL
  ├─ Parse JSON manual (InStr/Mid — sem biblioteca VBA)
  ├─ Grava linhas A→F em LctosTratados
  └─ Kill C:\Temp\extratores_output.json
```

---

## 5. SCHEMA ABA LctosTratados

| Col | Campo | Tipo Python | Tipo Excel gravado | Observações |
|-----|-------|-------------|-------------------|-------------|
| A | Arquivo Origem | str | String | Caminho absoluto completo do PDF |
| B | Data Vencimento | str "DD/MM/YYYY" | Date serial (CDate) | Format `dd/mm/yyyy` aplicado |
| C | Descrição | str | String | Parcela e data compra embutidas no texto |
| D | Valor (R$) | float | Double | Débitos negativos, créditos positivos |
| E | Tipo | str enum | String | Pagamento / Compra parcelada / Compra à vista / Outros / Ajuste |
| F | Titular - Cartão | str | String | "NOME TITULAR - XXXX" (4 dígitos) |

**Modo escrita:** SOBRESCRITA TOTAL — delete rows 2:N antes de cada execução.
**Colunas ausentes (gaps ativos):** Cliente, ID_Lote, DataProcessamento, ArquivoOrigem_Hash.

---

## 6. CREDENCIAIS — MECANISMO E ENQUADRAMENTO BR-08

| Atributo | Detalhe |
|----------|---------|
| Armazenamento | Aba `Senhas` do `Extratores.xlsm` — texto claro, sheet sem proteção |
| Conteúdo | Santander: CPF/CNPJ numérico titular; Mercado Pago: "ND"; Samsung: CPF parcial |
| Natureza | Senha de abertura PDF (CPF/CNPJ do portador) — NÃO é senha bancária |
| Uso atual | MANUAL — operador lê aba Senhas e aplica pikepdf fora do script |
| Integração scripts | NENHUMA — scripts recebem PDFs já descriptografados |
| Risco exposição | Arquivo em OneDrive → credenciais sincronizadas para nuvem em texto claro |
| Status BR-08 | **CONFORME para MVP** (operador único = proprietário AZ Resultados) |
| Gatilho violação | Qualquer distribuição para terceiros → violação crítica imediata |
| Ação futura obrigatória | Cofre de senhas (keyring/Windows Credential Store) antes de v1.0-multi-user |

---

## 7. DECISÕES DE ARQUITETURA TOMADAS (LOCKED)

| # | Decisão | Rationale |
|---|---------|-----------|
| A1 | pikepdf em memória via `io.BytesIO` | Elimina arquivo temporário sem senha em disco (BR-06) |
| A2 | Interface VBA→Python via WScript.Shell com args CLI | `--input`, `--cliente`, `--password` passados pelo VBA |
| A3 | `sys.exit(1)` em erro → VBA trata como Fail-Fast | Aciona interrupção no Excel sem persistir dados parciais |
| A4 | Pasta de entrada estruturada por cliente: `input/NOME_CLIENTE/` | Isolamento físico pré-processamento (BR-02) |
| A5 | Coluna `Cliente` no schema de saída | Rastreabilidade pós-processamento (BR-02 + BR-04) |
| A6 | Coluna `Parcela` extraída via Regex | Mantém dado estruturado separado da Descrição |
| A7 | `requirements.txt` commitado no repo | G4 resolvido — ambiente reproduzível |
| A8 | Commits nunca mencionam nomes de clientes, CPFs ou dados sensíveis | Repo público — histórico permanentemente visível |

> **NOTA:** A1, A2, A3, A4, A5, A6 são design acordado — ainda NÃO implementados no código. A7 e A8 estão implementados.

---

## 8. GAPS ATIVOS — BR-02, BR-03, BR-04

### GAP BR-02 — Isolamento de Dados ❌

**G1 — Sem campo Cliente no schema:**
```python
# saída atual em ambos os scripts — 6 campos, sem "cliente"
lancamento = {
    "arquivo": str(pdf_path),
    "vencimento": vencimento_str,
    "descricao": descricao,
    "valor": valor,
    "tipo": tipo,
    "titular_cartao": titular
}
# FALTA: "cliente": cliente_arg  ← virá de --cliente CLI
```

**G2 — Pasta de entrada livre (sem enforcing):**
```python
# cartao_mercadopago.py / cartao_santander.py
pasta = filedialog.askdirectory(title="Selecione a pasta com os PDFs")
# sem validação de estrutura input/CLIENTE/ — operador pode selecionar qualquer pasta
# PDFs de clientes distintos podem estar juntos → mistura silenciosa
```

---

### GAP BR-03 — Fail-Fast ❌

**Continue-on-error em ambos os scripts:**
```python
for pdf_path in pdfs:
    try:
        lancamentos = processar_pdf(pdf_path)
        todos.extend(lancamentos)   # ← dados do PDF atual já acumulados
    except Exception as e:
        erros.append(f"{pdf_path.name}: {e}")  # ← loga e CONTINUA

# se arquivo 3/5 falhar → arquivos 1 e 2 JÁ estão em todos[] → serão gravados
# validar_total() divergência → gera aviso mas NÃO interrompe
```

**Fix acordado:**
```python
# substituir try/except por raise imediato
for pdf_path in pdfs:
    lancamentos = processar_pdf(pdf_path)  # exception propaga → sys.exit(1)
    todos.extend(lancamentos)
```

---

### GAP BR-04 — Rastreabilidade ❌

**G3 — Sem ID_Lote / DataProcessamento:**
```python
# saída atual — sem identificador de lote
json.dumps(todos_lancamentos)  # lista pura, sem envelope de metadados

# schema necessário:
{
  "id_lote": "MP-20260428-143022",   # {EMISSOR}-{YYYYMMDD}-{HHMMSS}
  "data_processamento": "2026-04-28T14:30:22",
  "cliente": "NOME_CLIENTE",
  "emissor": "mercadopago",
  "lancamentos": [ {...}, {...} ]
}
```

---

## 9. BACKLOG PÓS-MVP

| ID | Item | BR | Severidade | Status |
|----|------|----|------------|--------|
| G1 | Campo `Cliente` no schema saída + arg `--cliente` CLI | BR-02 | Alta | **Próximo sprint** |
| G2 | pikepdf integrado aos scripts (in-memory BytesIO) | BR-04/BR-06 | Média | Backlog |
| G3 | `ID_Lote` + `DataProcessamento` no envelope JSON | BR-04 | Alta | **Próximo sprint** |
| G4 | `requirements.txt` | — | Média | **RESOLVIDO ✓** |
| G5 | Cofre de senhas (keyring/WinCredStore) | BR-08 | Alta (latente) | Pré v1.0-multi |
| G6 | Tolerâncias validação documentadas (R$0,05 MP vs R$0,10 SAN) | BR-05 | Baixa | Backlog |
| G7 | `C:\Temp` hardcoded no VBA → usar `Environ("TEMP")` | — | Média | Backlog |
| PCI-3 | Datas seriais Excel → conversão para Date nativo Python | BR-05 | Média | Backlog |

---

## 10. PRÓXIMO PASSO ACORDADO

**Objetivo:** Design Doc → Tasks atômicas para execução no Claude Code.

**Tríade de Tasks prioritárias (ordem de execução):**

```
TASK-01 [BR-03]: Implementar Fail-Fast
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py
  Ação: substituir try/except loop por propagação imediata de exception
  Critério: sys.exit(1) disparado se qualquer PDF falhar → VBA aborta

TASK-02 [BR-02 + BR-04]: Adicionar --cliente + --input CLI args + campo Cliente na saída
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py + vba/ModComum.bas
  Ação: argparse com --cliente e --input obrigatórios; adicionar campo "cliente" no JSON
  Critério: LctosTratados col G = Cliente; pasta validada como input/CLIENTE/

TASK-03 [BR-04]: Envelope JSON com ID_Lote
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py + vba/ModComum.bas
  Ação: json.dumps({"id_lote": ..., "lancamentos": [...]})
  Critério: VBA extrai lancamentos do envelope; ID_Lote gravado na aba LctosTratados

TASK-04 [BR-02/BR-06]: Integrar pikepdf in-memory (BytesIO)
  Arquivo: src/cartao_santander.py
  Ação: receber --password via arg CLI; descriptografar em memória antes do pdfplumber
  Critério: zero arquivos temporários decriptografados em disco
```

**Protocolo Claude Code:**
- Cada task = 1 commit atômico
- Mensagem commit: genérica descritiva, sem dados de clientes/CPFs
- Testar com PDF real após cada task antes de avançar
- Atualizar `docs/SnapShot_Tecnico_*.md` ao final

---

## META

```
repo:     https://github.com/AZResultados/Extratores
versão:   0.3-MVP
commits:  4 (repo público)
docs/:    Requiriments_*.md + SnapShot_*.md + Checkpoint_*.md
próxima:  execução TASK-01 no Claude Code
gerado:   2026-04-28 | Claude Sonnet 4.6
```

# CHECKPOINT_SINC — Extratores AZ Resultados
**Gerado:** 2026-04-28T02:50Z | **Versão:** 0.4.1-MVP | **Para:** Claude Code / Gemini / DeepSeek

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
| Arquivo JSON temporário em disco | **NÃO RESOLVIDO** — `C:\Temp\extratores_output.json` ainda persiste entre Run e leitura |

---

## 2. STACK COMPLETA COM VERSÕES

```
Python          3.13.7        Windows, venv em C:\Dev\projetos\Extratores\venv\
pdfplumber      0.11.9        pip — extração texto/words com coordenadas
pikepdf         10.5.1        pip — descriptografia PDF (manual, não integrado)
python-dateutil 2.9.0.post0   pip — cálculo retroativo datas parcelas
tkinter         nativo Python — seletor pasta (fallback sem arg CLI)
io / re / json / pathlib / collections  stdlib
VBA             Excel 365 — WScript.Shell.Exec() [target], ADODB.Stream, FileDialog
Git             repo público AZResultados/Extratores (5 commits)
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
├── .gitignore                    ← exclui: venv/, output/, __pycache__/
├── README.md
├── requirements.txt              ← G4 resolvido
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
└── Extratores.xlsm
    ├── VBA: ModComum / ModMP / ModSantander
    ├── Aba: LctosTratados       ← destino único lançamentos
    ├── Aba: Config (oculta)     ← caminhos ambiente
    └── Aba: Senhas              ← credenciais PDF texto claro

Runtime (target: eliminado — ver G7 e TASK-05):
C:\Temp\extratores_output.json   ← JSON intermediário Python→VBA (atual: arquivo; target: stdout)
```

---

## 4. FLUXO DE DADOS

**Estado atual (arquivo em disco):**
```
[Operador → botão Excel]
        │
        ▼
ModComum.ProcessarExtrator()
  └─ WScript.Shell.Run() → aguarda exit code
     cmd /c python.exe <script> > C:\Temp\extratores_output.json
        │
        ▼
Python → json.dumps() → stdout → arquivo C:\Temp\extratores_output.json
        │
        ▼
ModComum → ADODB.Stream.LoadFromFile(C:\Temp\...) → parse → grava Excel
         → Kill C:\Temp\extratores_output.json
```

**Estado target (stdout direto — TASK-05 / G7):**
```
[Operador → botão Excel]
        │
        ▼
ModComum.ProcessarExtrator()
  └─ WScript.Shell.Exec() → captura stdout em memória (StdOut.ReadAll)
     python.exe <script> --cliente X --input Y [--password Z]
        │
        ▼
Python → json.dumps() → sys.stdout  [zero escrita em disco]
        │
        ▼
ModComum → jsonStr = oExec.StdOut.ReadAll → parse → grava Excel
         [sem arquivo temporário; sem Kill]
```

**Pipeline interno Python (target pós-tasks):**
```
pdfplumber.open(pdf_em_memoria)     ← pikepdf BytesIO (TASK-04)
  ├─ extrair_vencimento()           → regex "Vencimento: DD/MM/YYYY"
  ├─ extrair_titular_cartao()       → RE_TITUL → "NOME - XXXX"
  ├─ parsear_lancamentos()          → regex/word-level
  ├─ extrair_parcela()              → regex "NN/NN" → campo separado (TASK-05)
  ├─ inferir_ano_*()                → retroação por contagem de parcelas
  ├─ classificar_tipo()             → enum 5 valores
  └─ validar_total()                → soma vs total PDF; exception se divergir (TASK-01)
```

---

## 5. SCHEMA ABA LctosTratados

**Ordem lógica: Identificadores → Dados.** Python monta o JSON nessa ordem; VBA grava sequencialmente sem reordenação.

| Col | Campo JSON | Campo Excel | Tipo Python | Tipo Excel | Observações |
|-----|-----------|-------------|-------------|------------|-------------|
| A | `cliente` | Cliente | str | String | Arg `--cliente` CLI — **IDENTIFICADOR** |
| B | `id_lote` | ID_Lote | str | String | `{EMISSOR}-{YYYYMMDD}-{HHMMSS}` — **IDENTIFICADOR** |
| C | `arquivo` | Arquivo Origem | str | String | Caminho absoluto do PDF |
| D | `vencimento` | Data Vencimento | str "DD/MM/YYYY" | Date serial (CDate) | Format `dd/mm/yyyy` |
| E | `descricao` | Descrição | str | String | Texto limpo, sem parcela embutida |
| F | `parcela` | Parcela | str \| null | String | "02/06" ou null se não parcelado (TASK-05) |
| G | `valor` | Valor (R$) | float | Double | Débitos negativos, créditos positivos |
| H | `tipo` | Tipo | str enum | String | Pagamento / Compra parcelada / Compra à vista / Outros / Ajuste |
| I | `titular_cartao` | Titular - Cartão | str | String | "NOME TITULAR - XXXX" (4 dígitos) |

**Modo escrita:** SOBRESCRITA TOTAL — delete rows 2:N antes de cada execução.

---

## 6. CREDENCIAIS — MECANISMO E ENQUADRAMENTO BR-08

| Atributo | Detalhe |
|----------|---------|
| Armazenamento | Aba `Senhas` do `Extratores.xlsm` — texto claro, sheet sem proteção |
| Conteúdo | Santander: CPF/CNPJ numérico titular; Mercado Pago: "ND"; Samsung: CPF parcial |
| Natureza | Senha de abertura PDF (CPF/CNPJ do portador) — NÃO é senha bancária |
| Uso atual | MANUAL — operador lê aba Senhas e aplica pikepdf fora do script |
| Integração scripts | NENHUMA — scripts recebem PDFs já descriptografados |
| Risco exposição | OneDrive sincroniza credenciais em texto claro para a nuvem |
| Status BR-08 | **CONFORME para MVP** (operador único = proprietário AZ Resultados) |
| Gatilho violação | Qualquer distribuição para terceiros → violação crítica imediata |
| Ação futura obrigatória | Cofre de senhas (keyring / Windows Credential Store) antes de v1.0-multi-user |

---

## 7. DECISÕES DE ARQUITETURA TOMADAS (LOCKED)

| # | Decisão | Rationale |
|---|---------|-----------|
| A1 | pikepdf in-memory via `io.BytesIO` | Zero arquivo temporário sem senha em disco (BR-06) |
| A2 | Interface VBA→Python via `WScript.Shell.Exec()` capturando stdout | Elimina arquivo JSON intermediário em disco (BR-06 / G7) |
| A3 | `sys.exit(1)` em erro → VBA lê exit code e aborta | Fail-Fast sem persistência de dados parciais (BR-03) |
| A4 | Pasta de entrada estruturada por cliente: `input/NOME_CLIENTE/` | Isolamento físico pré-processamento (BR-02) |
| A5 | `--cliente` obrigatório via CLI → campo `cliente` col A no schema | Identificador primário para isolamento e rastreabilidade (BR-02 + BR-04) |
| A6 | Campo `parcela` separado via Regex — col F no schema | Dado estruturado; descricao limpa sem embutimento (TASK-05) |
| A7 | Schema JSON ordenado: Identificadores (A,B) → Dados (C→I) | VBA grava sequencialmente sem reordenação |
| A8 | `requirements.txt` commitado no repo | G4 resolvido — ambiente reproduzível |
| A9 | Commits nunca mencionam nomes de clientes, CPFs ou dados sensíveis | Repo público — histórico permanentemente visível |

> **NOTA:** A1–A7 são design acordado — ainda NÃO implementados no código. A8 e A9 estão implementados.

---

## 8. GAPS ATIVOS — BR-02, BR-03, BR-04

### GAP BR-02 — Isolamento de Dados ❌

**G1 — Sem campo Cliente no schema:**
```python
# saída atual — 6 campos, sem "cliente"
lancamento = {
    "arquivo": str(pdf_path),
    "vencimento": vencimento_str,
    "descricao": descricao,   # parcela embutida aqui
    "valor": valor,
    "tipo": tipo,
    "titular_cartao": titular
}
# FALTA: "cliente": cliente_arg  ← virá de --cliente CLI (TASK-02)
# FALTA: "parcela": parcela_str  ← extraída via regex (TASK-05)
```

**G2 — Pasta de entrada sem enforcing:**
```python
pasta = filedialog.askdirectory(title="Selecione a pasta com os PDFs")
# sem validação input/CLIENTE/ — mistura silenciosa possível
```

---

### GAP BR-03 — Fail-Fast ❌

```python
for pdf_path in pdfs:
    try:
        lancamentos = processar_pdf(pdf_path)
        todos.extend(lancamentos)   # dados acumulados antes da falha
    except Exception as e:
        erros.append(f"{pdf_path.name}: {e}")  # continua — viola BR-03

# fix (TASK-01):
for pdf_path in pdfs:
    lancamentos = processar_pdf(pdf_path)  # exception propaga → sys.exit(1)
    todos.extend(lancamentos)
```

---

### GAP BR-04 — Rastreabilidade ❌

```python
# atual: lista pura sem envelope
json.dumps(todos_lancamentos)

# target (TASK-03):
{
  "id_lote": "MP-20260428-143022",
  "data_processamento": "2026-04-28T14:30:22",
  "cliente": "NOME_CLIENTE",
  "emissor": "mercadopago",
  "lancamentos": [
    {
      "cliente": "NOME_CLIENTE",
      "id_lote": "MP-20260428-143022",
      "arquivo": "/path/fatura.pdf",
      "vencimento": "14/04/2026",
      "descricao": "SUPERMERCADO XYZ",
      "parcela": "02/03",
      "valor": -289.42,
      "tipo": "Compra parcelada",
      "titular_cartao": "NOME TITULAR - 1234"
    }
  ]
}
```

---

## 9. BACKLOG PÓS-MVP

| ID | Item | BR | Severidade | Status |
|----|------|----|------------|--------|
| G1 | Campo `Cliente` col A + arg `--cliente` CLI obrigatório | BR-02 | Alta | **Próximo sprint** |
| G2 | pikepdf integrado in-memory (BytesIO) + `--password` CLI | BR-04/BR-06 | Média | TASK-04 |
| G3 | Envelope JSON com `ID_Lote` + `DataProcessamento` | BR-04 | Alta | **Próximo sprint** |
| G4 | `requirements.txt` | — | Média | **RESOLVIDO ✓** |
| G5 | Cofre de senhas (keyring / WinCredStore) | BR-08 | Alta (latente) | Pré v1.0-multi |
| G6 | Tolerâncias de validação documentadas (R$0,05 MP vs R$0,10 SAN) | BR-05 | Baixa | Backlog |
| G7 | Eliminar arquivo JSON em disco: `WScript.Shell.Exec()` captura stdout | BR-06 | Média | TASK-05 |
| PCI-3 | Datas seriais Excel → Date nativo Python | BR-05 | Média | Backlog |

> **G7 — Decisão:** não usar `Environ("TEMP")`. A solução correta é eliminar a escrita em disco. `WScript.Shell.Exec()` retorna objeto com `.StdOut.ReadAll` — JSON capturado diretamente em memória VBA, sem arquivo intermediário.

---

## 10. PRÓXIMO PASSO ACORDADO

**Objetivo:** Tasks atômicas para execução no Claude Code.

```
TASK-01 [BR-03]: Fail-Fast
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py
  Ação: remover try/except do loop; exception propaga → sys.exit(1)
  Critério: qualquer PDF falho aborta lote; zero dados persistidos

TASK-02 [BR-02 + BR-04]: --cliente CLI + col A no schema
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py + vba/ModComum.bas
  Ação: argparse --cliente obrigatório; campo "cliente" como primeira chave no dict JSON
  Critério: col A = Cliente; col B = ID_Lote; pasta validada como input/CLIENTE/
  Schema JSON target: {"cliente": X, "id_lote": Y, "arquivo": Z, ...}

TASK-03 [BR-04]: Envelope JSON com ID_Lote
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py + vba/ModComum.bas
  Ação: json.dumps({"id_lote": ..., "cliente": ..., "lancamentos": [...]})
  Critério: VBA extrai lancamentos do envelope; ID_Lote gravado col B em LctosTratados

TASK-04 [BR-06]: pikepdf in-memory
  Arquivo: src/cartao_santander.py + vba/ModComum.bas
  Ação: --password via CLI; pikepdf.open(pdf, password=pwd) → BytesIO → pdfplumber
  Critério: zero arquivos Livre-*.pdf em disco
  ⚠️ RISCO ACEITO (MVP): senha trafega em texto claro via arg CLI.
     Enquadramento: BR-08 exceção MVP documentada — operador único = proprietário.
     Mitigação futura: keyring antes de v1.0-multi-user.

TASK-05 [BR-06 / G7]: Eliminar JSON em disco — VBA Exec()
  Arquivo: vba/ModComum.bas
  Ação: substituir WScript.Shell.Run() por .Exec(); capturar .StdOut.ReadAll em memória
  Critério: C:\Temp\extratores_output.json nunca criado; fluxo Python→VBA via stdout puro
  ⚠️ RISCO DEADLOCK: Exec() bloqueia leitura do stdout enquanto o processo escreve.
     Se o JSON gerado exceder o buffer do pipe (~4 KB no Windows), o processo Python
     trava aguardando o VBA ler, e o VBA trava aguardando o Python terminar.
     Mitigação obrigatória: chamar .StdOut.ReadAll ANTES de verificar .Status = 0.
     Padrão seguro:
       jsonStr = oExec.StdOut.ReadAll   ' lê primeiro
       If oExec.ExitCode <> 0 Then ...  ' verifica depois

TASK-06 [BR-02]: Extrair Parcela — campo separado no JSON
  Arquivo: src/cartao_mercadopago.py + src/cartao_santander.py + vba/ModComum.bas
  Ação: regex extrai parcela da descricao → campos separados "descricao" e "parcela"
    Regex target: r'(\d{2}/\d{2})' no final da string de descrição
    Ex. input:  "SUPERMERCADO XYZ 02/03"
    Ex. output: {"descricao": "SUPERMERCADO XYZ", "parcela": "02/03"}
    Sem parcela: {"descricao": "SUPERMERCADO XYZ", "parcela": null}
  Critério: col E = Descrição limpa; col F = Parcela em LctosTratados
```

**Protocolo Claude Code:**
- Cada task = 1 commit atômico
- Mensagem commit: genérica descritiva, sem dados de clientes/CPFs
- Testar com PDF real após cada task antes de avançar
- Atualizar `docs/SnapShot_Tecnico_*.md` ao final do sprint

---

## META

```
repo:      https://github.com/AZResultados/Extratores
versão:    0.4.1-MVP
commits:   5 (repo público)
docs/:     Requiriments_*.md + SnapShot_*.md + Checkpoint_*.md
próxima:   execução TASK-01 no Claude Code
gerado:    2026-04-28 | Claude Sonnet 4.6
revisado:  sugestões Gemini Pro 3.1 + DeepSeek 3.4 + auditoria Claude (TASK-05 desmembrada; risco deadlock Exec() documentado)
```

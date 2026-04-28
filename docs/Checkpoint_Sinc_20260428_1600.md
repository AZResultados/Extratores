# CHECKPOINT_SINC — Extratores AZ Resultados
v0.5-MVP | 2026-04-28 | Para: Claude Code

**Revisão:** v2 — adição TASK-07, atualização estrutura repo, credenciais e decisões locked  
**Fonte da verdade:** este documento prevalece sobre Checkpoint_Sinc_20260428_0444.md

---

## 1. STATUS

| Item | Estado |
|------|--------|
| Repo | PUBLIC https://github.com/AZResultados/Extratores |
| Branch | main |
| Extratores prod | cartao_mercadopago.py + cartao_santander.py |
| Interface | Extratores.xlsm (OneDrive) |
| requirements.txt | RESOLVIDO ✓ |
| TASK-01 CLI+Lote | PENDENTE |
| TASK-02 Envelope JSON | PENDENTE |
| TASK-03 pikepdf in-mem | PENDENTE |
| TASK-04 Regex parcela | PENDENTE |
| TASK-05 VBA Exec() | PENDENTE |
| TASK-06 Schema+Gravação | PENDENTE |
| TASK-07 pdf_decrypt módulo compartilhado | PENDENTE |

---

## 2. STACK

```
Python          3.13.7  venv: C:\Dev\projetos\Extratores\venv\
pdfplumber      0.11.9
pikepdf         10.5.1  (instalado, NÃO integrado — pendente TASK-03/TASK-07)
python-dateutil 2.9.0.post0
tkinter         stdlib (fallback sem CLI — remover pós-tasks)
VBA             Excel 365
Git             public repo AZResultados/Extratores (7 commits)
```

---

## 3. ESTRUTURA REPO

```
AZResultados/Extratores/
├── .gitignore          (venv/, output/, __pycache__/)
├── README.md
├── requirements.txt
├── src/
│   ├── pdf_decrypt.py          (módulo compartilhado — descriptografia in-memory)
│   ├── cartao_mercadopago.py   (~10.4 KB)
│   └── cartao_santander.py     (~10.9 KB)
├── vba/
│   ├── ModComum.bas
│   ├── ModMP.bas
│   └── ModSantander.bas
└── docs/
    ├── Requiriments.md
    ├── Design_Doc_20260428_1557.md
    ├── Tasks_20260428_1530.md
    ├── _SnapShot_Tecnico_20260428_0100.md
    └── Checkpoint_Sinc_20260428_*.md

Fora do repo:
C:\Users\[operador]\OneDrive\Documentos\Automações\Extratores.xlsm
  Abas: LctosTratados | Config (oculta) | Senhas
```

---

## 4. FLUXO ATUAL (estado código — pré-tasks)

```
[botão Excel] → ModComum.ProcessarExtrator()
  └─ WScript.Shell.Run()
     cmd /c python.exe script.py > C:\Temp\extratores_output.json
     → Python: json.dumps(lista_lancamentos) → stdout → arquivo disco
     → VBA: ADODB.Stream.LoadFromFile() → parse → SOBRESCREVE LctosTratados
     → Kill C:\Temp\extratores_output.json
```

## 4b. FLUXO TARGET (pós-tasks)

```
[botão Excel] → ModComum.ProcessarExtrator()
  └─ WScript.Shell.Exec()
     python.exe script.py --cliente X --input-dir Y [--password Z]
     → Python: pdf_decrypt.descriptografar(pdf_path, password)  [zero disco]
              → json.dumps(envelope) → sys.stdout
     → VBA: jsonStr = oExec.StdOut.ReadAll
            errStr  = oExec.StdErr.ReadAll
            if ExitCode<>0: MsgBox errStr → Exit Sub
            parse jsonStr → checa "avisos" → MsgBox se não vazio
            → APPEND em LctosTratados
```

---

## 5. SCHEMA JSON TARGET

```json
{
  "id_lote": "MP-20260428-143022",
  "data_processamento": "2026-04-28T14:30:22",
  "emissor": "mercadopago|santander",
  "cliente": "NOME-CLIENTE",
  "avisos": [],
  "lancamentos": [
    {
      "cliente": "NOME-CLIENTE",
      "id_lote": "MP-20260428-143022",
      "arquivo": "fatura.pdf",
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

Regras:
- `id_lote` formato `{EMISSOR}-{YYYYMMDD}-{HHMMSS}` — NÃO usar UUID4
- `avisos` sempre presente (lista vazia = execução limpa)
- `arquivo` = path.name apenas, SEM caminho absoluto
- `parcela` = null quando não parcelado

---

## 6. SCHEMA ABA LctosTratados (target)

| Col | Campo JSON | Tipo Excel |
|-----|-----------|------------|
| A | cliente | String |
| B | id_lote | String |
| C | arquivo | String (path.name só) |
| D | vencimento | Date serial (CDate) |
| E | descricao | String (sem parcela embutida) |
| F | parcela | String ou vazio |
| G | valor | Double |
| H | tipo | String |
| I | titular_cartao | String |

**Modo escrita: APPEND acumulativo** — nunca deletar linhas existentes.
Rollback: deletar todas linhas onde Col B = id_lote a reverter.

Migração automática (VBA antes de gravar):
- A1 <> "Cliente" → renomear aba para LctosTratados_legado, criar nova com cabeçalho
- A1 = "Cliente" → prosseguir append

---

## 7. CREDENCIAIS

| Item | Estado |
|------|--------|
| Armazenamento | Aba Senhas do xlsm — texto claro |
| Santander | CPF/CNPJ do titular |
| Mercado Pago | "ND" |
| Uso atual | MANUAL — operador lê e informa via --password |
| Integração | Via src/pdf_decrypt.py (pendente TASK-07) — in-memory, zero disco |
| BR-08 status | CONFORME para MVP (operador único = proprietário AZ) |
| Gatilho violação | Qualquer distribuição a terceiros |

---

## 8. TASKS — SPEC DE IMPLEMENTAÇÃO

### TASK-01 — CLI e Estrutura de Lote (BR-03)
Arquivos: src/cartao_mercadopago.py + src/cartao_santander.py

```python
# REMOVER este padrão:
for pdf_path in pdfs:
    try:
        lancamentos = processar_pdf(pdf_path)
        todos.extend(lancamentos)
    except Exception as e:
        erros.append(f"{pdf_path.name}: {e}")  # continua — viola BR-03

# SUBSTITUIR por:
for pdf_path in pdfs:
    lancamentos = processar_pdf(pdf_path)  # exception propaga → sys.exit(1)
    todos.extend(lancamentos)
```

Critério: qualquer PDF falho → sys.exit(1) + stderr → zero dados gravados.

---

### TASK-02 — Envelope JSON (BR-02+BR-04)
Arquivos: src/cartao_mercadopago.py + src/cartao_santander.py

```python
import argparse, sys, json
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input-dir', required=True)
parser.add_argument('--cliente', required=True)
parser.add_argument('--password', default='')
args = parser.parse_args()

avisos = []
input_path = Path(args.input_dir)
if input_path.name != args.cliente:
    avisos.append(f"AVISO: Nome da pasta ({input_path.name}) diverge do --cliente ({args.cliente}). Verifique isolamento de dados.")

pdfs = list(input_path.glob('*.pdf'))

ts = datetime.now()
emissor = "mercadopago"  # ou "santander"
envelope = {
    "id_lote": f"{emissor.upper()[:2]}-{ts.strftime('%Y%m%d-%H%M%S')}",
    "data_processamento": ts.isoformat(timespec='seconds'),
    "emissor": emissor,
    "cliente": args.cliente,
    "avisos": avisos,
    "lancamentos": todos_lancamentos
}
print(json.dumps(envelope, ensure_ascii=False))
```

Critério:
- --cliente ou --input-dir ausentes → argparse sys.exit(2)
- Divergência pasta → aviso no JSON, processamento continua
- Zero escrita em disco

---

### TASK-03 — pikepdf in-memory via módulo compartilhado (BR-06)
Arquivo: src/cartao_santander.py

> ⚠️ TASK-03 depende de TASK-07 concluída. Após TASK-07, o padrão de uso é:

```python
from pdf_decrypt import descriptografar

source = descriptografar(pdf_path, args.password)
with pdfplumber.open(source) as doc:
    # processar
```

Não implementar lógica de descriptografia inline no extrator — delegar inteiramente a pdf_decrypt.py.

Erro de senha → sys.exit(1) + print(str(e), file=sys.stderr)  
Critério: zero PDFs descriptografados em disco.  
RISCO ACEITO MVP: senha em texto claro via CLI (BR-08 exceção MVP).

---

### TASK-04 — Regex Parcela (BR-estrutural)
Arquivos: src/cartao_mercadopago.py + src/cartao_santander.py

CRÍTICO: regex É específica por emissor. NÃO usar regex genérica. A lógica já existe em cada script — extrair para campo separado apenas.

```python
# Exemplo estrutural (validar regex real de cada emissor antes de alterar):
import re
match = re.search(r'\s+(\d{2}/\d{2})$', descricao_raw)
if match:
    parcela = match.group(1)
    descricao = descricao_raw[:match.start()].strip()
else:
    parcela = None
    descricao = descricao_raw.strip()
```

Testar com mínimo 2 casos por emissor (1 parcelado + 1 não parcelado) antes de commitar.  
Critério: Col E = descricao limpa; Col F = parcela ou null.

---

### TASK-05 — VBA Exec() + Fail-Fast (BR-03+BR-06)
Arquivo: vba/ModComum.bas

```vba
Dim oShell As Object, oExec As Object
Dim jsonStr As String, errStr As String

Set oShell = CreateObject("WScript.Shell")
Set oExec = oShell.Exec("cmd /c chcp 65001 > nul && """ & pythonExe & """ """ & scriptPath & """ --cliente """ & nomeCliente & """ --input-dir """ & inputDir & """")

' ORDEM OBRIGATÓRIA — previne deadlock de pipe
jsonStr = oExec.StdOut.ReadAll
errStr  = oExec.StdErr.ReadAll

If oExec.ExitCode <> 0 Then
    MsgBox "ERRO: " & errStr, vbCritical
    Exit Sub
End If

If Len(Trim(errStr)) > 0 Then
    MsgBox "Aviso técnico: " & errStr, vbExclamation
End If

' Parse JSON e checar avisos
' ... parse jsonStr via ScriptControl ou rotina nativa VBA ...
' Se envelope("avisos") não vazio → MsgBox com avisos
' Prosseguir gravação
```

RISCO DEADLOCK DOCUMENTADO: JSON > ~4KB trava pipe. Mitigação: StdOut.ReadAll SEMPRE antes de ExitCode.  
Critério: C:\Temp\extratores_output.json nunca criado.

---

### TASK-06 — Schema + Gravação Excel
Arquivo: vba/ModComum.bas

```vba
' Migração automática
Dim ws As Worksheet
Set ws = ThisWorkbook.Sheets("LctosTratados")
If ws.Cells(1,1).Value <> "Cliente" Then
    ws.Name = "LctosTratados_legado"
    ' criar nova aba LctosTratados com cabeçalho
    ' [A]Cliente [B]ID_Lote [C]Arquivo Origem [D]Data Vencimento
    ' [E]Descrição [F]Parcela [G]Valor (R$) [H]Tipo [I]Titular - Cartão
End If

' APPEND — nunca deletar linhas
Dim lastRow As Long
lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row + 1

' Iterar lancamentos do JSON e gravar A→I
' Col D: ws.Cells(r, 4).Value = CDate(lancamento("vencimento"))
' Col G: ws.Cells(r, 7).Value = CDbl(lancamento("valor"))
```

Critério:
- Execuções acumulam (não sobrescrevem)
- Col C = path.name sem caminho absoluto
- Col D = serial date Excel (CDate), não string

---

### TASK-07 — Módulo Compartilhado pdf_decrypt (BR-06)
Arquivo: src/pdf_decrypt.py (novo)

```python
import io
from pathlib import Path

def descriptografar(pdf_path: Path, password: str):
    """Retorna BytesIO (descriptografado in-memory) ou Path original se sem senha."""
    if not password:
        return pdf_path
    import pikepdf
    try:
        with pikepdf.open(pdf_path, password=password) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            buf.seek(0)
        return buf
    except Exception as e:
        import sys
        print(f"ERRO: falha ao descriptografar {pdf_path.name}: {e}", file=sys.stderr)
        sys.exit(1)
```

Uso em qualquer extrator:
```python
from pdf_decrypt import descriptografar
source = descriptografar(pdf_path, args.password)
with pdfplumber.open(source) as doc: ...
```

Critério:
- Módulo importável por qualquer extrator do projeto
- Extratores não contêm lógica de descriptografia própria
- Zero PDFs descriptografados em disco
- Erro de senha: ExitCode=1, mensagem legível no stderr
- --password permanece em todos os extratores (transparente para VBA)

---

## 9. DECISÕES LOCKED — NÃO ALTERAR

| ID | Decisão |
|----|---------|
| A1 | pikepdf in-memory via io.BytesIO — zero disco |
| A2 | VBA→Python via WScript.Shell.Exec(), stdout |
| A3 | sys.exit(1) em erro → VBA aborta sem gravar |
| A4 | Pasta input/NOME_CLIENTE/ por cliente |
| A5 | --cliente obrigatório → col A schema |
| A6 | parcela separado via regex por emissor |
| A7 | Schema JSON ordenado: identificadores (A,B) → dados (C→I) |
| A8 | requirements.txt commitado |
| A9 | Commits sem nomes de clientes, CPFs, dados sensíveis (repo público) |
| A10 | Validação cruzada pasta/cliente não-fatal → aviso em "avisos" |
| A11 | Modo escrita APPEND + rollback por id_lote |
| A12 | id_lote = {EMISSOR}-{YYYYMMDD}-{HHMMSS} (não UUID) |
| A13 | Descriptografia centralizada em src/pdf_decrypt.py — nenhum extrator contém lógica própria de abertura de PDF protegido |

---

## 10. PROTOCOLO DE EXECUÇÃO

1. Uma TASK por vez
2. Testar com PDF real antes de avançar
3. Commit atômico após sucesso: mensagem genérica, sem dados sensíveis
4. Se testes quebrarem → não avançar, corrigir primeiro
5. Início de sessão: injetar este checkpoint como contexto

---

## META
repo: https://github.com/AZResultados/Extratores
versão: 0.5-MVP
próxima ação: TASK-01 em Claude Code
gerado: 2026-04-28 | fonte: Design_Doc_1557 + Tasks_1530 + SnapShot_0100 + Checkpoint_0444

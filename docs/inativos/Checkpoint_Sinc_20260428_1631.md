# CHECKPOINT_SINC — Extratores AZ Resultados
v0.5-MVP | 2026-04-28 | Para: Claude Code

**Revisão:** v4 — adição Seção 11 (Riscos de Migração Docker/Linux), NFR-03, A15  
**Fonte da verdade:** este documento prevalece sobre Checkpoint_Sinc_20260428_1614.md

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
| TASK-08 ScriptControl substitui parser JSON | CONCLUÍDA ✓ |

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
│   ├── pdf_decrypt.py
│   ├── cartao_mercadopago.py
│   └── cartao_santander.py
├── vba/
│   ├── ModComum.bas    (ScriptControl — TASK-08 concluída)
│   ├── ModMP.bas
│   └── ModSantander.bas
└── docs/
    ├── SDD/
    │   ├── Requiriments_20260428_1631.md
    │   ├── Design_Doc_20260428_1631.md
    │   └── Tasks_20260428_1622.md
    ├── _SnapShot_Tecnico_20260428_0100.md
    └── Checkpoint_Sinc_20260428_*.md

Fora do repo:
C:\Users\[operador]\OneDrive\Documentos\Automações\Extratores.xlsm
  Abas: LctosTratados | Config (oculta) | Senhas (a remover após migração para env var)
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
     python.exe script.py --cliente X --input-dir Y
     → Python: lê senha de env var EXTRATOR_SENHA_SANTANDER
              → pdf_decrypt.descriptografar(pdf_path, password)  [zero disco]
              → json.dumps(envelope) → sys.stdout
     → VBA: jsonStr = oExec.StdOut.ReadAll
            errStr  = oExec.StdErr.ReadAll
            if ExitCode<>0: MsgBox errStr → Exit Sub
            ScriptControl → parse jsonStr → checa "avisos" → MsgBox se não vazio
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

| Col | Campo JSON | Tipo Excel | Tipo DB (futuro) |
|-----|-----------|------------|-----------------|
| A | cliente | String | VARCHAR |
| B | id_lote | String | VARCHAR |
| C | arquivo | String (path.name só) | VARCHAR |
| D | vencimento | Date serial (CDate) | DATE |
| E | descricao | String (sem parcela embutida) | VARCHAR |
| F | parcela | String ou vazio | VARCHAR NULL |
| G | valor | Double | DECIMAL(10,2) |
| H | tipo | String | VARCHAR |
| I | titular_cartao | String | VARCHAR |

**Modo escrita: APPEND acumulativo** — nunca deletar linhas existentes.
Rollback: deletar todas linhas onde Col B = id_lote a reverter.

---

## 7. CREDENCIAIS

| Item | Estado |
|------|--------|
| Armazenamento atual | Aba Senhas do xlsm — texto claro (a migrar) |
| Target | Variável de ambiente do usuário Windows (`EXTRATOR_SENHA_SANTANDER`) |
| Santander | CPF/CNPJ do titular |
| Mercado Pago | Sem senha |
| Integração Python | `os.environ.get('EXTRATOR_SENHA_SANTANDER')` (pendente implementação) |
| BR-08 status | CONFORME para MVP (operador único = proprietário AZ) |
| Gatilho violação | Qualquer distribuição a terceiros |
| Próxima evolução | `keyring` (Windows Credential Manager) antes de multi-usuário |

---

## 8. TASKS — SPEC DE IMPLEMENTAÇÃO

Ver `docs/SDD/Tasks_20260428_1622.md` para spec completa de cada task.

TASK-08 (ScriptControl) — **CONCLUÍDA** em 2026-04-28. `vba/ModComum.bas` atualizado.

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
| A13 | Descriptografia centralizada em src/pdf_decrypt.py |
| A14 | VBA é camada temporária — lógica em Python; VBA no VBA = retrabalho na migração (NFR-01) |
| A15 | Credenciais via env var — nunca hardcoded, nunca em planilha (target: `EXTRATOR_SENHA_SANTANDER`) |

---

## 10. PROTOCOLO DE EXECUÇÃO

1. Uma TASK por vez
2. Testar com PDF real antes de avançar
3. Commit atômico após sucesso: mensagem genérica, sem dados sensíveis
4. Se testes quebrarem → não avançar, corrigir primeiro
5. Início de sessão: injetar este checkpoint como contexto

---

## 11. RISCOS DE MIGRAÇÃO DOCKER/LINUX

Esta seção mapeia os problemas concretos na migração do MVP (Windows/Excel) para o ambiente de produção (Docker/Linux + banco de dados). Registrado aqui para que nenhuma decisão de código tome o caminho errado antes da migração.

### 11.1 Componentes não-portáveis (bloqueantes)

| Componente | Problema | Ação na migração |
|---|---|---|
| VBA/Excel inteiro | Não executa em Linux | Substituir por conector de banco (planejado — NFR-01) |
| `WScript.Shell.Exec()` | API Windows-only | Some com a remoção do VBA |
| `MSScriptControl` | COM 32-bit Windows-only | Some com a remoção do VBA |
| `CDate()` / serial Excel | Tipo de data Excel-specific | Banco recebe campo `DATE` nativo do JSON ISO |
| Aba `Config` / `Senhas` | Configuração dentro do Excel | Substituir por env vars + arquivo de config externo |

### 11.2 Dependências de sistema (ajuste no Dockerfile)

| Dependência | Problema | Mitigação |
|---|---|---|
| `pikepdf` | Requer `libqpdf` instalado no SO | `RUN apt-get install -y libqpdf-dev` no Dockerfile |
| `pdfplumber` | Pode precisar de `libpoppler` em alguns layouts | `RUN apt-get install -y poppler-utils` (verificar) |
| Python 3.13 | Imagem base pode não ter | `FROM python:3.13-slim` como base |

### 11.3 Portabilidade de código Python (baixo risco)

| Ponto | Situação | Observação |
|---|---|---|
| `pathlib.Path()` | ✅ cross-platform | Já usado — não usar strings de caminho Windows |
| Separador decimal | ✅ resolvido | `json.dumps` emite `.` — ScriptControl já tratava isso; banco não tem problema |
| Encoding UTF-8 | ✅ sem risco | Scripts não dependem de `chcp 65001` — isso era artefato do cmd VBA |
| Env vars | ✅ mesmo conceito | `os.environ.get()` funciona igual em Windows e Linux |
| Caminhos de input | ⚠️ atenção | `--input-dir` já é arg CLI; em Docker será volume mount — sem mudança no código |
| Timezone / datas | ⚠️ verificar | `datetime.now()` usa timezone do SO — container deve ter `TZ=America/Sao_Paulo` |

### 11.4 O que NÃO muda na migração

- Os scripts Python (`cartao_*.py`, `pdf_decrypt.py`) — zero alteração de código
- O envelope JSON — é o contrato de interface; permanece idêntico
- O schema de campos A→I — mapeia diretamente para colunas de tabela de banco
- Os exit codes (0 = sucesso, 1 = erro fatal, 2 = arg inválido) — padrão Unix, perfeito para Docker

### 11.5 Dockerfile mínimo de referência (pós-MVP)

```dockerfile
FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    libqpdf-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV TZ=America/Sao_Paulo

ENTRYPOINT ["python", "src/cartao_mercadopago.py"]
```

> ⚠️ O `ENTRYPOINT` acima é para um extrator específico. Em produção, o orquestrador (ex: script shell, Airflow, cron) chamará o extrator correto com os argumentos adequados.

---

## META
repo: https://github.com/AZResultados/Extratores
versão: 0.5-MVP
próxima ação: TASK-01 em Claude Code
gerado: 2026-04-28 | fonte: Design_Doc_1631 + Tasks_1622 + SnapShot_0100 + Checkpoint_1614

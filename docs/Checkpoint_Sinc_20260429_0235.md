# CHECKPOINT_SINC — Extratores AZ Resultados
v1.5-MVP | 2026-04-29 | Para: Claude Code

**Revisão:** v6 — corrige fluxo de senha (Seção 4), remove python-dateutil, ajusta diagrama repo  
**Fonte da verdade:** este documento prevalece sobre Checkpoint_Sinc_20260429_0148.md

---

## 1. STATUS

| Item | Estado |
|------|--------|
| Repo | PUBLIC https://github.com/AZResultados/Extratores |
| Branch | main |
| Extratores prod | extrator.py (entry point único) + cartao_mercadopago.py + cartao_santander.py |
| Interface | Extratores.xlsm (a montar — módulos VBA prontos) |
| requirements.txt | RESOLVIDO ✓ |
| TASK-01 a TASK-13 | CONCLUÍDAS ✓ |
| Próxima ação | Montar xlsm e testar com PDFs reais |

---

## 2. STACK

```
Python          3.13.7  venv: C:\Dev\projetos\Extratores\venv\
pdfplumber      0.11.9
pikepdf         10.5.1
VBA             Excel 365
Git             public repo AZResultados/Extratores
```

---

## 3. ESTRUTURA REPO

```
AZResultados/Extratores/
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   ├── extrator.py             (entry point único de produção)
│   ├── pdf_router.py           (detecta emissor por fingerprint)
│   ├── pdf_decrypt.py          (descriptografia in-memory)
│   ├── db_senha.py             (banco de senhas SQLite)
│   ├── db_cliente.py           (cadastro de clientes SQLite)
│   ├── setup_senha.py          (CLI gestão de senhas)
│   ├── setup_cliente.py        (CLI gestão de clientes)
│   ├── cartao_mercadopago.py
│   └── cartao_santander.py
├── vba/
│   ├── ModConfig.bas           (BASE_DIR — único ponto de configuração de caminhos)
│   ├── ModComum.bas            (ProcessarExtrator + utilitários)
│   ├── ModProcessar.bas        (botão Processar)
│   ├── ModClientes.bas         (cadastro de clientes)
│   └── ModSenhas.bas           (cadastro de senhas PDF)
└── docs/
    ├── SDD/
    │   ├── Requiriments_20260428_1631.md
    │   ├── Design_Doc_20260429_0148.md      ← atual
    │   └── Tasks_20260428_1821.md
    ├── Esquema_LctosTratados_20260429_0148.md  ← atual
    └── Checkpoint_Sinc_20260429_0235.md     ← este arquivo

Fora do repo (local only):
  vba/Inativos/               — ModMP.bas, ModSantander.bas obsoletos
  docs/Inativos/              — versões anteriores deste checkpoint
  docs/SDD/Inativos/          — versões anteriores de Design Docs e Tasks

Fora do repo (operador):
  C:\Users\[operador]\OneDrive\Documentos\Automações\Extratores.xlsm
    Aba: LctosTratados (única necessária)
  C:\Users\[operador]\.extratores\dados.db   — banco SQLite de senhas e clientes
```

---

## 4. FLUXO ATUAL (v1.5 — implementado)

```
[botão Processar] → ModProcessar.Processar()
  └─ SelecionarCliente() → setup_cliente.py list → InputBox número
  └─ SelecionarPasta()   → BrowseForFolder a partir de base_dir do cliente
  └─ ProcessarExtrator(cliente, inputDir)
       └─ WScript.Shell.Exec()
            cmd /c python.exe extrator.py --cliente X --input-dir Y
            oExec.StdIn.Close  ← stdin fechado imediatamente; extrator.py não lê stdin
            → Python: pdf_router.rotear(pdf_path, cliente)
                     → tenta abrir sem senha
                     → se protegido: cicla senhas via db_senha.get_todas_senhas(cliente)
                       (senhas lidas do SQLite interno — nao passadas pelo VBA)
                     → detecta emissor por fingerprint de texto
                     → processar_arquivo(pdf_path, source)
                     → json.dumps(envelope) → sys.stdout
            → VBA: jsonStr = oExec.StdOut.ReadAll (bloqueia até término)
                   errStr  = oExec.StdErr.ReadAll
                   if ExitCode<>0: MsgBox errStr → Exit Sub
                   On Error GoTo ErroParse (cobre parse + gravação)
                   ScriptControl → parse jsonStr → checa "avisos" → MsgBox
                   → APPEND em LctosTratados (13 colunas)

[botão Cadastrar Senha] → ModSenhas.CadastrarSenhaPDF()
  └─ SelecionarCliente() → InputBox senha
  └─ Exec: setup_senha.py add <cliente> --stdin
           oExec.StdIn.WriteLine senha  ← única vez que stdin entrega senha ao Python
           oExec.StdIn.Close
```

---

## 5. SCHEMA JSON (v2.0 — implementado)

```json
{
  "id_lote": "SA-20260429-023500",
  "data_processamento": "2026-04-29T02:35:00",
  "emissor": "santander|mercadopago|multi",
  "cliente": "NOME-CLIENTE",
  "avisos": [],
  "lancamentos": [
    {
      "cliente":            "NOME-CLIENTE",
      "id_lote":            "SA-20260429-023500",
      "arquivo":            "fatura.pdf",
      "titular":            "NOME TITULAR",
      "final_cartao":       "1234",
      "tipo":               "Compra parcelada",
      "data_compra":        "15/02/2026",
      "descricao":          "SUPERMERCADO XYZ",
      "parcela_num":        2,
      "qtde_parcelas":      6,
      "vencimento":         "10/05/2026",
      "descricao_adaptada": "SUPERMERCADO XYZ parc 2/6 15/02/2026",
      "valor":              -289.42
    }
  ]
}
```

Regras:
- `id_lote` formato `{EMISSOR}-{YYYYMMDD}-{HHMMSS}` — NÃO usar UUID
- `emissor` = `"multi"` quando pasta mista
- `avisos` sempre presente (lista vazia = execução limpa)
- `arquivo` = path.name apenas, SEM caminho absoluto
- `data_compra` = null quando impossível inferir
- `parcela_num` / `qtde_parcelas` = 0 para não parcelados

---

## 6. SCHEMA ABA LctosTratados (v2.0 — 13 colunas)

| Col | Campo JSON         | Tipo Excel         | Tipo DB (futuro)  |
|-----|--------------------|--------------------|-------------------|
| A   | cliente            | String             | VARCHAR           |
| B   | id_lote            | String             | VARCHAR           |
| C   | arquivo            | String (Path.name) | VARCHAR           |
| D   | titular            | String             | VARCHAR           |
| E   | final_cartao       | String (4 chars)   | CHAR(4)           |
| F   | tipo               | String             | VARCHAR           |
| G   | data_compra        | Date dd/mm/yyyy    | DATE NULL         |
| H   | descricao          | String             | VARCHAR           |
| I   | parcela_num        | Inteiro (0=N/A)    | SMALLINT          |
| J   | qtde_parcelas      | Inteiro (0=N/A)    | SMALLINT          |
| K   | vencimento         | Date dd/mm/yyyy    | DATE              |
| L   | descricao_adaptada | String             | VARCHAR           |
| M   | valor              | Double             | DECIMAL(10,2)     |

**Modo escrita: APPEND acumulativo** — nunca deletar linhas existentes.  
Rollback: deletar todas as linhas onde Col B = id_lote a reverter.

Schema completo com regras: `docs/Esquema_LctosTratados_20260429_0148.md`

---

## 7. CREDENCIAIS

| Item | Estado |
|------|--------|
| Armazenamento | SQLite local `~/.extratores/dados.db`, schema `(cliente, senha)` |
| Entrega ao Python | `setup_senha.py` recebe via stdin; `extrator.py` lê do SQLite diretamente |
| Santander | Senha cadastrada via botão [Cadastrar Senha] no xlsm |
| Mercado Pago | PDF sem senha; `get_todas_senhas()` retorna lista vazia |
| BR-08 status | CONFORME para MVP (operador único = proprietário AZ) |
| Gatilho violação | Qualquer distribuição a terceiros |
| Próxima evolução | Criptografia da coluna senha no banco antes de multi-usuário |

---

## 8. TASKS — SPEC DE IMPLEMENTAÇÃO

TASK-01 a TASK-13 — **todas CONCLUÍDAS** em 2026-04-28/29.  
Ver `docs/SDD/Tasks_20260428_1821.md` para spec completa.

---

## 9. DECISÕES LOCKED — NÃO ALTERAR

| ID | Decisão |
|----|---------|
| A1 | pikepdf in-memory via io.BytesIO — zero disco |
| A2 | VBA→Python via WScript.Shell.Exec(), stdout |
| A3 | sys.exit(1) em erro → VBA aborta sem gravar |
| A4 | Pasta input/NOME_CLIENTE/ por cliente |
| A5 | --cliente obrigatório → col A schema |
| A6 | parcela_num e qtde_parcelas como inteiros separados (0 = não parcelado) |
| A7 | Schema JSON ordenado: identificadores → dados → valor |
| A8 | requirements.txt commitado |
| A9 | Commits sem nomes de clientes, CPFs, dados sensíveis (repo público) |
| A10 | Validação cruzada pasta/cliente não-fatal → aviso em "avisos" |
| A11 | Modo escrita APPEND + rollback por id_lote |
| A12 | id_lote = {EMISSOR}-{YYYYMMDD}-{HHMMSS} (não UUID) |
| A13 | Descriptografia centralizada em src/pdf_decrypt.py |
| A14 | VBA é camada temporária — lógica em Python; VBA no VBA = retrabalho na migração (NFR-01) |
| A15 | Credenciais via banco SQLite local — nunca hardcoded, nunca em planilha |
| A16 | Senhas armazenadas em SQLite `~/.extratores/dados.db`; entregues via stdin apenas ao setup_senha.py |
| A17 | Router detecta emissor por fingerprint de texto — nunca pela senha que abriu o PDF |
| A18 | extrator.py é o único entry point de produção; extratores expostos via processar_arquivo() |
| A19 | Schema v2: titular e final_cartao como campos separados — nunca concatenados |
| A20 | Schema v2: parcela_num e qtde_parcelas como inteiros (0 = não parcelado) |
| A21 | Schema v2: data_compra inferida em Python (NFR-01) — pode ser null |
| A22 | Schema v2: descricao_adaptada montada em Python (NFR-01) — VBA grava, nunca monta |
| A23 | Tipo "Ajuste" removido do domínio — absorvido por "Outros" |

---

## 10. PROTOCOLO DE EXECUÇÃO

1. Testar com PDF real após montar o xlsm
2. Commit atômico após cada mudança: mensagem genérica, sem dados sensíveis
3. Se testes quebrarem → corrigir antes de avançar
4. Início de sessão: injetar este checkpoint como contexto

---

## 11. RISCOS DE MIGRAÇÃO DOCKER/LINUX

### 11.1 Componentes não-portáveis (bloqueantes)

| Componente | Problema | Ação na migração |
|---|---|---|
| VBA/Excel inteiro | Não executa em Linux | Substituir por conector de banco (planejado — NFR-01) |
| `WScript.Shell.Exec()` | API Windows-only | Some com a remoção do VBA |
| `MSScriptControl` | COM 32-bit Windows-only | Some com a remoção do VBA |
| `CDate()` / serial Excel | Tipo de data Excel-specific | Banco recebe campo `DATE` nativo do JSON ISO |
| SQLite local `dados.db` | Caminho Windows-specific | Parametrizar via env var `EXTRATORES_DB` (já suportado) |

### 11.2 Dependências de sistema (ajuste no Dockerfile)

| Dependência | Problema | Mitigação |
|---|---|---|
| `pikepdf` | Requer `libqpdf` instalado no SO | `RUN apt-get install -y libqpdf-dev` no Dockerfile |
| `pdfplumber` | Pode precisar de `libpoppler` em alguns layouts | `RUN apt-get install -y poppler-utils` (verificar) |
| Python 3.13 | Imagem base pode não ter | `FROM python:3.13-slim` como base |

### 11.3 Portabilidade de código Python (baixo risco)

| Ponto | Situação | Observação |
|---|---|---|
| `pathlib.Path()` | ✅ cross-platform | Já usado |
| Separador decimal | ✅ resolvido | `json.dumps` emite `.` |
| Encoding UTF-8 | ✅ sem risco | Scripts não dependem de `chcp 65001` |
| Env vars | ✅ mesmo conceito | `os.environ.get()` funciona igual |
| Caminhos de input | ⚠️ atenção | `--input-dir` já é arg CLI; em Docker será volume mount |
| Timezone / datas | ⚠️ verificar | Container deve ter `TZ=America/Sao_Paulo` |

### 11.4 O que NÃO muda na migração

- Os scripts Python (`cartao_*.py`, `pdf_decrypt.py`, `pdf_router.py`, `extrator.py`) — zero alteração de código
- O envelope JSON — é o contrato de interface; permanece idêntico
- O schema de campos A→M — mapeia diretamente para colunas de tabela de banco
- Os exit codes (0 = sucesso, 1 = erro fatal) — padrão Unix, perfeito para Docker

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

ENTRYPOINT ["python", "src/extrator.py"]
```

---

## META

repo: https://github.com/AZResultados/Extratores  
versão: 1.5-MVP  
próxima ação: Montar xlsm e testar com PDFs reais  
gerado: 2026-04-29 | fonte: Design_Doc_20260429_0148 + Tasks_20260428_1821 + Checkpoint_20260429_0148

# CHECKPOINT_SINC — Extratores AZ Resultados
**v1.7-MVP | 2026-05-05 | Para: Claude Code**  
**Fonte da verdade:** prevalece sobre Checkpoint_Sinc_20260429_1530.md

---

## 1. STATUS

| Item | Estado |
|------|--------|
| Repo | PUBLIC https://github.com/AZResultados/Extratores |
| Branch | main |
| Extratores prod | extrator.py + cartao_mercadopago.py + cartao_santander.py + cartao_samsung.py + extrator_nubank_rdb.py |
| Interface | Extratores.xlsm testado — VBA compatível com nubank_rdb sem alterações |
| TASK-01 a TASK-17 | CONCLUÍDAS ✓ |
| Testes | 65 testes — 100% passando (cobertura nubank_rdb sem testes automatizados ainda) |
| Design Doc ativo | `docs/SDD/Design_Doc_20260505_1336.md` (v1.7 / revisão v9) |
| Tasks ativo | `docs/SDD/Tasks_20260505_1338.md` (v16) |
| **Próxima ação** | **Implementar extrator Itaú cartão de crédito** |

---

## 2. STACK

```
Python       3.13.7  venv: C:\Dev\projetos\Extratores\venv\
pdfplumber   0.11.9
pikepdf      10.5.1
VBA          Excel 365
pytest       9.0.3 / pytest-mock 3.15.1
```

---

## 3. EXTRATOR NUBANK RDB — DECISÕES LOCKED

| ID  | Decisão |
|-----|---------|
| N1  | `tipo` usa apenas `"Entrada"` ou `"Saída"` (distinto de cartões) |
| N2  | `"Resgate RDB"` usa **Saldo Líquido** como valor — não Valor Bruto |
| N3  | IR e IOF são lançamentos separados (`"IR s/ Resgate RDB"`, `"IOF s/ Resgate RDB"`) |
| N4  | `saldo_líquido + IR + IOF = valor_bruto` — invariante de parsing |
| N5  | Parser linha a linha com `pendente` como máquina de estado (movimentações multilinhas) |
| N6  | Validação per-row sempre ativa; validação de saldo requer `--saldo-abertura` |
| N7  | Saldo de abertura **não** está no PDF — deve ser fornecido via CLI |
| N8  | `final_cartao = None` (JSON `null`) → VBA já trata como string vazia |
| N9  | Fingerprint: `["RDB Resgate Imediato", "Caixinhas PJ"]` |
| N10 | `id_lote` prefix: `"NRD"` |
| N11 | `processar_arquivo(pdf_path, source, saldo_abertura=None)` — saldo_abertura opcional |
| N12 | PDF sem senha — `--password` aceito mas ignorado |

---

## 4. PRÓXIMO EXTRATOR — Itaú Cartão de Crédito

### 4.1 Contexto

O Itaú gerencia a operação do cartão Samsung. A fatura Itaú é descrita como muito similar à fatura Samsung (`cartao_samsung.py`). Ponto de partida: usar `cartao_samsung.py` como base e identificar diferenças de layout/fingerprint.

### 4.2 Referência Samsung — constantes e padrões confirmados

```python
X_DIV = 330          # gap coluna esq/dir (Samsung/Itaú — NÃO usar 250 do Santander)
RE_DATA  = re.compile(r"^\d{2}/\d{2}$")
RE_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
RE_PARC  = re.compile(r"^(\d{2})/(\d{2})$")
RE_TITUL = re.compile(r"Titular\s+([A-Z][A-Z\s]+)")
RE_CART  = re.compile(r"Cartão\s+\d{4}\.XXXX\.XXXX\.(\d{4})")
RE_VENC  = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})")
```

### 4.3 Diferenças conhecidas vs Samsung

| Aspecto | Samsung | Itaú (hipótese — confirmar no PDF) |
|---|---|---|
| Fingerprint | `"App Samsung Itaú"` | A definir (ex.: `"Fatura Itaú"`) |
| `emissor` | `"samsung"` | `"itau"` (proposto) |
| `id_lote` prefix | `SM-` | `IT-` (proposto) |
| Layout colunas | `X_DIV = 330` | Provavelmente igual — confirmar |
| Seções | Pagamentos / Lançamentos / Internacionais / Próximas | Provavelmente igual — confirmar |
| Titular/Cartão | regex pág. 1 | Provavelmente igual — confirmar |

> **Antes de implementar:** extrair texto do PDF real para confirmar fingerprint, X_DIV e seções.

### 4.4 Protocolo de execução sugerido

1. Injetar este checkpoint no início da sessão
2. Extrair e analisar texto do PDF Itaú real com pdfplumber
3. Comparar com Samsung linha a linha — identificar delta mínimo
4. Implementar `src/cartao_itau.py` (cópia adaptada de `cartao_samsung.py`)
5. Registrar fingerprint em `src/pdf_router.py`
6. Registrar em `src/extrator.py` (EXTRATORES + PREFIXOS_LOTE)
7. Atualizar Design Doc + Tasks
8. Commit atômico

---

## 5. DECISÕES LOCKED ANTERIORES

Ver lista completa A1–A27 em `docs/Inativos/Checkpoint_Sinc_20260429_1110.md`.  
Adicionais Samsung (S1–S7) em `docs/Inativos/Checkpoint_Sinc_20260429_1530.md`.  
Adicionais Nubank RDB (N1–N12): seção 3 acima.

---

## 6. ESTRUTURA DE ARQUIVOS RELEVANTE

```
src/
  extrator.py               — entry point único; EXTRATORES + PREFIXOS_LOTE
  pdf_router.py             — FINGERPRINTS por emissor
  cartao_mercadopago.py
  cartao_santander.py
  cartao_samsung.py
  extrator_nubank_rdb.py    — standalone + processar_arquivo()
  pdf_decrypt.py
  logger.py
  db_senha.py / db_cliente.py
docs/SDD/
  Design_Doc_20260505_1336.md   — v1.7 / revisão v9 (fonte da verdade)
  Tasks_20260505_1338.md        — v16 (fonte da verdade)
PDFs de teste (sem senha):
  C:\Users\jwcos\OneDrive - Azmid\Documentos\Automações\Extrator\PDFsTeste\SemSenha\
```

---

*Gerado: 2026-05-05 | Claude Sonnet 4.6*

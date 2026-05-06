# CHECKPOINT_SINC — Extratores AZ Resultados
**v1.7-MVP | 2026-05-06 02:36 | Para: Claude Code**  
**Fonte da verdade:** prevalece sobre Checkpoint_Sinc_20260505_1928.md

---

## 1. STATUS

| Item | Estado |
|------|--------|
| Repo | PUBLIC https://github.com/AZResultados/Extratores |
| Branch | main |
| Extratores prod | extrator.py + cartao_mercadopago.py + cartao_santander.py + cartao_samsung.py + cartao_itau_personnalite.py + extrator_nubank_rdb.py |
| Interface | Extratores.xlsm — sem alterações VBA necessárias para Itaú |
| TASK-01 a TASK-17 | CONCLUÍDAS ✓ |
| TASK-IT-01 | ✅ CONCLUÍDA — recon PDF; fingerprint I4 revisado |
| TASK-IT-02 | ✅ CONCLUÍDA — `src/cartao_itau_personnalite.py` implementado |
| TASK-IT-03 | ✅ CONCLUÍDA — fingerprint registrado em `pdf_router.py` |
| TASK-IT-04 | ✅ CONCLUÍDA — extrator registrado em `extrator.py` |
| TASK-IT-05 | ✅ CONCLUÍDA — 14 testes; suite completa: 93/93 passando |
| TASK-IT-06 | ✅ CONCLUÍDA — Design Doc v11, Checkpoint atualizado |
| Testes | **93 testes — 100% passando** |
| Design Doc ativo | `docs/SDD/Design_Doc_20260506_0236.md` (v1.7 / revisão v11) |
| Tasks gerais ativo | `docs/SDD/Tasks_20260505_1338.md` (v16) |
| Tasks Itaú ativo | `docs/SDD/Tasks_Itau_20260505_1928.md` (v1 — todas concluídas) |
| **Próxima ação** | **A definir** |

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

## 4. EXTRATOR ITAÚ PERSONNALITÊ — DECISÕES LOCKED

| ID  | Decisão |
|-----|---------|
| I1  | `emissor = "itau_personnalite"` |
| I2  | `id_lote` prefix: `"ITP"` |
| I3  | `X_DIV = 355` — confirmado por medição; não herdar de outros extratores |
| I4  | Fingerprint: `["40044828", "ITAUUNIBANCOHOLDING"]` — `"Personnalitê"` não existe no text layer |
| I5  | Escopo: qualquer bandeira/categoria da linha Personnalitê |
| I6  | Descriptografia via `pdf_decrypt.py` — senha no banco SQLite |
| I7  | Múltiplos titulares: rastrear `titular_ativo` / `final_cartao_ativo` por bloco; nomes com espaços |
| I8  | Seção `"Compras parceladas - próximas faturas"` ignorada em ambas as colunas ao ser detectada |
| I9  | Ajustes negativos sem parcela → `tipo = "Ajuste"` → valor = `+abs(v)` (crédito positivo) |
| I10 | Validação: `"Totaldoslançamentosatuais"` tolerância R$ 0,10; ausência = WARNING, não abort |
| I11 | `x_tolerance=1` em `extract_words()` para preservar espaços; detecção usa `''.join(tokens)` |

---

## 5. VALIDAÇÃO COM PDF REAL (fatura abril/2026)

```
Arquivo:    Livre_Fatura_MASTERCARD_100242919426_04-2026 (1).pdf
Emissor:    itau_personnalite  (detectado via pdf_router.py)
id_lote:    ITP-20260506-HHMMSS
Lançamentos: 114
Total:      R$ 17.054,69  ✅ (diff = R$ 0,00)

Blocos multi-titular:
  MONICA D KULLIAN  (final 6318) — 35 lançamentos — subtotal R$ 3.228,05
  GENNARO DI LIDDO  (final 4442) —  3 lançamentos — subtotal R$   352,83
  GENNARO DI LIDDO  (final 0374) — 76 lançamentos — subtotal R$13.473,81
```

---

## 6. DECISÕES LOCKED ANTERIORES

Ver lista completa A1–A27 em `docs/Inativos/Checkpoint_Sinc_20260429_1110.md`.  
Adicionais Samsung (S1–S7) em `docs/Inativos/Checkpoint_Sinc_20260429_1530.md`.  
Adicionais Nubank RDB (N1–N12): seção 3 acima.  
Adicionais Itaú Personnalitê (I1–I11): seção 4 acima.

---

## 7. ESTRUTURA DE ARQUIVOS RELEVANTE

```
src/
  extrator.py               — entry point único; EXTRATORES + PREFIXOS_LOTE
  pdf_router.py             — FINGERPRINTS por emissor
  cartao_mercadopago.py
  cartao_santander.py
  cartao_samsung.py
  cartao_itau_personnalite.py  ✅ implementado
  extrator_nubank_rdb.py
  pdf_decrypt.py
  logger.py
  db_senha.py / db_cliente.py
tests/
  test_itau_personnalite.py    ✅ 14 testes
docs/SDD/
  Design_Doc_20260506_0236.md   — v1.7 / revisão v11 (fonte da verdade)
  Tasks_20260505_1338.md        — v16 (fonte da verdade — tasks gerais)
  Tasks_Itau_20260505_1928.md   — v1 (todas as tasks IT concluídas)
PDFs de teste (sem senha):
  C:\Users\jwcos\OneDrive - Azmid\Documentos\Automações\Extrator\PDFsTeste\SemSenha\
```

---

*Gerado: 2026-05-06 02:36 | Claude Sonnet 4.6*

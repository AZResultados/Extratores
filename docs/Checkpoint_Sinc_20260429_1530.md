# CHECKPOINT_SINC — Extratores AZ Resultados
**v1.7-MVP | 2026-04-29 | Para: Claude Code**  
**Fonte da verdade:** prevalece sobre Checkpoint_Sinc_20260429_1110.md

---

## 1. STATUS

| Item | Estado |
|------|--------|
| Repo | PUBLIC https://github.com/AZResultados/Extratores |
| Branch | main |
| Extratores prod | extrator.py + cartao_mercadopago.py + cartao_santander.py |
| Interface | Extratores.xlsm testado — 358 lançamentos importados ✓ |
| TASK-01 a TASK-16 | CONCLUÍDAS ✓ |
| Testes | 65 testes — 100% passando |
| **Próxima ação** | **Implementar cartao_samsung.py — TASK-S01 a TASK-S09** |

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

## 3. NOVO EXTRATOR — cartao_samsung.py

### 3.1 Constantes calibradas (4 amostras reais)

```python
X_DIV = 330          # gap confirmado: col esq termina ~315, col dir começa ~351
# Santander usa X_DIV = 250 — NÃO reutilizar
```

### 3.2 Regex

```python
RE_DATA  = re.compile(r"^\d{2}/\d{2}$")
RE_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
RE_PARC  = re.compile(r"^(\d{2})/(\d{2})$")
RE_TITUL = re.compile(r"Titular\s+([A-Z][A-Z\s]+)")
RE_CART  = re.compile(r"Cartão\s+\d{4}\.XXXX\.XXXX\.(\d{4})")
RE_VENC  = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})")
```

### 3.3 Diferenças críticas vs Santander

| Aspecto | Santander | Samsung/Itaú |
|---|---|---|
| `X_DIV` | 250 | **330** |
| Titular | `NOME - XXXX XXXX XXXX 1234` inline | `Titular NOME` + `Cartão XXXX.XXXX.XXXX.1234` separados na pág. 1 |
| Extração titular | `RE_TITUL.search(txt)` no segmento | `RE_TITUL` + `RE_CART` no `texto_pagina1`; aplicar `.strip().split("\n")[0].strip()` para remover resíduo `\nC` |
| Parcela posição | token isolado antes do valor | penúltimo token embutido no nome: `NAT*Natura Pag 02/06 53,34` |
| Seção pagamento | keyword na descrição | label `"Pagamentos efetuados"` — rastrear `secao_atual` |
| Seção ignorar | N/A | `"Compras parceladas - próximas faturas"` → `continue` |
| Internacionais | N/A | Seção `"Lançamentos internacionais"` → processar igual aos nacionais (mesmo `tipo`, valor coluna R$) |
| Validação total | `(=) Saldo Desta Fatura` | `Total dos lançamentos atuais` (fallback: `Lançamentos no cartão`) |
| Tolerância | R$ 0,10 | R$ 0,10 |
| `id_lote` prefix | `SA-` | `SM-` |
| `emissor` | `"santander"` | `"samsung"` |
| Fingerprint router | texto Santander | `"App Samsung Itaú"` |
| Fusão prefixo solitário | Sim (`"2"`, `"3"`) | **Não** — não existe nas amostras |

### 3.4 Detecção de seção (CRÍTICO)

```python
SECAO_PAGAMENTOS  = "Pagamentos efetuados"
SECAO_LANCAMENTOS = "Lançamentos: compras e saques"
SECAO_INTER       = "Lançamentos internacionais"
SECAO_PROXIMAS    = "Compras parceladas - próximas faturas"

# Durante iteração de tokens:
txt_linha = " ".join(tokens)
if txt_linha in (SECAO_PAGAMENTOS, SECAO_LANCAMENTOS, SECAO_INTER, SECAO_PROXIMAS):
    secao_atual = txt_linha
    continue

if secao_atual == SECAO_PROXIMAS:
    continue  # ignorar completamente

# tipo via secao_atual:
if secao_atual == SECAO_PAGAMENTOS:
    tipo = "Pagamento"
else:
    tipo = classificar_tipo(descricao, tem_parcela)
```

### 3.5 Validação de total

```python
def validar_total(lancamentos, texto):
    m = re.search(r"Total dos lançamentos atuais\s+([\d.]+,\d{2})", texto)
    if not m:
        m = re.search(r"Lançamentos no cartão\s+([\d.]+,\d{2})", texto)
    if not m:
        return False, 0.0, 0.0
    total_pdf  = float(m.group(1).replace(".", "").replace(",", "."))
    tipos_debito = {"Compra parcelada", "Compra à vista", "Outros"}
    total_calc = sum(abs(l["valor"]) for l in lancamentos if l["tipo"] in tipos_debito)
    return abs(total_pdf - total_calc) < 0.10, total_pdf, total_calc
```

### 3.6 Totais esperados nas 4 amostras (critério de aceite)

| Amostra | Vencimento | Total PDF | Lançamentos esperados |
|---|---|---|---|
| 01/2026 | 27/01/2026 | 1.139,85 | 16 compras + 1 pagamento |
| 02/2026 | 27/02/2026 | 1.023,24 | compras + internacionais + pagamento; sem próximas |
| 03/2026 | 27/03/2026 | 1.396,74 | compras + pagamento; sem próximas |
| 04/2026 | 27/04/2026 | 1.050,75 | compras + pagamento; sem próximas |

---

## 4. TASKS — SEQUÊNCIA DE EXECUÇÃO

| Task | Arquivo | Ação resumida |
|------|---------|---------------|
| TASK-S01 | `src/cartao_samsung.py` | Estrutura base, constantes, `extrair_vencimento`, `extrair_titular`, `extrair_texto_pdf` |
| TASK-S02 | `src/cartao_samsung.py` | `extrair_segmento` com `X_DIV=330` |
| TASK-S03 | `src/cartao_samsung.py` | `inferir_ano_*`, `classificar_tipo` com `secao_atual` |
| TASK-S04 | `src/cartao_samsung.py` | `parsear_lancamentos` com detecção de seção |
| TASK-S05 | `src/cartao_samsung.py` | `validar_total` |
| TASK-S06 | `src/cartao_samsung.py` | `processar_arquivo`, `processar_pasta`, CLI `argparse` |
| TASK-S07 | `src/pdf_router.py` | Fingerprint `"App Samsung Itaú"` → `cartao_samsung` |
| TASK-S08 | `tests/test_samsung.py` | 8 testes mínimos |
| TASK-S09 | CLI (terminal) | Cadastrar senha Samsung via `setup_senha.py` |

**Spec completa:** `docs/SDD/Tasks_Samsung_20260429_1530.md`

---

## 5. DECISÕES LOCKED — NÃO ALTERAR

Ver lista completa A1–A27 no Checkpoint_Sinc_20260429_1110.md.  
Adicionais para Samsung:

| ID  | Decisão |
|-----|---------|
| S1  | `X_DIV = 330` — calibrado em 4 amostras reais |
| S2  | Ordem leitura `("e", "d")` por página — idêntica ao Santander |
| S3  | Titular extraído da pág. 1 via regex, não do segmento de lançamentos |
| S4  | Seção "próximas faturas" ignorada completamente |
| S5  | Internacionais tratados igual aos nacionais |
| S6  | `secao_atual` controla `tipo=Pagamento` — não keyword na descrição |
| S7  | Validação usa `Total dos lançamentos atuais` com fallback |

---

## 6. PROTOCOLO DE EXECUÇÃO

1. Injetar este checkpoint no início da sessão Claude Code
2. Injetar `Tasks_Samsung_20260429_1530.md` como referência de spec
3. Executar TASK-S01 → commit → TASK-S02 → commit → ... → TASK-S09
4. `pytest` completo antes de cada push — 65 testes existentes + novos devem passar
5. Testar com PDF real após TASK-S06 antes de avançar para S07

---

*Gerado: 2026-04-29 | Claude Sonnet 4.6*

# Prompt 1 — Atualização SDD: Extrator Itaú Personnalitê
**Para:** Claude Code
**Sessão:** Documentação — executar ANTES da codificação
**Data:** 2026-05-05

---

## CONTEXTO

Projeto **Extratores AZ Resultados**.

Arquivos fonte da verdade (leia antes de qualquer alteração):
- `docs/SDD/Design_Doc_20260505_1336.md` — SDD v1.7 / revisão v9
- `docs/SDD/Tasks_20260505_1338.md` — Tasks v16
- `docs/SDD/Checkpoint_Sinc_20260505_1338.md` — Checkpoint atual

Stack: Python 3.13.7 | pdfplumber 0.11.9 | pikepdf 10.5.1 | pytest 9.0.3

---

## ESCOPO DO EXTRATOR

**Módulo:** `src/cartao_itau_personnalite.py`
**Cobertura:** faturas da linha Personnalitê do Itaú Unibanco, independente de bandeira (Mastercard, Visa, Elo) e categoria (Black, Platinum, Gold, etc.).
**Fora do escopo:** outras linhas do Itaú (Uniclass, Personnalité Empresas, etc.) — tratadas como emissores distintos se necessário no futuro.

---

## ANÁLISE DO PDF REAL (fatura abril/2026 — já executada)

Os dados abaixo foram extraídos com pdfplumber do PDF de teste. Use como especificação de layout — não especule.

### Fingerprint

Strings candidatas identificadas no PDF, robustas a variações de bandeira e categoria:

| String | Onde aparece | Robustez |
|--------|-------------|----------|
| `"ITAU UNIBANCO"` | Página 1, dados do beneficiário | Alta — independe de bandeira/categoria |
| `"Personnalitê"` | Cabeçalho de todas as páginas | Alta — define a linha do produto |
| `"40044828"` | Página 2, rodapé de atendimento | Alta — número SAC fixo da linha |

**Fingerprint adotado:** `["Personnalitê", "ITAU UNIBANCO"]`
Lógica: ambas devem estar presentes (AND). Isso exclui outros produtos Itaú sem risco de falso positivo na linha Personnalitê.

> **TASK-IT-01 deve confirmar** que essas strings estão presentes literalmente no `extract_text()` antes de commitar.

### Descriptografia
PDF protegido por senha. Senha armazenada na tabela SQLite de senhas (banco `~/.extratores/dados.db`), entregue via `pdf_decrypt.py` — padrão idêntico ao Santander e Samsung. Nenhuma lógica de descriptografia no extrator.

### Layout de colunas (extract_words — pág. 2)
```
Coluna ESQ:  x0 ≈ 151 (DATA) | x0 ≈ 178 (ESTABELECIMENTO) | x0 ≈ 225–234 (PARCELA) | x0 ≈ 319–323 (VALOR)
Coluna DIR:  x0 ≈ 367 (DATA) | x0 ≈ 394 (ESTABELECIMENTO) | x0 ≈ 530–556 (VALOR)

X_DIV = 355  ← gap real medido: 340 a 367
```
**Atenção:** diferente do Samsung (330) e do Santander (250). Não reutilizar constante de outros extratores.

### Extração de titular e cartão (página 1)
O `extract_text()` une palavras sem espaço em alguns campos. Usar `extract_words()` para esses campos específicos ou aplicar regex com tolerância a espaçamento variável.

```python
RE_TITUL = re.compile(r"Titular\s+([A-Z][A-Z\s]+?)(?=\s{2,}|\n|Cartão)")
RE_CART  = re.compile(r"Cartão\s+([\d.X]+)\s+(\w[\w\s]+)")   # captura número mascarado e produto (bandeira + categoria)
RE_VENC  = re.compile(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})")
```

`final_cartao`: últimos 4 dígitos do padrão `NNNN.XXXX.XXXX.NNNN` — grupo de captura do RE_CART.

### Estrutura de múltiplos titulares

A fatura Personnalitê agrupa lançamentos por portador com cabeçalhos e subtotais intermediários. Este comportamento **não é exclusivo do Itaú** — o Samsung pode apresentar o mesmo padrão quando o cliente possui cartões adicionais ativos. O tratamento aqui é idêntico ao que deve ser aplicado retroativamente ao Samsung se necessário.

Estrutura observada no PDF:
```
NOME PORTADOR (final NNNN)         ← cabeçalho de bloco: novo titular ativo
  DATA  ESTABELECIMENTO  VALOR
  ...lançamentos deste bloco...
Lançamentos no cartão (final NNNN)  SUBTOTAL   ← linha de subtotal: ignorar como lançamento

OUTRO PORTADOR (final NNNN)
  ...
Lançamentos no cartão (final NNNN)  SUBTOTAL

Total dos lançamentos atuais        TOTAL GERAL  ← campo de validação
```

Regras de parsing:
- Ao detectar cabeçalho de bloco: atualizar `titular_ativo` e `final_cartao_ativo`
- Lançamentos do bloco herdam esses valores
- Linha `"Lançamentos no cartão"`: pular (não é lançamento)
- Linha `"Total dos lançamentos atuais"`: capturar para validação

### Padrão de linha de lançamento
```
DATA  NOME_ESTABELECIMENTO[PARCELA]  VALOR
```
- `PARCELA`: token `NN/NN` embutido no nome (penúltimo token quando presente), ex: `AzulSeguros 04/06 398,12`
- Lançamentos de ajuste/estorno: valor negativo sem parcela, ex: `HOSPITAL RUBEM BERTA -1.033,44`
- Linha de categoria (ALIMENTAÇÃO, VESTUÁRIO, etc.) aparece logo abaixo do lançamento — ignorar

### Seções a processar / ignorar
| Seção | Ação |
|-------|------|
| `Lançamentos: compras e saques` | ✅ Processar |
| `Compras parceladas - próximas faturas` | ❌ Ignorar completamente |
| `Pagamento efetuado em DD/MM/YYYY` | ✅ Capturar como tipo `Pagamento` |
| Demais seções (Encargos, Limites, Simulações) | ❌ Ignorar |

### Validação
- **Campo:** `"Total dos lançamentos atuais"` (texto unido no extract_text: `"Totaldoslançamentosatuais"`)
- **Tolerância:** R$ 0,10
- **Sem fallback identificado** — se ausente: logar WARNING, não abortar

### Classificação de tipo
| Condição | Tipo |
|----------|------|
| `valor > 0` e `parcela_num > 0` | `"Compra parcelada"` |
| `valor > 0` e `parcela_num = 0` | `"Compra à vista"` |
| `valor < 0` e sem parcela | `"Ajuste"` |
| Linha de pagamento efetuado | `"Pagamento"` |

---

## DECISÕES LOCKED — EXTRATOR ITAÚ PERSONNALITÊ

| ID | Decisão |
|----|---------|
| I1 | `emissor = "itau_personnalite"` |
| I2 | `id_lote` prefix: `"ITP"` |
| I3 | `X_DIV = 355` — confirmado por medição; não herdar de outros extratores |
| I4 | Fingerprint: `["Personnalitê", "ITAU UNIBANCO"]` — AND lógico; confirmar no recon |
| I5 | Escopo: qualquer bandeira/categoria da linha Personnalitê |
| I6 | Descriptografia via `pdf_decrypt.py` — senha no banco SQLite, padrão idêntico ao Santander/Samsung |
| I7 | Múltiplos titulares: rastrear `titular_ativo` e `final_cartao_ativo` por bloco intermediário |
| I8 | Seção `"Compras parceladas - próximas faturas"` ignorada integralmente |
| I9 | Ajustes negativos sem parcela → `tipo = "Ajuste"` |
| I10 | Validação: `"Total dos lançamentos atuais"` com tolerância R$ 0,10; ausência = WARNING, não abort |

---

## O QUE FAZER

### Passo 1 — Criar `Tasks_Itau_20260505_HHMM.md`

Incluir as seguintes tasks atômicas (uma por commit):

**TASK-IT-01: Recon do PDF real**
Confirmar fingerprint, X_DIV e seções no PDF de teste.
Critério: relatório de recon registrado no arquivo de tasks; nenhum `.py` alterado.

**TASK-IT-02: Implementar `src/cartao_itau_personnalite.py`**
Novo módulo com lógica de parsing, multi-titular, validação.
Critério: processa PDF de teste sem erro; total validado dentro de R$ 0,10.

**TASK-IT-03: Registrar fingerprint em `pdf_router.py`**
Adicionar `"itau_personnalite": ["Personnalitê", "ITAU UNIBANCO"]`.
Critério: `detectar_emissor()` retorna `"itau_personnalite"` para o PDF de teste.

**TASK-IT-04: Registrar em `extrator.py`**
Adicionar `EXTRATORES["itau_personnalite"]` e `PREFIXOS_LOTE["itau_personnalite"] = "ITP"`.
Critério: flow end-to-end com envelope JSON correto.

**TASK-IT-05: Testes automatizados**
Criar `tests/test_itau_personnalite.py` — mínimo 5 testes com texto fixo/mocks.
Critério: `pytest tests/test_itau_personnalite.py` 100% passando.

**TASK-IT-06: Atualizar Design Doc e Checkpoint**
Adicionar seção `## 8. Extrator Itaú Personnalitê` no Design Doc; criar Checkpoint novo.
Critério: documentos versionados com timestamp correto.

### Passo 2 — Atualizar `Design_Doc_20260505_1336.md`

Incrementar para revisão v10. Adicionar:

```
## 8. Extrator Itaú Personnalitê

**Arquivo:** `src/cartao_itau_personnalite.py`
**Emissor:** `itau_personnalite`
**Escopo:** linha Personnalitê do Itaú Unibanco — qualquer bandeira e categoria
**PDF:** protegido por senha — descriptografia via `pdf_decrypt.py` (senha no banco SQLite)

### 8.1 Decisões locked
[tabela I1–I10]

### 8.2 Estrutura multi-titular
[descrever rastreamento de bloco]

### 8.3 Validação
Campo: `Total dos lançamentos atuais` | Tolerância: R$ 0,10
```

### Passo 3 — Criar `Checkpoint_Sinc_20260505_HHMM.md`

Atualizar:
- Status: TASK-01 a TASK-17 concluídas; TASK-IT-01 a IT-06 em fila
- Próxima ação: TASK-IT-01 (recon)
- Decisões locked: I1–I10

---

## RESTRIÇÕES

- Um arquivo por commit. Não agrupar tasks.
- Nomenclatura: `Nome_AAAAMMDD_HHMM.md` (HHMM = hora real de geração).
- Nunca incluir CPFs, nomes de clientes reais, senhas ou caminhos pessoais em commits.
- Perguntar antes de codificar se houver ambiguidade.
- Aguardar confirmação entre tasks.
- **Nenhum arquivo `.py` deve ser criado ou alterado nesta sessão.**

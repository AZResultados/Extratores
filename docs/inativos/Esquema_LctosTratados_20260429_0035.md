# Descrição dos campos de saída para a planilha LctosTratados

Este documento define o esquema de saída que todo extrator deve gerar na aba `LctosTratados`.
Os lançamentos são inseridos em modo **append acumulativo**, identificados por `ID_Lote`.

---

## Tabela de colunas

| # | Nome do campo       | Tipo     | Obrig. | Descrição / Regra de formação | Exemplo |
|---|---|---|---|---|---|
| 1 | Cliente             | Texto    | Sim    | Nome do cliente da AZ Resultados, selecionado pelo operador a partir de lista baseada no BD `cadastro_clientes`. | `ACME Ltda` |
| 2 | ID_Lote             | Texto    | Sim    | Identificador único do lote, gerado automaticamente no formato `{EMISSOR}-{AAAAMMDD}-{HHMMSS}`. | `SANTANDER-20260429-143022` |
| 3 | Arquivo Origem      | Texto    | Sim    | Nome do arquivo PDF (`Path.name`) — sem caminho absoluto (evita vazamento de PII). | `cliente_santander_04_2026.pdf` |
| 4 | Titular do cartão   | Texto    | Sim    | Nome do titular do cartão conforme consta no PDF. | `JOAO SILVA PEREIRA` |
| 5 | Final Cartão        | Texto (4) | Sim   | Últimos 4 dígitos do número do cartão, preservando zero à esquerda. Extraído do PDF. | `1234` |
| 6 | Tipo                | Texto    | Sim    | Classificação do lançamento. Domínio atual (será externalizado para tabela no BD): `Compra à vista`, `Compra parcelada`, `Pagamento`, `Outros`. | `Compra parcelada` |
| 7 | Data da Compra      | Data (DD/MM/AAAA) | Não¹ | Data original da transação. Muitas faturas informam apenas dia e mês; o ano deve ser inferido por retroação das parcelas (campo derivado). | `15/02/2026` |
| 8 | Descrição           | Texto    | Sim    | Descrição original do lançamento conforme aparece no PDF. | `PGTO AMAZON*MARKETPLACE` |
| 9 | Parcela             | Inteiro  | Sim    | Número da parcela atual conforme PDF. Para lançamentos **não parcelados** (Pagamento, Outros, Compra à vista), preencher com `0` (indica “não se aplica”). | `2` |
| 10| Qtde Parcelas       | Inteiro  | Sim    | Número total de parcelas conforme PDF. Para lançamentos **não parcelados**, preencher com `0`. | `5` |
| 11| Data de Vencimento  | Data (DD/MM/AAAA) | Sim | Data de vencimento da fatura informada no PDF. | `10/05/2026` |
| 12| Descrição Adaptada  | Texto    | Sim    | Texto amigável para leitura humana. Formação condicional:<br>• Se `Qtde Parcelas > 0`: `Descrição & " parc " & Parcela & "/" & Qtde Parcelas & " " & Data da Compra`<br>• Caso contrário: `Descrição & " " & Data da Compra` | `PGTO AMAZON*MARKETPLACE parc 2/5 15/02/2026` |
| 13| Valor               | Decimal  | Sim    | Valor da transação: **negativo para débitos, positivo para créditos** (convenção do projeto). | `-149,90` |

¹ **Data da Compra**: opcional apenas se o dado estiver ausente no PDF e for impossível inferir. Caso contrário, obrigatória.

---

## Regras de negócio complementares

- **Append acumulativo**: cada extração adiciona linhas ao final da planilha; nenhum registro existente é sobrescrito.
- **Rollback**: para desfazer um lote, excluir todas as linhas com o `ID_Lote` correspondente.
- **Fuso horário do `ID_Lote`**: horário local do sistema no momento do processamento.
- **Tipos de lançamento**: a lista de valores permitidos para `Tipo` será mantida em tabela de banco de dados no futuro; enquanto isso, validar contra os quatro valores textuais listados.
- **Inferência de ano da compra**: quando a fatura omite o ano, o extrator calcula retroagindo a partir da data da fatura (vencimento) considerando o intervalo entre as parcelas. Esse valor é uma **estimativa** e deve ser tratado como dado derivado.
- **Segurança**: jamais persistir PDF descriptografado em disco. As credenciais de abertura (senha) são armazenadas em banco SQLite local (`~/.extratores/dados.db`) e entregues ao Python via stdin — nunca em linha de comando nem em planilha.
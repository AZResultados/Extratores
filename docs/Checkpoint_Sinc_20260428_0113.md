Aqui está o resumo estruturado e técnico do nosso progresso até o momento, ideal para sincronizar o **DeepSeek** com as decisões de arquitetura e estratégia que tomamos.

---

### 🏛️ Checkpoint de Sincronização: Projeto Extratores AZ Resultados

**1. Contexto e Visão Geral**
* **Objetivo**: Transição de um MVP pessoal para um sistema B2B profissional para a **AZ Resultados**.
* **Escopo**: Consolidação automatizada de faturas de múltiplos cartões (Santander, Mercado Pago) e extratos bancários.
* **Operação**: Operador único (proprietário) no MVP, com expansão planejada para outros consultores.

**2. Status dos Requirements (v1.0 - LOCKED)**
* **BR-02 (Isolamento)**: Segregação estrita por cliente; dados nunca se misturam.
* **BR-03 (Fail-Fast)**: Qualquer falha em um arquivo (layout, senha, corrupção) interrompe o lote imediatamente e impede a persistência de dados.
* **BR-04 (Rastreabilidade)**: Auditoria total da origem de cada lançamento para permitir rollback futuro.
* **BR-08 (Segurança)**: Credenciais em texto claro permitidas apenas no MVP local; evolução obrigatória para cofre de senhas em distribuições futuras.

**3. Decisões do Design Doc (v1.0)**
* **Arquitetura de Isolamento**: Pastas de entrada estruturadas por cliente (`input/NOME_DO_CLIENTE`) e passagem do identificador via argumento CLI para o script Python.
* **Integração `pikepdf`**: Descriptografia feita em memória via `io.BytesIO`, eliminando arquivos temporários sem senha no disco.
* **Schema de Dados**: Inclusão das colunas "Cliente" e "Parcela" (extraída via Regex) na aba `LctosTratados`.
* **Interface VBA ↔ Python**: O VBA passa `--input`, `--cliente` e `--password` via `WScript.Shell`. O script retorna `sys.exit(1)` em erros para acionar o Fail-Fast no Excel.

**4. Pendências e Gaps (Backlog)**
* **G3 (ID_Lote)**: Criação de identificador único de execução para auditoria.
* **G4 (Ambiente)**: Criação do `requirements.txt` para portabilidade.
* **PCI-3 (Datas)**: Correção da conversão de datas seriais do Excel para objetos Date nativos.

---

**Próximo Passo**: Iniciar a **Tríade de Tasks**, quebrando o Design Doc em tarefas granulares para o **Claude Code** executar no terminal.

Alguma dúvida sobre as decisões ou podemos seguir para o detalhamento das Tasks?
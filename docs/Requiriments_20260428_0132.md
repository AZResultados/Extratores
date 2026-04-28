### 📄 Requirements: Sistema Extrator Financeiro AZ Resultados

**[VISÃO GERAL]**
Automatizar a consolidação de extratos bancários e faturas de cartão de crédito (PDFs de múltiplas fontes) em dados estruturados para análise financeira B2B. O sistema deve suportar múltiplos clientes, titulares, emissores e períodos, garantindo integridade financeira e privacidade.

**[REGRAS DE NEGÓCIO CORE - FUNCIONAIS]**
* **BR-01 (Multi-contexto):** O sistema deve processar lotes de documentos identificando e separando lançamentos por Cliente (contratante da AZ Resultados), Emissor (banco/bandeira) e Titular final (portador do cartão).
* **BR-02 (Isolamento de Dados):** Obrigatória a segregação estrita dos dados processados. Informações de um cliente não podem, sob nenhuma hipótese, ser expostas ou misturadas com as de outro.
* **BR-03 (Fail-Fast em Falhas):** Se a extração de um arquivo falhar (ex: layout não reconhecido, erro de credencial, arquivo corrompido), o sistema deve interromper imediatamente todo o processamento do lote, gerar alerta detalhado ao operador e não persistir nenhum dado da execução atual.
* **BR-04 (Rastreabilidade e Rollback):** Todo lançamento processado deve ter sua origem auditável. O sistema deve ser capaz de identificar de qual arquivo e de qual lote de execução exato um dado se originou, permitindo reversão (rollback) de lotes importados com erro.

**[REGRAS DE NEGÓCIO - SEGURANÇA E CICLO DE VIDA]**
* **BR-05 (Integridade Financeira):** Tolerância zero para conversões silenciosas. O sistema deve garantir a exatidão absoluta de valores monetários (respeitando sinais de crédito/débito) e datas originais.
* **BR-06 (Privacidade e Descarte):** Arquivos temporários sem criptografia gerados durante o processo devem ser expurgados imediatamente após o sucesso da extração ou após a resolução manual de pendências pelo operador.
* **BR-07 (Retenção de Longo Prazo):** Documentos originais e bases de dados consolidadas devem ser mantidos de forma íntegra e acessível por 5 anos após o encerramento do contrato com o cliente.
* **BR-08 (Segurança de Credenciais - Evolução Obrigatória):**
  - Versão MVP (uso exclusivo do proprietário AZ Resultados): credenciais de abertura de PDF podem permanecer em texto claro, armazenadas localmente, sob responsabilidade do único operador.
  - Qualquer versão subsequente distribuída para outros usuários (incluindo testes com terceiros) DEVE implementar armazenamento criptografado ou gerenciamento seguro de credenciais, sem texto claro em arquivos compartilhados.
# Implementação de Agente Autônomo Seguro com LangChain, LangGraph, Groq, Pydantic e Streamlit

Guia prático e registro técnico da implementação de um **Agente Autônomo de Gestão de Prontuários Médicos** em Python, utilizando a arquitetura moderna baseada em grafos (`create_agent` / LangGraph), *Tool Calling* via API do Groq, validação estrita de dados com Pydantic v2, camadas determinísticas de **Segurança de Aplicações (AppSec / Hardening)** e interface web interativa com Streamlit.

---

## Visão Geral da Arquitetura

Diferente de um pipeline estático, o agente opera em um ciclo **ReAct** (*Reasoning + Acting*) gerenciado por um grafo de estados (*StateGraph*). Ele avalia a entrada do usuário, consulta a memória da conversa, decide autonomamente se precisa acionar uma ferramenta (`@tool`) e passa todas as interações por camadas determinísticas de segurança antes de ler ou gravar no CSV.

```text
[Entrada do Usuário (CLI ou Streamlit - app.py)]
        │
        ▼  Trava Anti-DoS (máx. 1.000 caracteres)
[conversar_com_agente()] ◄─── Memória (chat_history: janela deslizante de 10 msgs)
        │
        ▼  LangGraph: create_agent (recursion_limit=10)
[LLM: ChatOpenAI -> Groq API (openai/gpt-oss-120b)]
        │
        ├──► Dados incompletos ou conversa geral ──► [Resposta Direta ao Usuário]
        │
        ├──► Tool: salvar_na_planilha()
        │       └──► Pydantic v2 (DadosPaciente)
        │               ├──► Regex Whitelist no nome (anti-CSV Injection)
        │               └──► Bloqueio de prefixos (=, +, -, @, \t, \r)
        │                       └──► Append em [pacientes.csv]
        │
        └──► Tool: consultar_planilha()
                └──► Trava Anti-Dump (mín. 3 chars + .head(3))
                        └──► Leitura segura em [pacientes.csv]
```

---

## Stack Utilizada

- **Orquestração e Motor de Grafos:** `langchain` (v1.x), `langchain-core`, `langgraph` (`create_agent`)
- **Provedor LLM:** `langchain-openai` (`ChatOpenAI` apontando para o endpoint compatível da API do Groq com `openai/gpt-oss-120b`)
- **Validação de Schema e Hardening:** `pydantic` (v2 com `BaseModel`, `Field` e `@field_validator`) + `re` (Regex)
- **Persistência de Dados:** `pandas` (leitura e gravação em `pacientes.csv`)
- **Interface Web e Red Team Playground:** `streamlit`
- **Gerenciamento de Segredos:** `python-dotenv`

---

## Estrutura do Projeto

```text
AGENT/
├── .env                 # Chave de API do Groq (não versionado; pode ficar na raiz do repo)
├── .gitignore           # Ignora .env, pacientes.csv e caches do Python
├── agent.py             # Núcleo do agente, ferramentas (@tool), memória e travas de segurança
├── app.py               # Interface web em Streamlit + Red Team Playground (gerada com auxílio de IA)
├── pacientes.csv        # Base de prontuários gerada automaticamente na primeira execução
└── README.md            # Documentação, registro de segurança e guia de revisão
```

---

## Passo a Passo de Configuração e Execução

### 1. Instalação das Dependências

Instale os pacotes necessários para a arquitetura moderna do LangChain 1.x com LangGraph, manipulação de dados e interface gráfica:

```bash
pip install langchain langchain-core langchain-openai langgraph pydantic pandas python-dotenv streamlit
```

### 2. Configuração de Variáveis de Ambiente

Crie um arquivo `.env` (na raiz do repositório ou dentro da pasta `AGENT/`) com a sua chave da API do Groq:

```env
GROQ_API_KEY="gsk_sua_chave_aqui"
```

Garanta que o `.gitignore` bloqueie o envio de credenciais e dados locais para o GitHub:

```gitignore
.env
pacientes.csv
__pycache__/
*.pyc
```

### 3. Etapas da Implementação no Código (`agent.py`)

1. **Validação Estrita e Anti-CSV Injection (`DadosPaciente`):** Uso do Pydantic v2 com `Field` (`min_length=2`, `gt=0`) e `@field_validator` determinísticos. O campo `nome` só aceita letras, espaços, hífen e apóstrofo via Regex (`^[A-Za-zÀ-ÿ\s'-]+$`), enquanto `sintomas` e `diagnostico` bloqueiam prefixos de fórmula (`=`, `+`, `-`, `@`, `\t`, `\r`) que poderiam executar comandos ao abrir o CSV no Excel.
2. **Persistência Local (`criar_planilha_paciente`):** Verifica automaticamente se `pacientes.csv` existe no diretório do script e o inicializa com as colunas padrão (`nome`, `idade`, `sintomas`, `diagnostico`).
3. **Ferramentas Modulares (`@tool`):**
   - `salvar_na_planilha`: Vinculada ao schema `args_schema=DadosPaciente`. Só realiza o *append* (`mode="a"`) no CSV após todas as validações passarem.
   - `consultar_planilha`: Realiza busca *case-insensitive* (`str.contains(..., case=False, na=False)`), mas exige no mínimo **3 caracteres** na query e limita o retorno com `.head(3)` para impedir extração total (*dump*) da tabela.
4. **LLM e Grafo de Estados (`create_agent`):** Instanciação do `ChatOpenAI` apontando para `https://api.groq.com/openai/v1` com o modelo `openai/gpt-oss-120b` (`temperature=0`, `max_retries=3`). O agente é compilado via `create_agent(model=llm, tools=tools, system_prompt=system_prompt)`, eliminando a necessidade de `ChatPromptTemplate` manual e `agent_scratchpad`.
5. **Memória e Proteção contra DoS (`conversar_com_agente`):**
   - Bloqueia entradas maiores que **1.000 caracteres** antes mesmo de acionar o LLM.
   - Passa `config={"recursion_limit": 10}` no `.invoke()` para impedir loops infinitos entre raciocínio e ferramenta.
   - Mantém o contexto com `HumanMessage` e `AIMessage` em uma **janela deslizante (*Sliding Window*)** via `del chat_history[:-10]`, evitando crescimento ilimitado de tokens.

### 4. Interface Gráfica e Red Team Playground (`app.py`)

Para facilitar os testes práticos e demonstrar as defesas atuando em tempo real, foi adicionada uma interface em **Streamlit** *(camada visual gerada com auxílio de IA, enquanto toda a lógica do agente e os controles reais de segurança residem de forma determinística no `agent.py`)*:

- **Chat Interativo (`st.chat_message` / `st.chat_input`):** Conectado diretamente à função `conversar_com_agente()`, com botão para limpar a tela e resetar a memória (`chat_history.clear()`).
- **Tabela em Tempo Real (`st.dataframe`):** Exibe o conteúdo de `pacientes.csv` atualizado automaticamente a cada cadastro realizado pelo agente.
- **Red Team Playground (Barra Lateral):** Botões prontos para disparar vetores reais de ataque com um clique:
  - *CSV Injection* (`=cmd|' /C calc'!A0`)
  - *Dump Total da Base* (busca genérica pela letra `'a'`)
  - *Prompt Injection* (engenharia social tentando sobrescrever o *System Prompt*)
  - *Payload Gigante* (1.200 caracteres testando a trava anti-DoS)
- **Monitor de AppSec / Guardrails:** Painel de telemetria visual que registra as tentativas anômalas interceptadas pelo back-end durante a sessão.

Para iniciar a interface no navegador (`http://localhost:8501`):

```bash
streamlit run AGENT/app.py
```

*(Também é possível executar o agente diretamente em modo terminal/CLI com `python AGENT/agent.py`.)*

---

## Segurança e Hardening (AppSec / OWASP LLM)

Um dos principais aprendizados desta etapa foi constatar que **guardrails escritos apenas no System Prompt não são controles de segurança confiáveis**, pois LLMs são probabilísticos e suscetíveis a engenharia social (*Prompt Injection*). Para blindar o agente, foi aplicada a estratégia de **Defesa em Profundidade (*Defense-in-Depth*)**:

| Vetor de Ataque / Risco | Cenário Explorável | Controle Determinístico Aplicado (`agent.py`) |
| :--- | :--- | :--- |
| **CSV / Formula Injection** | Inserção de payloads como `=cmd\|' /C calc'!A0` para execução de comandos ao abrir o `.csv` no Excel. | `@field_validator` no Pydantic v2 com *whitelist* Regex no nome e bloqueio de prefixos (`=`, `+`, `-`, `@`, `\t`, `\r`). |
| **Dump / Exfiltração de Dados** | Busca por `"a"` ou string vazia retornando 100% dos prontuários cadastrados. | Exigência de no mínimo 3 caracteres na query + paginação estrita com `.head(3)`. |
| **DoS / Consumo Ilimitado** | Envio de textos gigantes ou prompts forçando loops infinitos de *tool calling*. | Limite de 1.000 caracteres na entrada + `recursion_limit=10` no grafo do LangGraph. |
| **Estouro de Contexto (*Context Bloat*)** | Acúmulo infinito de mensagens no histórico degradando custo e latência. | Janela deslizante (`del chat_history[:-10]`) mantendo apenas as 10 mensagens mais recentes. |
| **Separação Front-end / Back-end** | Validação apenas na interface podendo ser burlada via CLI ou API. | Toda a segurança real roda no `agent.py`; o `app.py` faz apenas exibição e telemetria visual. |

---

## Troubleshooting e Lições Aprendidas

Durante o desenvolvimento, migração de arquitetura e testes de segurança deste agente, foram enfrentados e resolvidos os seguintes problemas:

| Problema / Sintoma | Causa Raiz | Solução Aplicada |
| :--- | :--- | :--- |
| `ImportError: cannot import name 'create_tool_calling_agent' from 'langchain.agents'` | No LangChain v1.x, a arquitetura legada (`AgentExecutor` e `create_tool_calling_agent`) foi movida para `langchain-classic` e substituída pela API moderna baseada em LangGraph. | Instalação do `langgraph` e migração para `from langchain.agents import create_agent`, removendo `AgentExecutor`, `ChatPromptTemplate` e `MessagesPlaceholder`. |
| `OpenAIInvalidRequestError (400): 'messages.0.content' : value must be a string` | Uma vírgula sobrando após as aspas dentro dos parênteses de `system_prompt` fez o Python interpretá-lo como uma **tupla** de 1 elemento em vez de `str`. | Remoção da vírgula final na declaração da variável `system_prompt`, enviando uma string pura ao grafo. |
| `OpenAIModelNotFoundError (404): The model 'llama-3.3-70b-versatile' does not exist` | O catálogo de modelos ativos no Groq foi atualizado e o ID antigo deixou de estar disponível na conta. | Consulta direta ao endpoint `/models` da API do Groq via SDK `openai` e atualização para o modelo ativo `openai/gpt-oss-120b`. |
| Erro de sintaxe/aspas ao listar modelos via `urllib` em comando de uma linha no PowerShell | Diferenças de escape de aspas no PowerShell do Windows e bloqueio de `User-Agent` padrão em requisições manuais. | Execução de um script Python curto usando o cliente oficial `OpenAI(base_url="https://api.groq.com/openai/v1").models.list()`. |
| Agente vulnerável a engenharia social (*Prompt Injection*), *CSV Injection* e extração total de registros | Confiança exclusiva em regras no prompt do sistema, sem validação determinística nas ferramentas e entradas. | Implementação de validação via Pydantic v2 (`@field_validator`), trava de 3 caracteres + `.head(3)`, limite de 1.000 chars, `recursion_limit=10` e *Red Team Playground* no Streamlit para validação contínua. |

---

## Próximos Passos da Trilha de Estudos

- [x] **Etapa 1 — RAG Básico + Interface:** Leitura de PDF, chunking, embeddings, FAISS, geração fundamentada via OpenRouter e interface em Streamlit.
- [x] **Etapa 2 — Agentes + AppSec:** Criação de *tools*, migração para LangGraph (`create_agent`), validação com Pydantic v2, hardening contra ataques reais e interface em Streamlit.
- [ ] **Etapa 3 — Agentic-RAG:** Encapsular o índice vetorial (FAISS) como uma `@tool` para que o agente decida dinamicamente quando consultar a base documental, com atenção a *Indirect Prompt Injection*.
- [ ] **Etapa 4 — NER + Agente (Projeto Final):** Estudo da arquitetura BERT, extração de entidades nomeadas (NER) de prontuários de pacientes, cadastro automatizado em planilha e consulta via chatbot (FastAPI + Streamlit).

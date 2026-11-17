# Implementação de RAG (Retrieval-Augmented Generation) com LangChain, FAISS e OpenRouter

Guia prático e registro técnico da implementação de um pipeline de **RAG (*Retrieval-Augmented Generation*)** em Python, utilizando leitura de documentos PDF, quebra semântica em trechos (*chunking*), embeddings multilíngues locais, busca vetorial com **FAISS** e geração de respostas fundamentadas via **OpenRouter**.

---

## Visão Geral da Arquitetura

O pipeline segue o fluxo clássico de RAG dividido em duas fases principais: **Indexação** (preparação da base vetorial) e **Recuperação + Geração** (consulta em tempo de execução).

```text
[PDF (musicas.pdf)]
        │
        ▼  PyMuPDFLoader
[Texto Extraído]
        │
        ▼  RecursiveCharacterTextSplitter (chunk_size=500, overlap=100)
[Chunks Semânticos]
        │
        ▼  HuggingFaceEmbeddings (paraphrase-multilingual-MiniLM-L12-v2)
[Vetores Numéricos]
        │
        ▼  FAISS (Vector Store)
[Índice Vetorial] ◄─── Pergunta do Usuário (vetorizada pelo mesmo modelo)
        │
        ▼  Retriever (top k=5)
[Contexto Recuperado] + [Prompt Template]
        │
        ▼  ChatOpenAI (OpenRouter API)
[Resposta Fundamentada]
```

---

## Stack Utilizada

* **Orquestração:** `langchain`, `langchain-core`, `langchain-community`
* **Leitura de PDF:** `pymupdf` (`PyMuPDFLoader`)
* **Divisão de Texto (*Chunking*):** `langchain-text-splitters` (`RecursiveCharacterTextSplitter`)
* **Embeddings Locais:** `langchain-huggingface` + `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`)
* **Banco Vetorial:** `faiss-cpu` (`FAISS`)
* **Provedor LLM:** `langchain-openai` (`ChatOpenAI` apontando para o endpoint do OpenRouter)
* **Gerenciamento de Segredos:** `python-dotenv`

---

## Estrutura do Projeto

```text
RAG/
├── .env                 # Chave de API do OpenRouter (não versionado)
├── .gitignore           # Ignora .env e caches do Python
├── musicas.pdf          # Base de conhecimento em PDF
├── rag.py               # Script principal do pipeline de RAG
└── README.md            # Documentação e guia de revisão
```

---

## Passo a Passo de Configuração e Execução

### 1. Instalação das Dependências

Devido à modularização das versões recentes do LangChain, os pacotes de comunidade, splitters e provedores devem ser instalados separadamente:

```powershell
pip install langchain langchain-core langchain-community langchain-text-splitters langchain-huggingface langchain-openai sentence-transformers faiss-cpu pymupdf python-dotenv
```

### 2. Configuração de Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com a sua chave do OpenRouter:

```env
OPENROUTER_API_KEY="sk-or-v1-sua_chave_aqui"
```

Adicione um `.gitignore` para evitar o envio da chave para o GitHub:

```gitignore
.env
__pycache__/
*.pyc
```

### 3. Etapas do Pipeline no Código (`rag.py`)

1. **Carregamento do PDF (`Load`):**
   O `PyMuPDFLoader` extrai o texto selecionável de cada página do arquivo `musicas.pdf`.
2. **Quebra em Trechos (`Chunking`):**
   O `RecursiveCharacterTextSplitter` divide o documento usando separadores alinhados à estrutura do texto (`["\nFaixa ", "\n\n", "\n", " ", ""]`), com `chunk_size=500` e `chunk_overlap=100`, evitando misturar blocos distintos no mesmo vetor.
3. **Vetorização (`Embeddings`):**
   O modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` roda localmente para converter os trechos e as perguntas do usuário em vetores densos com suporte semântico ao português.
4. **Indexação e Busca (`Vector Store` & `Retriever`):**
   O `FAISS.from_documents()` indexa os vetores em memória e cria um *retriever* configurado com `k=5` para retornar os 5 trechos mais próximos da pergunta.
5. **Prompt e Geração (`Augmentation` & `Generation`):**
   O `ChatPromptTemplate` injeta os trechos recuperados no contexto e instrui o modelo a responder exclusivamente com base no documento (evitando alucinações). A chamada ao LLM é feita via `ChatOpenAI` conectado ao OpenRouter (`base_url="https://openrouter.ai/api/v1"`).

---

## Troubleshooting e Lições Aprendidas

Durante o desenvolvimento e os testes deste pipeline, foram identificados e resolvidos os seguintes pontos:

| Problema / Sintoma | Causa Raiz | Solução Aplicada |
| :--- | :--- | :--- |
| `ModuleNotFoundError` / imports sublinhados em `langchain_community`, `langchain_text_splitters` e `langchain.prompts` | Separação de pacotes no ecossistema LangChain atual e mudança do `ChatPromptTemplate` para `langchain_core`. | Instalação individual dos pacotes parceiros e atualização do import para `from langchain_core.prompts import ChatPromptTemplate`. |
| `ImportError: pymupdf package not found` | O `PyMuPDFLoader` depende da biblioteca `pymupdf` instalada à parte. | Instalação via `pip install pymupdf`. |
| `AttributeError: 'VectorStoreRetriever' object has no attribute 'get_relevant_documents'` (e erro ao chamar `llm(mensagens)`) | Métodos legidos removidos em favor da interface padrão `Runnable` (LCEL). | Substituição por `retriever.invoke(question)` e `llm.invoke(mensagens)`. |
| `OpenAIModelNotFoundError (404)` ou `OpenAIRateLimitError (429)` no OpenRouter | Modelos gratuitos específicos podem ser descontinuados ou sofrer fila/limite de requisições no provedor upstream. | Uso do roteador dinâmico `model="openrouter/free"` com `max_retries=3` no `ChatOpenAI`. |
| Pipeline roda sem erros, mas o LLM diz não encontrar uma informação que está no PDF | **1.** Embedding monolíngue em inglês (`all-MiniLM-L6-v2`) dava mais peso a palavras estruturais em PT-BR do que às entidades.<br>**2.** `chunk_size=1000` agrupava múltiplos registros no mesmo vetor, diluindo a semântica. | **1.** Troca para `paraphrase-multilingual-MiniLM-L12-v2`.<br>**2.** Redução para `chunk_size=500` com separador customizado (`"\nFaixa "`) e aumento do retriever para `k=5`. |

---

## Próximos Passos da Trilha de Estudos

* [x] **Etapa 1 — RAG Básico:** Leitura de PDF, chunking, embeddings, FAISS e geração fundamentada.
* [ ] **Etapa 2 — Agentes:** Criação de *tools* e uso de agentes com LangChain e Pydantic.
* [ ] **Etapa 3 — Agentic-RAG:** Agente capaz de decidir quando consultar a base vetorial, reformular buscas ou acionar ferramentas externas.
* [ ] **Etapa 4 — NER + Agente (Projeto Final):** Estudo da arquitetura BERT, extração de entidades nomeadas (NER) de prontuários de pacientes, cadastro automatizado em planilha e consulta via chatbot (FastAPI + Streamlit).

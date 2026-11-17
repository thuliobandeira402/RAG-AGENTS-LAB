import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

"""Esse script é um exemplo de implementação de RAG (Retrieval-Augmented Generation) usando LangChain, FAISS e OpenRouter.
Ele carrega um documento PDF, divide o conteúdo em partes menores, cria embeddings para essas partes
e permite responder perguntas com base no conteúdo do documento usando um modelo de linguagem. Colocarei no decorrer do código
(principalmente na parte do fluxo de responder as questões pq é mais complexo) comentários
pra explicar melhor o que cada parte do código faz."""

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY environment variable não encontrada no .env")

# Instanciar o LLM

llm = ChatOpenAI(
    model="openrouter/free",                  # roteia automaticamente para um modelo gratuito, antes tava dando erro 429
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
    max_tokens=512,
    max_retries=3,                            # tenta novamente automaticamente se der ERRO 429 
)

# Embeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

# carregar o PDF
pdf_path = "musicas.pdf"  
if not os.path.exists(pdf_path):
    raise FileNotFoundError(f"O arquivo {pdf_path} não foi encontrado.")

loader = PyMuPDFLoader(pdf_path)
docs = loader.load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\nFaixa ", "\n\n", "\n", " ", ""] # separadores para dividir o texto em partes menores, priorizando quebras de linha e espaços
    )
splits = splitter.split_documents(docs)

vectorstore = FAISS.from_documents(splits, embeddings)
retriver = vectorstore.as_retriever(search_kwargs={"k": 5}) # buscar os 5 documentos mais relevantes para a pergunta

prompt = ChatPromptTemplate.from_template(
    "Você é um assistente especializado em músicas, significados e temáticas das músicas, sonoridade, etc."
    "Responda exclusivamente com base no documento de referência fornecido. Se a resposta não estiver no documento, diga 'Desculpe, não sei a resposta para isso.'"
    "- Responda sempre em português brasileiro, de forma clara, didática e acolhedora. \n"
    "- Explique o significado das músicas, a temática, a sonoridade, o contexto histórico e cultural, e qualquer outra informação relevante que possa ser extraída do documento sempre que perguntado.\n"
    "- Não invente nada que não esteja no documento. Se a informação não estiver no documento, diga 'Desculpe, não sei a resposta para isso.'\n"
    "- Se a pergunta não estiver relacionada ao documento, diga 'Desculpe, não sei a resposta para isso.'\n "
    "Documento de referência: {context}\n"
    "Pergunta: {question}\n" 
)

# Função para responder perguntas com base no documento
def answer_question(question: str) -> str:
    """Recebe uma pergunta e retorna uma resposta baseada no documento de referência."""
    print(f"DEBUG: Recebendo pergunta: {question}")

    docs = retriver.invoke(question) # buscar documentos relevantes
    print(f"DEBUG: Documentos relevantes encontrados: {len(docs)}")
    for i, d in enumerate(docs, 1):
        print(f"DEBUG: Documento {i}: {d.page_content[:200]}...")  # printar os primeiros 200 caracteres do conteúdo do documento

    context = "\n\n".join([d.page_content for d in docs])  # concatenar o conteúdo dos documentos relevantes
    mensagens = prompt.format_messages(context=context, question=question)  # formatar a mensagem com o contexto e a pergunta

    try:
        resposta = llm.invoke(mensagens) # gerar a resposta usando o LLM
        print(f"DEBUG: Resposta gerada: {resposta.content}")

    except Exception as e:
        print(f"DEBUG: Ocorreu um erro ao gerar a resposta: {e}")
        raise e

    return resposta.content if hasattr(resposta, 'content') else str(resposta)  # retornar a resposta gerada  

if __name__ == "__main__":
    pergunta = "Qual o significado da música 'E85' do Don Toliver?"
    print(answer_question(pergunta))
    
    

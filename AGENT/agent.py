from pydantic import BaseModel, Field, field_validator
import os
import pandas as pd
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from dotenv import load_dotenv
import re
from langchain_core.messages import HumanMessage, AIMessage

main_dir = os.path.dirname(os.path.abspath(__file__))  # diretório principal do projeto
caminho_planilha = os.path.join(main_dir, "pacientes.csv")  # caminho para a planilha de dados do paciente

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")



class DadosPaciente(BaseModel):
    nome: str = Field(min_length=2, description="Nome completo do paciente") 
    idade: int = Field(gt=0, description="Idade do paciente em anos")
    sintomas: str= Field(min_length=2, description="Sintomas do paciente")         # Colocar os atributos da classe com "Field para aplicar guardrails"
    diagnostico:str = Field(min_length=2, description="Diagnóstico do paciente")

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, campo: str) -> str:
        # bloqueia CSV Injection e símbolos estranhos
        if not re.match(r"^[A-Za-zÀ-ÿ\s'-]+$", campo.strip()):
            raise ValueError("Nome inválido: use apenas letras, espaços, hífen ou apóstrofo.")
        return campo.strip()


    @field_validator("sintomas", "diagnostico")
    @classmethod
    def bloquear_csv_injection_sindia(cls, campo:str) -> str:
        texto = campo.strip()
        if texto.startswith(("=", "+", "-", "@", "\t", "\r")):
            raise ValueError("Input bloqueado por conter prefixos inválidos")
        return texto

def criar_planilha_paciente():
    """Cria uma planilha de dados do paciente com colunas padrão, caso não exista."""
    if not os.path.exists(caminho_planilha):
        colunas = ["nome", "idade", "sintomas", "diagnostico"]
        df = pd.DataFrame(columns=colunas)  # criar um DataFrame vazio com as colunas padrão
        df.to_csv(caminho_planilha, index=False, encoding="utf-8")  # salvar a planilha no caminho especificado
        print(f"Planilha de dados do paciente criada em: {caminho_planilha}")
    else:
        print(f"A planilha de dados do paciente já existe em: {caminho_planilha}")


criar_planilha_paciente()

@tool(args_schema=DadosPaciente)
def salvar_na_planilha(nome: str, idade: int, sintomas: str, diagnostico: str) -> str:
    """Pega os dados do paciente e salva na planilha pacientes.csv"""
    nova_linha = pd.DataFrame([{
        "nome": nome,
        "idade": idade,
        "sintomas": sintomas,              # cria uma nova linha para ser inserida
        "diagnostico": diagnostico
    }])

    # o mode "a"anexa ao final do arquivo, append
    nova_linha.to_csv(caminho_planilha, mode="a", header=False, index=False, encoding="utf-8")

    return f"Paciente {nome}(idade: {idade}) Salvo com sucesso na planilha!"

@tool
def consultar_planilha(nome_busca: str) -> str:
    """Busca um paciente dentro da planilha com base em seu nome"""
    if len(nome_busca.strip()) < 3:
        return "Informe pelo menos 3 caracteres do nome do paciente para realizar a busca."
    
    df = pd.read_csv(caminho_planilha, encoding="utf-8")

    if df.empty:
        return "A planilha está vazia. Nenhum paciente cadastrado ainda"

    # busca pelo paciente sem diferenciar maiuscula e minuscula (case=False)
    resultados = df[df["nome"].str.contains(nome_busca, case=False, na=False)]

    if resultados.empty:
        return f"Nenhum paciente encontrado com o nome {nome_busca}"

    # Caso ache, converter as linhas encontradas para texto legível para a LLM ler e responder o usuário
    return resultados.head(3).to_string(index=False)


# Instanciando o modelo LLM

llm = ChatOpenAI(
    model="openai/gpt-oss-120b",  # ou "qwen/qwen3.8-27b"
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
    temperature=0,
    max_tokens=2048,
    max_retries=3,
)

system_prompt = (
        "Você é um assistente médico responsável por gerenciar prontuários na planilha.\n"
        "Regras e Guardrails:\n"
        "1. Para cadastrar um paciente, você precisa obrigatoriamente de: nome, idade (maior que 0), sintomas e diagnóstico. Se faltar qualquer um desses dados, NÃO chame a ferramenta, pergunte ao usuário o que está faltando.\n"
        "2. Quando tiver todos os 4 dados validados, use a ferramenta 'salvar_na_planilha'.\n"
        "3. Quando perguntarem sobre um paciente, use sempre 'consultar_planilha'. Nunca invente dados que não retornarem da planilha.\n"
        "4. Responda sempre em português brasileiro, de forma clara e objetiva."
)


tools = [salvar_na_planilha, consultar_planilha]


agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)

chat_history = []

def conversar_com_agente(mensagem_usuario: str) -> str:
    if len(mensagem_usuario) > 1000:
        return f"Mensagem muito longa, a mensagem não deve ultrapassar 1000 caracteres."

    mensagens_entrada = chat_history + [HumanMessage(content=mensagem_usuario)]
    resposta = agent.invoke({"messages": mensagens_entrada}, config={"recursion_limit": 10}) # chama a llm passando o historico de conversa e a mensagem do user
    
    texto_resposta = resposta['messages'][-1].content # guarda a resposta da llm

    chat_history.append(HumanMessage(content=mensagem_usuario)) # Aqui a gente vai guardar no histórico a pergunta do humando e a resposta da IA
    chat_history.append(AIMessage(content=texto_resposta))

    del chat_history[:-10] # segurança, limpar o histórico, mantém as ultimas 10 mensagens

    return texto_resposta


# looping de teste para ver se tá tudo funcionando
if __name__ == "__main__":
    print("Assistente Médico iniciado! (Digite 'sair' para encerrar)\n")
    while True:
        entrada = input("Você: ")
        if entrada.strip().lower() == "sair":
            break
        saida = conversar_com_agente(entrada)
        print(f"\nAgente: {saida}\n")



import streamlit as st
from rag import answer_question  # se o seu arquivo for rag_2.py, troque para: from rag_2 import answer_question

st.set_page_config(page_title="RAG - Músicas", page_icon="🎧", layout="centered")
st.title("RAG - Dossiê Musical")
st.caption("Pergunte sobre significados, sonoridades e temáticas das músicas da playlist 🎵")

pergunta = st.text_input(
    "Digite sua pergunta:",
    placeholder="Ex: Qual o significado da música E85 do Don Toliver?"
)

if st.button("Consultar"):
    if not pergunta.strip():
        st.warning("⚠️ Digite uma pergunta primeiro!")
    else:
        with st.spinner("Consultando a base musical e gerando resposta..."):
            try:
                resposta = answer_question(pergunta)
                st.markdown("### 🎶 Análise:")
                st.success(resposta)
            except Exception as e:
                st.error(f"Erro ao gerar resposta: {e}")
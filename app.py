from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.chatbot_fai_docs.rag import ask_model, build_index, list_pdf_files, retrieve


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent


def default_value(name: str, fallback: str) -> str:
    return os.getenv(name, fallback)


def current_pdf_signature(pdf_files: list[Path]) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (pdf.name, pdf.stat().st_mtime_ns, pdf.stat().st_size) for pdf in pdf_files
    )


@st.cache_resource(show_spinner=False)
def load_retrieval_index(signature: tuple[tuple[str, int, int], ...]):
    pdf_files = [ROOT_DIR / "docs" / "sil" / item[0] for item in signature]
    return build_index(pdf_files)


def provider_defaults(provider: str) -> tuple[str, str, str]:
    if provider == "Ollama local":
        return (
            default_value("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            default_value("OPENAI_API_KEY", "ollama"),
            default_value("OPENAI_MODEL", "llama3.2:3b"),
        )

    return (
        default_value("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        default_value("OPENAI_API_KEY", ""),
        default_value("OPENAI_MODEL", "gpt-4.1-mini"),
    )


st.set_page_config(page_title="Chatbot FAI Docs", page_icon="📄", layout="wide")
st.title("Chatbot FAI Docs")
st.caption("Protótipo local para conversar com os manuais em PDF do projeto.")

with st.sidebar:
    st.header("Configuração")
    provider = st.selectbox("Modelo", ["OpenAI API", "Ollama local"])
    base_url_default, api_key_default, model_default = provider_defaults(provider)

    base_url = st.text_input("Base URL", value=base_url_default)
    model = st.text_input("Modelo", value=model_default)
    api_key = st.text_input("API key", value=api_key_default, type="password")
    top_k = st.slider("Trechos recuperados", min_value=2, max_value=8, value=4)

    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

pdf_files = list_pdf_files()

if not pdf_files:
    st.error("Nenhum PDF foi encontrado em docs/sil.")
    st.stop()

signature = current_pdf_signature(pdf_files)
with st.spinner("Lendo e indexando os documentos..."):
    retrieval_index = load_retrieval_index(signature)

if retrieval_index is None:
    st.error("Os PDFs foram encontrados, mas não foi possível extrair texto deles.")
    st.stop()

st.info("Documentos carregados: " + ", ".join(f"{pdf.name}" for pdf in pdf_files))

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources")
        if sources:
            with st.expander("Fontes usadas"):
                for source in sources:
                    st.markdown(source)

question = st.chat_input("Pergunte algo sobre os documentos")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    retrieved_chunks = retrieve(retrieval_index, question, top_k=top_k)
    source_lines = [
        f"- {item.chunk.source}, página {item.chunk.page}, similaridade {item.score:.3f}"
        for item in retrieved_chunks
    ]

    if provider == "OpenAI API" and not api_key.strip():
        answer = "Defina uma API key para usar a OpenAI API."
    else:
        with st.spinner("Consultando o modelo..."):
            try:
                answer = ask_model(
                    question=question,
                    retrieved_chunks=retrieved_chunks,
                    chat_history=st.session_state.messages,
                    api_key=api_key.strip() or "ollama",
                    model=model.strip(),
                    base_url=base_url.strip(),
                )
            except Exception as exc:
                answer = f"Erro ao consultar o modelo: {exc}"

    assistant_message = {
        "role": "assistant",
        "content": answer,
        "sources": source_lines,
    }
    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.markdown(answer)
        if source_lines:
            with st.expander("Fontes usadas"):
                for source in source_lines:
                    st.markdown(source)

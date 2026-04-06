from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.llm import ChatSettings
from src.chatbot_fai_docs.pdfs import list_pdf_files


load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent


def default_value(name: str, fallback: str) -> str:
    return os.getenv(name, fallback)


def current_pdf_signature(pdf_files: list[Path]) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (pdf.name, pdf.stat().st_mtime_ns, pdf.stat().st_size) for pdf in pdf_files
    )


@st.cache_resource(show_spinner=False)
def load_rag_service(
    *,
    signature: tuple[tuple[str, int, int], ...],
    database_url: str,
    embedding_model: str,
    embedding_dimension: int,
    chunk_size: int,
    chunk_overlap: int,
):
    _signature = signature
    config = AppConfig(
        docs_dir=ROOT_DIR / "docs" / "sil",
        database_url=database_url,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    service = RagService(config)
    sync_result = service.sync_documents()
    return service, sync_result


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
st.caption("Chat simples para consultar documentos usando embeddings e Supabase.")

env_error = None
try:
    env_config = AppConfig.from_env(docs_dir=ROOT_DIR / "docs" / "sil")
except ValueError as exc:
    env_error = str(exc)
    env_config = None

with st.sidebar:
    st.header("Configuração")
    provider = st.selectbox("Modelo", ["OpenAI API", "Ollama local"])
    base_url_default, api_key_default, model_default = provider_defaults(provider)

    st.caption("Arquitetura: PDFs -> embeddings -> Supabase pgvector -> resposta")

    database_url = st.text_input(
        "DATABASE_URL do Supabase/Postgres",
        value=(env_config.database_url if env_config else ""),
        help="Use a connection string Postgres do projeto Supabase.",
    )

    base_url = st.text_input("Base URL", value=base_url_default)
    model = st.text_input("Modelo", value=model_default)
    api_key = st.text_input("API key", value=api_key_default, type="password")
    top_k = st.slider("Trechos recuperados", min_value=2, max_value=8, value=4)

    with st.expander("Embeddings"):
        embedding_model = st.text_input(
            "Modelo de embedding",
            value=(
                env_config.embedding_model
                if env_config
                else "sentence-transformers/all-MiniLM-L6-v2"
            ),
        )
        embedding_dimension = st.number_input(
            "Dimensão do embedding",
            min_value=1,
            value=(env_config.embedding_dimension if env_config else 384),
            step=1,
        )
        chunk_size = st.number_input(
            "Chunk size",
            min_value=300,
            value=(env_config.chunk_size if env_config else 1200),
            step=100,
        )
        chunk_overlap = st.number_input(
            "Chunk overlap",
            min_value=0,
            max_value=1000,
            value=(env_config.chunk_overlap if env_config else 200),
            step=50,
        )

    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

pdf_files = list_pdf_files(ROOT_DIR / "docs" / "sil")

if not pdf_files:
    st.error("Nenhum PDF foi encontrado em docs/sil.")
    st.stop()

if env_error and not database_url.strip():
    st.warning(env_error)
    st.stop()

signature = current_pdf_signature(pdf_files)
with st.spinner(
    "Lendo documentos, gerando embeddings e sincronizando a base vetorial..."
):
    try:
        rag_service, sync_result = load_rag_service(
            signature=signature,
            database_url=database_url.strip(),
            embedding_model=embedding_model,
            embedding_dimension=int(embedding_dimension),
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
        )
    except Exception as exc:
        st.error(f"Erro ao preparar o RAG: {exc}")
        st.stop()

st.info("Documentos carregados: " + ", ".join(pdf.name for pdf in pdf_files))
st.caption(
    f"Banco vetorial: {sync_result.backend} | PDFs: {sync_result.file_count} | Chunks indexados: {sync_result.chunk_count}"
)

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

    if provider == "OpenAI API" and not api_key.strip():
        answer = "Defina uma API key para usar a OpenAI API."
        search_results = []
    else:
        with st.spinner("Consultando o modelo..."):
            try:
                answer, search_results = rag_service.answer_question(
                    question=question,
                    chat_history=st.session_state.messages,
                    settings=ChatSettings(
                        api_key=api_key.strip() or "ollama",
                        model=model.strip(),
                        base_url=base_url.strip(),
                    ),
                    top_k=top_k,
                )
            except Exception as exc:
                answer = f"Erro ao consultar o modelo: {exc}"
                search_results = []

    source_lines = [
        f"- {item.chunk.source}, página {item.chunk.page}, similaridade {item.score:.3f}"
        for item in search_results
    ]

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

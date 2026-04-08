from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
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


def start_ollama():
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=0.2)
        return
    except Exception:
        pass
        
    try:
        if os.name == 'nt':
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
    except Exception:
        pass


def get_ollama_models(base_url: str) -> list[tuple[str, str]]:
    if not base_url:
        base_url = "http://localhost:11434"
    
    if base_url.endswith("/v1"):
        api_url = base_url[:-3] + "/api/tags"
    elif base_url.endswith("/v1/"):
        api_url = base_url[:-4] + "/api/tags"
    elif "/v1" in base_url:
        api_url = base_url.replace("/v1", "/api/tags")
    else:
        api_url = base_url.rstrip("/") + "/api/tags"

    try:
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                details = item.get("details", {})
                param_size = details.get("parameter_size", "?B")
                models.append((name, f"{name} ({param_size})"))
            return models
    except Exception:
        return []


@st.cache_resource(show_spinner=False)
def load_rag_service(
    *,
    signature: tuple[tuple[str, int, int], ...],
    database_url: str,
    embedding_model: str,
    embedding_dimension: int,
    chunk_size: int,
    chunk_overlap: int,
    reranker_model: str,
    reranker_threshold: float,
):
    config = AppConfig(
        docs_dir=ROOT_DIR / "docs" / "sil",
        database_url=database_url,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        reranker_model=reranker_model,
        reranker_threshold=reranker_threshold,
    )
    service = RagService(config)
    sync_result = service.sync_documents()
    return service, sync_result


def provider_defaults(provider: str) -> tuple[str, str, str]:
    if provider == "Ollama local":
        return (
            default_value("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            default_value("OLLAMA_API_KEY", "ollama"),
            default_value("OLLAMA_MODEL", "llama3.2:3b"),
        )
    elif provider == "Google Gemini":
        return (
            "",
            default_value("GEMINI_API_KEY", ""),
            default_value("GEMINI_MODEL", "gemini-2.5-flash"),
        )

    return (
        default_value("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        default_value("OPENAI_API_KEY", ""),
        default_value("OPENAI_MODEL", "gpt-4o-mini"),
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
    provider = st.selectbox("Modelo de Resposta (LLM)", ["OpenAI API", "Ollama local", "Google Gemini"])
    base_url_default, api_key_default, model_default = provider_defaults(provider)

    st.caption("Arquitetura: PDFs -> embeddings -> Supabase pgvector -> resposta")

    # Valores extraídos em background
    database_url = env_config.database_url if env_config else ""

    if provider == "OpenAI API":
        model = st.selectbox(
            "Modelo", 
            [
                "gpt-3.5-turbo",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4.1",
                "gpt-4.1-mini"
            ], 
            index=3
        )
        api_key = st.text_input("API key", value=api_key_default, type="password")
        base_url = base_url_default
    elif provider == "Google Gemini":
        model = st.selectbox("Modelo", ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"], index=0)
        api_key = st.text_input("API key", value=api_key_default, type="password")
        base_url = base_url_default
    else:
        base_url = base_url_default
        
        start_ollama()
        
        local_models = get_ollama_models(base_url)
        if local_models:
            model_options = [m[0] for m in local_models]
            model_labels = [m[1] for m in local_models]
            
            selected_idx = 0
            if model_default in model_options:
                selected_idx = model_options.index(model_default)
            
            selected_label = st.selectbox("Modelo", options=model_labels, index=selected_idx)
            model = model_options[model_labels.index(selected_label)]
        else:
            model = st.text_input("Modelo (ex: llama3.2:3b)", value=model_default)
            st.caption("Nenhum modelo local detectado ou Ollama não está rodando.")
            
        api_key = api_key_default

    top_k = st.slider("Trechos recuperados", min_value=2, max_value=8, value=4)

    with st.expander("Modelo RAG (Banco Vetorial e Embeddings)"):
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
        reranker_threshold = st.number_input(
            "Reranker threshold",
            value=(env_config.reranker_threshold if env_config else 0.0),
            step=0.1,
            format="%.2f"
        )
        reranker_model = st.text_input(
            "Modelo de Rerank",
            value=(env_config.reranker_model if env_config else "cross-encoder/ms-marco-MiniLM-L-6-v2")
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
            reranker_model=reranker_model,
            reranker_threshold=float(reranker_threshold),
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
    elif provider == "Google Gemini" and not api_key.strip():
        answer = "Defina uma API key para usar a API do Google Gemini."
        search_results = []
    else:
        status_container = st.status("Iniciando processamento...", expanded=True)
        try:
            def update_status(text):
                status_container.write(f"🔄 {text}")
                status_container.update(label=text)

            answer, search_results = rag_service.answer_question(
                question=question,
                chat_history=st.session_state.messages,
                settings=ChatSettings(
                    provider=provider,
                    api_key=api_key.strip() or ("ollama" if provider == "Ollama local" else ""),
                    model=model.strip(),
                    base_url=base_url.strip(),
                ),
                top_k=top_k,
                status_callback=update_status,
            )
            status_container.update(label="Contexto RAG finalizado!", state="complete", expanded=False)
        except Exception as exc:
            status_container.update(label="Erro no processo!", state="error")
            answer = f"Erro ao consultar o modelo: {exc}"
            search_results = []

    source_lines = [
        f"- {item.chunk.source}, página {item.chunk.page}, similaridade {item.score:.3f}"
        for item in search_results
    ]

    with st.chat_message("assistant"):
        if isinstance(answer, str):
            full_answer = answer
            st.markdown(full_answer)
        else:
            full_answer = st.write_stream(answer)
            
        if source_lines:
            with st.expander("Fontes usadas"):
                for src in source_lines:
                    st.write(src)

    assistant_message = {
        "role": "assistant",
        "content": full_answer,
        "sources": source_lines,
    }
    st.session_state.messages.append(assistant_message)

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.llm import ChatSettings, ChatClient
from src.chatbot_fai_docs.pdfs import list_pdf_files
from src.chatbot_fai_docs.repository import PostgresChatRepository

load_dotenv()
ROOT_DIR = Path(__file__).resolve().parent


def default_value(name: str, fallback: str) -> str:
    return os.getenv(name, fallback)


@st.cache_data(ttl=60, show_spinner=False)
def get_pdf_files(docs_dir: Path) -> list[Path]:
    """Cacheia a lista de PDFs por 60 segundos."""
    from src.chatbot_fai_docs.pdfs import list_pdf_files
    return list_pdf_files(docs_dir)

@st.cache_data(ttl=60, show_spinner=False)
def current_pdf_signature(pdf_files: list[Path]) -> tuple[tuple[str, int, int], ...]:
    """Cacheia a assinatura dos arquivos para evitar IO repetitivo."""
    return tuple(
        (pdf.name, pdf.stat().st_mtime_ns, pdf.stat().st_size) for pdf in pdf_files
    )

@st.cache_resource(show_spinner=False)
def get_app_config(docs_path: Path) -> AppConfig:
    """Singleton para as configurações de ambiente."""
    return AppConfig.from_env(docs_dir=docs_path)


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


@st.cache_data(ttl=300, show_spinner=False)
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
):
    config = AppConfig(
        docs_dir=ROOT_DIR / "docs" / "sil",
        database_url=database_url,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        reranker_model=reranker_model,
        reranker_threshold=0.0,
        lightrag_api_url=os.getenv("LIGHTRAG_API_URL", "http://localhost:9621").strip(),
    )
    service = RagService(config)
    return service

@st.cache_resource(show_spinner="Conectando ao banco de histórico...")
def load_chat_repository(database_url: str):
    repo = PostgresChatRepository(database_url)
    repo.ensure_ready()
    return repo


@st.cache_resource
def get_transcription_client():
    return None # Funcionalidade de voz desativada temporariamente


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


def stream_with_loading(generator, placeholder, time_placeholder, start_time):
    """Auxiliary to clear the thinking placeholder on the first chunk and update timer."""
    started = False
    usage = 0
    for item in generator:
        if isinstance(item, tuple):
            ctype, content = item
            if ctype == "usage":
                usage = content
                continue
            
            if not started:
                placeholder.empty()
                started = True
            
            elapsed = time.perf_counter() - start_time
            time_placeholder.caption(f"⏱️ {elapsed:.1f}s")
            yield content
        else:
            if not started:
                placeholder.empty()
                started = True
            
            elapsed = time.perf_counter() - start_time
            time_placeholder.caption(f"⏱️ {elapsed:.1f}s")
            yield item
    
    # Store usage in session state temporarily to be picked up
    st.session_state["last_usage"] = usage


def ollama_stream_handler(generator, placeholder, time_placeholder, start_time):
    """Handles (type, content) tuples from OllamaModel and updates timer."""
    started = False
    thought_container = None
    thought_text = ""
    usage = 0
    
    for item in generator:
        elapsed = time.perf_counter() - start_time
        time_placeholder.caption(f"⏱️ {elapsed:.1f}s")
        
        if isinstance(item, tuple):
            ctype, content = item
            if ctype == "thought":
                if thought_container is None:
                    placeholder.empty()
                    thought_container = st.expander("💭 Raciocínio da IA", expanded=True)
                thought_text += content
                thought_container.markdown(thought_text)
            elif ctype == "usage":
                usage = content
                continue
            else:
                if not started:
                    placeholder.empty()
                    started = True
                yield content
        else:
            if not started:
                placeholder.empty()
                started = True
            yield item
            
    # Store usage in session state temporarily
    st.session_state["last_usage"] = usage


st.set_page_config(page_title="Chatbot FAI Docs", page_icon="📄", layout="wide")

# Main title
st.title("🤖 FAI Chatbot: Consultor de Manuais")
st.caption("Chat simples para consultar documentos e manuais da FAI")

# Estilos globais (Animação Thinking)
st.markdown(
    """
    <style>
    .dots-container {
        display: flex;
        gap: 4px;
    }
    .dot {
        width: 6px;
        height: 6px;
        background-color: #666;
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out both;
    }
    .dot:nth-child(1) { animation-delay: -0.32s; }
    .dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }
    </style>
    """,
    unsafe_allow_html=True
)

env_error = None
docs_path = ROOT_DIR / "docs" / "sil"

try:
    env_config = get_app_config(docs_path)
    chat_repo = load_chat_repository(env_config.database_url)
except ValueError as exc:
    env_error = str(exc)
    env_config = None
    chat_repo = None

# Gerenciamento de Session State para Conversas
if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Configuração")

    # Seção de Histórico
    st.subheader("📜 Histórico")
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conv_id = None
        st.session_state.messages = []
        st.rerun()

    if chat_repo:
        history = chat_repo.list_conversations()
        for chat in history:
            cols = st.columns([0.8, 0.2])
            # Marcar a conversa ativa
            label = f"📍 {chat.title}" if st.session_state.current_conv_id == chat.id else chat.title
            if cols[0].button(label, key=f"chat_{chat.id}", use_container_width=True):
                st.session_state.current_conv_id = chat.id
                db_messages = chat_repo.get_messages(chat.id)
                st.session_state.messages = [
                    {
                        "role": m.role, 
                        "content": m.content, 
                        "sources": m.metadata.get("sources"),
                        "gen_time": m.metadata.get("gen_time"),
                        "usage": m.metadata.get("usage")
                    } 
                    for m in db_messages
                ]
                st.rerun()
            
            if cols[1].button("🗑️", key=f"del_{chat.id}"):
                chat_repo.delete_conversation(chat.id)
                if st.session_state.current_conv_id == chat.id:
                    st.session_state.current_conv_id = None
                    st.session_state.messages = []
                st.rerun()

    st.markdown("---")
    rag_engine = st.radio("Motor de Busca RAG", ["Supabase (Padrão)", "LightRAG (Grafo)"], help="Escolha o sistema de recuperação de contexto para comparar os resultados.")

    if rag_engine == "LightRAG (Grafo)":
        lightrag_mode = st.selectbox(
            "Modo LightRAG", 
            ["hybrid", "mix", "local", "global", "naive"],
            index=0,
            help="Modos do LightRAG:\n- **hybrid**: Combina modo local e global.\n- **mix**: Mistura grafo de conhecimento com busca por similaridade vetorial.\n- **local**: Foca em entidades próximas (detalhamento específico).\n- **global**: Busca focada em temas macroscópicos do grafo.\n- **naive**: Busca vetorial tradicional."
        )
        st.info("No modo LightRAG, configurações de interface, LLM, Embedding e reranker são controladas pelo LightRAG.")
        
        provider = "Omitido"
        model = ""
        api_key = ""
        base_url = ""
        database_url = env_config.database_url if env_config else ""
        top_k = 4
        reranker_threshold = 0.0
        do_sync = False
        embedding_model = env_config.embedding_model if env_config else "sentence-transformers/all-MiniLM-L6-v2"
        embedding_dimension = 384
        chunk_size = 1200
        chunk_overlap = 200
        reranker_model = env_config.reranker_model if env_config else "cross-encoder/ms-marco-MiniLM-L-6-v2"
        
    else:
        provider = st.selectbox("Modelo de Resposta (LLM)", ["OpenAI API", "Ollama local", "Google Gemini"])
        base_url_default, api_key_default, model_default = provider_defaults(provider)

        st.caption("Arquitetura: PDFs -> embeddings -> Supabase pgvector -> resposta")

        # Valores extraídos em background
        database_url = env_config.database_url if env_config else ""

        if provider == "OpenAI API":
            model = st.selectbox(
                "Modelo", 
                [
                    "gpt-4.1",
                    "gpt-4.1-mini",
                    "gpt-5.2",
                    "gpt-5.2-pro",
                    "gpt-5.4-mini",
                    "gpt-5.4-nano",
                    "gpt-5.4-pro",
                    "gpt-5.4"
                ], 
                index=0
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

        top_k = st.slider(
            "Trechos recuperados", 
            min_value=2, 
            max_value=8, 
            value=4,
            help="Define quantos fragmentos de texto dos documentos serão enviados como contexto para a IA."
        )

        reranker_threshold = st.slider(
            "Reranker threshold",
            min_value=0.0,
            max_value=1.0,
            value=(env_config.reranker_threshold if env_config else 0.0),
            step=0.05,
            help="Nota mínima de relevância para que um documento seja usado.",
        )

        do_sync = st.checkbox("Sincronizar PDFs ao iniciar", value=False, help="Verifica se há novos arquivos na pasta e envia para o Supabase.")

        with st.expander("Modelo RAG (Banco Vetorial e Embeddings)"):
            embedding_model = st.text_input(
                "Modelo Embedding",
                value=(env_config.embedding_model if env_config else "sentence-transformers/all-MiniLM-L6-v2"),
                help="O modelo usado para converter textos em vetores numéricos.",
                disabled=True,
            )
            embedding_dimension = st.number_input(
                "Dimensão do Embedding",
                min_value=1,
                value=(env_config.embedding_dimension if env_config else 384),
                step=1,
                help="Tamanho do vetor gerado pelo modelo (ex: 384, 768, 1536).",
                disabled=True,
            )
            chunk_size = st.number_input(
                "Chunk size",
                min_value=300,
                value=(env_config.chunk_size if env_config else 1200),
                step=100,
                help="Tamanho em caracteres de cada pedaço de texto extraído.",
                disabled=True,
            )
            chunk_overlap = st.number_input(
                "Chunk Overlap",
                min_value=0,
                max_value=1000,
                value=(env_config.chunk_overlap if env_config else 200),
                step=50,
                help="Quantidade de texto repetido entre pedaços consecutivos para manter o contexto.",
                disabled=True,
            )
            reranker_threshold = st.number_input(
                "Reranker threshold num", # Alterado label para evitar conflito com name
                value=(env_config.reranker_threshold if env_config else 0.0),
                step=0.1,
                format="%.2f",
                help="Nota mínima de relevância.",
                disabled=True,
            )
            reranker_model = st.text_input(
                "modelo rerank",
                value=(env_config.reranker_model if env_config else "cross-encoder/ms-marco-MiniLM-L-6-v2"),
                help="Modelo de segunda etapa que reordena os resultados para maior precisão.",
                disabled=True,
            )

    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.info("Para suporte técnico, entre em contato com o Setor de TI da FAI.")

pdf_files = get_pdf_files(docs_path)

if not pdf_files:
    st.error("Nenhum PDF foi encontrado em docs/sil.")
    st.stop()

if env_error and not database_url.strip():
    st.warning(env_error)
    st.stop()

signature = current_pdf_signature(pdf_files)
rag_service = None
sync_result = None

try:
    if rag_engine == "Supabase (Padrão)":
        rag_service = load_rag_service(
            signature=signature,
            database_url=database_url.strip(),
            embedding_model=embedding_model,
            embedding_dimension=int(embedding_dimension),
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
            reranker_model=reranker_model,
        )
        
        if do_sync:
            with st.status("Sincronizando PDFs com Supabase...", expanded=False) as status:
                sync_result = rag_service.sync_documents(force=True)
                status.update(label=f"Sincronização concluída: {sync_result.file_count} arquivos.", state="complete")
        else:
            # Recuperar estado atual sem forçar sincronização (rápido)
            sync_result = rag_service.sync_documents(force=False)
except Exception as exc:
    st.error(f"Erro ao preparar o RAG: {exc}")
    st.stop()

if rag_engine == "Supabase (Padrão)":
    st.info("Documentos carregados no Supabase: " + ", ".join(pdf.name for pdf in pdf_files))
    if sync_result:
        st.caption(
            f"Banco vetorial: {sync_result.backend} | PDFs: {sync_result.file_count} | Chunks sincronizados/detectados: {sync_result.chunk_count}"
        )
else:
    st.info("Modo LightRAG Ativo: As indexações são mapeadas externamente no GraphRAG Backend.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display generation time and token usage if available
        if "gen_time" in message:
            usage_str = f" | 🪙 Tokens (Resposta): {message['usage']}" if "usage" in message and message["usage"] > 0 else ""
            st.caption(f"⏱️ Tempo de geração: {message['gen_time']:.1f}s{usage_str}")
            
        sources = message.get("sources")
        if sources:
            with st.expander("Fontes usadas"):
                for source in sources:
                    st.markdown(source)

# Lógica de Input (Padrão Streamlit)
if question := st.chat_input("Pergunte algo sobre os documentos..."):
    start_time = time.perf_counter()
    st.session_state.messages.append({"role": "user", "content": question})
    st.rerun()

# Processar a última mensagem do usuário (se houver acabado de ser adicionada)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user" and "usage" not in st.session_state.messages[-1]:
    # Pegar a última pergunta do histórico
    current_question = st.session_state.messages[-1]["content"]
    
    with st.chat_message("assistant"):
        t_placeholder = st.empty()
        
        # Inicializar e exibir o spinner imediatamente
        p = st.empty()
        p.markdown(
            """
            <div style="display: flex; align-items: center; gap: 10px; font-style: italic; color: #666;">
                <span>💭 Pensando</span>
                <div class="dots-container">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        if rag_engine == "LightRAG (Grafo)":
            from src.chatbot_fai_docs.lightrag_service import LightRagService
            
            try:
                lightrag_service = LightRagService(config=env_config)
                answer, search_results, source_lines = lightrag_service.answer_question_stream(current_question, lightrag_mode)
            except Exception as exc:
                answer = f"Erro ao consultar o LightRAG Server: {exc}"
                search_results = []
                source_lines = []
                
        else:
            if provider == "OpenAI API" and not api_key.strip():
                answer = "Defina uma API key para usar a OpenAI API."
                search_results = []
                source_lines = []
            elif provider == "Google Gemini" and not api_key.strip():
                answer = "Defina uma API key para usar a API do Google Gemini."
                search_results = []
                source_lines = []
            else:
                try:
                    answer, search_results = rag_service.answer_question(
                        question=current_question,
                        chat_history=st.session_state.messages,
                        settings=ChatSettings(
                            provider=provider,
                            api_key=api_key.strip() or ("ollama" if provider == "Ollama local" else ""),
                            model=model.strip(),
                            base_url=base_url.strip(),
                        ),
                        top_k=top_k,
                        reranker_threshold=reranker_threshold,
                    )
                except Exception as exc:
                    answer = f"Erro ao consultar o modelo: {exc}"
                    search_results = []
                    source_lines = []
            
            source_lines = [
                f"- {item.chunk.source}, página {item.chunk.page}, similaridade {item.score:.3f}"
                for item in search_results
            ]

        # Iniciar cronômetro apenas para a fase de geração (LLM)
        start_time = time.perf_counter()

        if isinstance(answer, str):
            p.empty()
            st.markdown(answer)
            full_answer = answer
        else:
            if provider == "Ollama local" or rag_engine == "LightRAG (Grafo)":
                full_answer = st.write_stream(ollama_stream_handler(answer, p, t_placeholder, start_time))
            else:
                full_answer = st.write_stream(stream_with_loading(answer, p, t_placeholder, start_time))
            
        final_time = time.perf_counter() - start_time
        final_usage = st.session_state.get("last_usage", 0)
        
        usage_label = f" | 🪙 Tokens (Resposta): {final_usage}" if final_usage > 0 else ""
        t_placeholder.caption(f"⏱️ Tempo de geração: {final_time:.1f}s{usage_label}")

        if source_lines:
            with st.expander("Fontes usadas"):
                for src in source_lines:
                    st.write(src)

        # Lifecycle de Salvamento (Supabase)
        if chat_repo:
            # Se for uma conversa nova, criar o registro e gerar título
            if st.session_state.current_conv_id is None:
                chat_client = ChatClient()
                try:
                    # Lógica de prioridade para o título:
                    # 1. Modelo selecionado na UI (se houver)
                    # 2. Modelo do arquivo .env (OLLAMA_MODEL)
                    # 3. Fallback final para gpt-4o-mini (se houver API Key)
                    
                    env_openai_key = os.getenv("OPENAI_API_KEY", "")
                    title_api_key = api_key.strip() or env_openai_key
                    
                    # Tentar primeiro o modelo local configurado
                    local_model_name = model.strip() if (model and model != "") else os.getenv("OLLAMA_MODEL", "")
                    
                    if local_model_name:
                        title_provider = "Ollama local"
                        title_api_key = "ollama"
                        title_model = local_model_name
                    elif title_api_key and title_api_key != "ollama":
                        title_provider = "OpenAI API"
                        title_model = "gpt-4o-mini"
                    else:
                        # Fallback extremo caso nada esteja configurado
                        title_provider = "Ollama local"
                        title_api_key = "ollama"
                        title_model = "llama3.2:3b"

                    suggested_title = chat_client.generate_title(current_question, ChatSettings(
                        provider=title_provider,
                        api_key=title_api_key,
                        model=title_model,
                        base_url=base_url.strip() if base_url else None
                    ))
                except Exception as e:
                    st.warning(f"Erro ao gerar título automático: {e}")
                    suggested_title = current_question[:30] + "..."
                
                st.session_state.current_conv_id = chat_repo.create_conversation(
                    title=suggested_title,
                    rag_engine=rag_engine
                )
                # Salvar a mensagem inicial do usuário
                chat_repo.add_message(st.session_state.current_conv_id, "user", current_question)

            # Salvar a resposta da IA
            chat_repo.add_message(
                st.session_state.current_conv_id, 
                "assistant", 
                full_answer, 
                metadata={
                    "sources": source_lines,
                    "gen_time": final_time,
                    "usage": final_usage
                }
            )

        assistant_message = {
            "role": "assistant",
            "content": full_answer,
            "sources": source_lines,
            "gen_time": final_time,
            "usage": final_usage,
        }
        st.session_state.messages.append(assistant_message)

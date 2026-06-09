import json
import time
import requests
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.schemas.chat_schema import ChatRequest
from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.llm import ChatSettings, ChatClient
from src.chatbot_fai_docs.repository import get_repo_from_url
from src.chatbot_fai_docs.lightrag_service import LightRagService

router = APIRouter()

def get_repo():
    # Persistencia do historico independe do motor RAG: usa Postgres se DATABASE_URL
    # estiver configurado, senao cai no repo em memoria (fallback de desenvolvimento).
    repo = get_repo_from_url(settings.DATABASE_URL)
    # ensure_ready is a no-op for in-memory repo
    repo.ensure_ready()
    return repo

@router.post("/stream")
async def chat_stream(request: ChatRequest, repo = Depends(get_repo)):
    """
    Endpoint de chat com streaming. Usa LightRAG por padrão; também suporta mecanismos alternativos se configurados.
    """
    
    def generate_response():
        start_time = time.perf_counter()
        conversation_id = request.conversation_id
        
        # 1. Preparar Contexto
        config = AppConfig(
            docs_dir=settings.DOCS_DIR,
            database_url=settings.DATABASE_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            reranker_model=settings.RERANKER_MODEL,
            reranker_threshold=settings.RERANKER_THRESHOLD,
            lightrag_api_url=settings.LIGHTRAG_API_URL
        )

        # Carregar historico anterior da conversa (turnos previos) para dar contexto ao LightRAG.
        # A pergunta atual NAO entra aqui; ela vai separada no parametro `query`.
        try:
            prior = repo.get_messages(conversation_id, request.user_id) if conversation_id else []
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in prior if m.role in ("user", "assistant")
            ][-(settings.HISTORY_TURNS * 2):]
        except Exception as e:
            print(f"Erro ao carregar historico: {e}")
            conversation_history = []

        # Force LightRAG (Grafo) as Supabase/Postgres is deactivated
        try:
            lightrag_service = LightRagService(config=config)
            answer, _, source_lines = lightrag_service.answer_question_stream(
                request.question,
                request.mode,
                conversation_history=conversation_history,
                history_turns=settings.HISTORY_TURNS,
            )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # 2. Processar Resposta (Streaming ou String)
        full_answer = ""
        last_usage = 0
        
        if isinstance(answer, str):
            full_answer = answer
            yield f"data: {json.dumps({'content': answer, 'sources': source_lines})}\n\n"
        else:
            # Gerador de streaming
            for item in answer:
                chunk_content = ""
                if isinstance(item, tuple):
                    ctype, content = item
                    if ctype == "usage":
                        last_usage = content
                        continue
                    chunk_content = content
                else:
                    chunk_content = item
                
                full_answer += chunk_content
                yield f"data: {json.dumps({'content': chunk_content})}\n\n"

        # 3. Finalizar e Salvar no Backend
        final_time = time.perf_counter() - start_time
        
        try:
            # Gerar título se for nova conversa
            if not conversation_id:
                chat_client = ChatClient()
                # Simplificação: Usar gpt-4o-mini ou modelo local para título
                title_settings = ChatSettings(
                    provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                    api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                    model="llama3.2:3b" if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                    base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None
                )
                try:
                    suggested_title = chat_client.generate_title(request.question, title_settings)
                except Exception as e:
                    print(f"Erro ao gerar título: {e}")
                    suggested_title = request.question[:30] + "..."
                
                conversation_id = repo.create_conversation(
                    title=suggested_title,
                    rag_engine=request.rag_engine,
                    user_id=request.user_id,
                )
                repo.add_message(conversation_id, "user", request.question)
            else:
                # Conversa existente: persistir a pergunta deste turno (faltava antes)
                repo.add_message(conversation_id, "user", request.question)

            # Salvar resposta da IA
            repo.add_message(
                conversation_id, 
                "assistant", 
                full_answer, 
                metadata={
                    "sources": source_lines,
                    "gen_time": final_time,
                    "usage": last_usage
                }
            )
            
            # Enviar evento final com metadados
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'gen_time': final_time, 'usage': last_usage, 'sources': source_lines})}\n\n"
        except Exception as e:
            print(f"Erro ao persistir histórico: {e}")
            yield f"data: {json.dumps({'error': 'Erro ao salvar histórico: ' + str(e)})}\n\n"

    return StreamingResponse(generate_response(), media_type="text/event-stream")

@router.get("/ollama/models")
async def get_ollama_models():
    """
    Busca os modelos locais disponíveis no Ollama.
    """
    # Usando o padrão /api/tags que é a API correta do Ollama
    base_url = settings.OLLAMA_BASE_URL.rstrip("/") if hasattr(settings, "OLLAMA_BASE_URL") and settings.OLLAMA_BASE_URL else "http://localhost:11434"
    # Ajuste: se a URL terminar em /v1, removemos pois tags fica em /api/tags
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
        
    try:
        url = f"{base_url}/api/tags"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                param_size = item.get("details", {}).get("parameter_size", "unknown")
                models.append({"name": name, "label": f"{name} ({param_size})"})
            return models
        else:
            return []
    except Exception as e:
        print(f"Erro ao buscar modelos Ollama: {e}")
        return []

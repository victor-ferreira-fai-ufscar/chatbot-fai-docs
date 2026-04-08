from __future__ import annotations
from typing import Any

from .config import AppConfig
from .embeddings import EmbeddingClient, RerankerClient
from .llm import ChatClient, ChatSettings
import json
from .models import SearchResult, SyncResult
from .pdfs import build_chunks, list_pdf_files
from .utils import get_file_hash
from .vector_store import build_vector_store


class RagService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.embedder = EmbeddingClient(config.embedding_model)
        if self.embedder.dimension != config.embedding_dimension:
            raise ValueError(
                "A dimensao configurada em EMBEDDING_DIMENSION nao corresponde ao modelo de embedding escolhido."
            )
        self.vector_store = build_vector_store(
            database_url=config.database_url,
            embedding_dimension=config.embedding_dimension,
        )
        self.vector_store.ensure_ready()
        self.reranker = RerankerClient(config.reranker_model)
        self.chat_client = ChatClient()

    def sync_documents(self) -> SyncResult:
        pdf_files = list_pdf_files(self.config.docs_dir)
        
        sync_state_file = self.config.docs_dir / ".sync_state.json"
        old_state = {}
        if sync_state_file.exists():
            try:
                old_state = json.loads(sync_state_file.read_text("utf-8"))
            except Exception:
                pass
                
        new_state = {}
        modified_or_new_files = []
        current_filenames = set()
        
        for pdf in pdf_files:
            file_hash = get_file_hash(pdf)
            new_state[pdf.name] = file_hash
            current_filenames.add(pdf.name)
            
            if old_state.get(pdf.name) != file_hash:
                modified_or_new_files.append(pdf)
                
        deleted_files = [name for name in old_state if name not in current_filenames]
        
        sources_to_delete = deleted_files + [pdf.name for pdf in modified_or_new_files]
        if sources_to_delete:
            self.vector_store.delete_by_source(sources_to_delete)

        if modified_or_new_files:
            chunks = build_chunks(
                modified_or_new_files,
                chunk_size=self.config.chunk_size,
                overlap=self.config.chunk_overlap,
            )
            if chunks:
                embeddings = self.embedder.embed_texts([chunk.content for chunk in chunks])
                self.vector_store.upsert(chunks, embeddings)
        
        sync_state_file.write_text(json.dumps(new_state, indent=2), "utf-8")

        return SyncResult(
            file_count=len(pdf_files),
            chunk_count=self.vector_store.count(),
            backend=self.vector_store.backend_name,
        )

    def answer_question(
        self,
        *,
        question: str,
        chat_history: list[dict[str, str]],
        settings: ChatSettings,
        top_k: int,
        status_callback=None,
    ) -> tuple[Any, list[SearchResult]]:
        if status_callback:
            status_callback("Consultando documentos na base vetorial...")
        query_embedding = self.embedder.embed_query(question)
        
        # Two-stage retrieval: Fetch more candidates first
        fetch_k = top_k * 4
        raw_results = self.vector_store.search(query_embedding, top_k=fetch_k)
        
        if status_callback:
            status_callback("Aplicando Re-ranking de relevância cruzada...")
        search_results = self.reranker.rerank(question, raw_results, top_k=top_k)
        
        # Filter by threshold
        search_results = [res for res in search_results if res.score >= self.config.reranker_threshold]
        
        if status_callback:
            status_callback("Puxando conexões e montando resposta...")
        answer = self.chat_client.answer(
            question=question,
            search_results=search_results,
            chat_history=chat_history,
            settings=settings,
        )
        
        return answer, search_results

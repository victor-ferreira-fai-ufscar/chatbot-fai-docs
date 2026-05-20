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

    def sync_documents(self, force: bool = False) -> SyncResult:
        """
        Sincroniza os arquivos locais com o banco vetorial.
        Usa metadados (mtime/size) para rapidez.
        """
        if not force:
            # Se não for forçado, podemos apenas retornar o estado atual do banco
            # para economizar tempo de disco
            return SyncResult(
                file_count=len(list_pdf_files(self.config.docs_dir)),
                chunk_count=self.vector_store.count(),
                backend=self.vector_store.backend_name,
            )

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
            # Usar mtime + size como 'hash' rapido para evitar ler o arquivo todo
            stats = pdf.stat()
            file_meta = f"{stats.st_mtime_ns}-{stats.st_size}"
            new_state[pdf.name] = file_meta
            current_filenames.add(pdf.name)
            
            if old_state.get(pdf.name) != file_meta:
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
        reranker_threshold: float | None = None,
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
        threshold = reranker_threshold if reranker_threshold is not None else self.config.reranker_threshold
        search_results = [res for res in search_results if res.score >= threshold]
        
        if status_callback:
            status_callback("Puxando conexões e montando resposta...")
            
        pdf_files = list_pdf_files(self.config.docs_dir)
        available_docs = [f.name for f in pdf_files]

        answer = self.chat_client.answer(
            question=question,
            search_results=search_results,
            chat_history=chat_history,
            settings=settings,
            available_docs=available_docs,
        )
        
        return answer, search_results

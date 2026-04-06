from __future__ import annotations

from .config import AppConfig
from .embeddings import EmbeddingClient
from .llm import ChatClient, ChatSettings
from .models import SearchResult, SyncResult
from .pdfs import build_chunks, list_pdf_files
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
        self.chat_client = ChatClient()

    def sync_documents(self) -> SyncResult:
        pdf_files = list_pdf_files(self.config.docs_dir)
        chunks = build_chunks(
            pdf_files,
            chunk_size=self.config.chunk_size,
            overlap=self.config.chunk_overlap,
        )
        embeddings = self.embedder.embed_texts([chunk.content for chunk in chunks])
        self.vector_store.upsert(chunks, embeddings)
        self.vector_store.delete_missing({chunk.id for chunk in chunks})
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
    ) -> tuple[str, list[SearchResult]]:
        query_embedding = self.embedder.embed_query(question)
        search_results = self.vector_store.search(query_embedding, top_k=top_k)
        answer = self.chat_client.answer(
            question=question,
            search_results=search_results,
            chat_history=chat_history,
            settings=settings,
        )
        return answer, search_results

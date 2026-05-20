from __future__ import annotations

from sentence_transformers import SentenceTransformer, CrossEncoder
from .models import SearchResult
from dataclasses import replace
class EmbeddingClient:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model_instance = None

    @property
    def _model(self):
        if self._model_instance is None:
            self._model_instance = SentenceTransformer(self.model_name, device="cpu")
        return self._model_instance

    @property
    def dimension(self) -> int:
        value = self._model.get_sentence_embedding_dimension()
        if value is None:
            raise ValueError(
                "Nao foi possivel identificar a dimensao do modelo de embedding."
            )
        return int(value)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

class RerankerClient:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model_instance = None

    @property
    def _model(self):
        if self._model_instance is None:
            self._model_instance = CrossEncoder(self.model_name, device="cpu")
        return self._model_instance

    def rerank(self, query: str, search_results: list[SearchResult], top_k: int) -> list[SearchResult]:
        if not search_results:
            return []
            
        pairs = [[query, result.chunk.content] for result in search_results]
        scores = self._model.predict(pairs)
        
        updated_results = []
        for i, result in enumerate(search_results):
            updated_result = replace(result, score=float(scores[i]))
            updated_results.append(updated_result)
        
        updated_results.sort(key=lambda x: x.score, reverse=True)
        return updated_results[:top_k]

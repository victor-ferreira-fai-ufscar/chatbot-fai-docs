from __future__ import annotations

from sentence_transformers import SentenceTransformer


class EmbeddingClient:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

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

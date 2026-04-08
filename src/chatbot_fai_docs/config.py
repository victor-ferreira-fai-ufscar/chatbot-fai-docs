from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    docs_dir: Path
    database_url: str
    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    reranker_model: str
    reranker_threshold: float

    @classmethod
    def from_env(cls, *, docs_dir: Path | None = None) -> "AppConfig":
        database_url = (os.getenv("DATABASE_URL") or "").strip()
        if not database_url:
            raise ValueError("Defina DATABASE_URL para conectar ao Postgres/Supabase.")

        return cls(
            docs_dir=docs_dir or ROOT_DIR / "docs" / "sil",
            database_url=database_url,
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ).strip(),
            embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "384")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "500")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            reranker_model=os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2").strip(),
            reranker_threshold=float(os.getenv("RERANKER_THRESHOLD", "0.0")),
        )

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    docs_dir: Path
    database_url: str | None
    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    reranker_model: str
    reranker_threshold: float
    lightrag_api_url: str
    # Chave enviada no header X-API-Key quando o servidor LightRAG exige autenticacao
    lightrag_api_key: str | None = None
    # Endpoint do reranker (mesmo usado pelo LightRAG) p/ RE-PONTUAR os chunks finais
    # e exibir a relevancia (%) por pagina nas fontes. None = nao pontua.
    rerank_url: str | None = None
    # Fallback de recuperacao: se a busca COM reranker devolver contexto vazio, refaz com
    # enable_rerank=False (chunks pela ordem do embedding, que casa sinonimos que o
    # cross-encoder perde). Preenchido pelo endpoint a partir de RERANK_FALLBACK_ENABLED.
    rerank_fallback_enabled: bool = False
    # Fallback de resiliencia: se o LightRAG falhar, responde pela base vetorial Supabase
    # (pgvector) + Ollama. Preenchido pelo endpoint a partir de SUPABASE_FALLBACK_ENABLED.
    supabase_fallback_enabled: bool = False
    # Cascata de APROFUNDAMENTO do retrieval (2026-07-21; ver comentarios em
    # app/core/config.py). Defaults conservadores (off) no dataclass — quem liga e o
    # endpoint, a partir das Settings (mesmo padrao do rerank_fallback_enabled).
    retrieval_deepen_enabled: bool = False
    retrieval_weak_min_chunks: int = 3
    retrieval_weak_max_score: float = 0.35
    retrieval_escalation_enabled: bool = False
    retrieval_escalation_top_k: int = 32
    retrieval_escalation_chunk_top_k: int = 20
    retrieval_escalation_entity_tokens: int = 5000
    retrieval_escalation_relation_tokens: int = 4500
    query_rewrite_enabled: bool = False
    query_rewrite_pgvector_hints: bool = False
    recall_channel_pgvector_enabled: bool = False
    # Substrings (lower) dos manuais APOSENTADOS que nao podem reaparecer em saida
    # nenhuma (ver RETIRED_MANUAL_PATTERNS em app/core/config.py). Usado p/ excluir
    # seus chunks do pgvector no fallback e nas dicas de vocabulario. () = nao filtra.
    retired_manual_patterns: tuple = ()

    @classmethod
    def from_env(cls, *, docs_dir: Path | None = None) -> "AppConfig":
        database_url = (os.getenv("DATABASE_URL") or "").strip() or None

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
            lightrag_api_url=os.getenv("LIGHTRAG_API_URL", "http://localhost:9621").strip(),
            lightrag_api_key=(os.getenv("LIGHTRAG_API_KEY") or "").strip() or None,
            rerank_url=(os.getenv("RERANK_URL", "http://localhost:7997/rerank").strip() or None),
            retired_manual_patterns=tuple(
                p.strip().lower() for p in os.getenv("RETIRED_MANUAL_PATTERNS", "").split(",")
                if p.strip()
            ),
        )


def is_retired_manual(name: str, patterns) -> bool:
    """True se `name` (nome de manual/source) casa qualquer substring aposentada."""
    low = (name or "").lower()
    return any(p in low for p in (patterns or ()))


def retired_ilike_patterns(patterns) -> list:
    """Converte as substrings aposentadas em padroes ILIKE ('%sistema%') p/ o SQL."""
    return [f"%{p}%" for p in (patterns or ()) if p]

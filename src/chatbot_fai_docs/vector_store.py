from __future__ import annotations

from pgvector import Vector
from pgvector.psycopg import register_vector
import psycopg

from .models import DocumentChunk, SearchResult


class PostgresVectorStore:
    backend_name = "supabase-postgres"

    def __init__(self, *, database_url: str, embedding_dimension: int) -> None:
        self.database_url = database_url
        self.embedding_dimension = embedding_dimension

    def ensure_ready(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        embedding VECTOR({self.embedding_dimension}) NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            connection.commit()

    def upsert(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> None:
        if not chunks:
            return

        rows = [
            (
                chunk.id,
                chunk.source,
                chunk.page,
                chunk.content,
                chunk.content_hash,
                Vector(embedding),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO document_chunks (
                        chunk_id,
                        source,
                        page,
                        content,
                        content_hash,
                        embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        content = EXCLUDED.content,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                    """,
                    rows,
                )
            connection.commit()

    def delete_missing(self, active_chunk_ids: set[str]) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if not active_chunk_ids:
                    cursor.execute("DELETE FROM document_chunks")
                else:
                    cursor.execute(
                        "DELETE FROM document_chunks WHERE NOT (chunk_id = ANY(%s))",
                        (list(active_chunk_ids),),
                    )
            connection.commit()

    def search(self, query_embedding: list[float], top_k: int) -> list[SearchResult]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        chunk_id,
                        source,
                        page,
                        content,
                        content_hash,
                        1 - (embedding <=> %s) AS score
                    FROM document_chunks
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (Vector(query_embedding), Vector(query_embedding), top_k),
                )
                rows = cursor.fetchall()

        return [
            SearchResult(
                chunk=DocumentChunk(
                    id=row[0],
                    source=row[1],
                    page=row[2],
                    content=row[3],
                    content_hash=row[4],
                ),
                score=float(row[5]),
            )
            for row in rows
            if float(row[5]) > 0
        ]

    def count(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM document_chunks")
                row = cursor.fetchone()
                return int(row[0]) if row else 0

    def _connect(self) -> psycopg.Connection:
        connection = psycopg.connect(self.database_url)
        register_vector(connection)
        return connection


def build_vector_store(
    *, database_url: str, embedding_dimension: int
) -> PostgresVectorStore:
    return PostgresVectorStore(
        database_url=database_url,
        embedding_dimension=embedding_dimension,
    )

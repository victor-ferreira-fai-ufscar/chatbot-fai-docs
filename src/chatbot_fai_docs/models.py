from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    source: str
    page: int
    content: str
    content_hash: str


@dataclass(frozen=True)
class SearchResult:
    chunk: DocumentChunk
    score: float


@dataclass(frozen=True)
class SyncResult:
    file_count: int
    chunk_count: int
    backend: str

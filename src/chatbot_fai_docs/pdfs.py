from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentChunk


def list_pdf_files(docs_dir: Path) -> list[Path]:
    return sorted(docs_dir.glob("*.pdf"))


def normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start = max(end - overlap, start + 1)

    return chunks


def build_chunks(
    pdf_files: list[Path], *, chunk_size: int, overlap: int
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    for pdf_file in pdf_files:
        reader = PdfReader(str(pdf_file))
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = normalize_text(page.extract_text() or "")
            if not page_text:
                continue

            split_chunks = split_text(
                page_text,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            for chunk_index, chunk_text in enumerate(split_chunks, start=1):
                chunk_id = hashlib.sha1(
                    f"{pdf_file.name}:{page_number}:{chunk_index}".encode("utf-8")
                ).hexdigest()
                content_hash = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        source=pdf_file.name,
                        page=page_number,
                        content=chunk_text,
                        content_hash=content_hash,
                    )
                )

    return chunks

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pymupdf4llm

from .models import DocumentChunk


def list_pdf_files(docs_dir: Path) -> list[Path]:
    return sorted(docs_dir.glob("*.pdf"))


def normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    # Remover espaços múltiplos consecutivos nas horizontais, manter quebras de linha Markdown
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    # Reduzir excesso de quebras de linha verticais seguidas por apenas duas para manter a leitura limpa
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
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
        try:
            # page_chunks=True faz com que devolva uma lista de dicts (um para cada página com o texto markdown)
            md_pages = pymupdf4llm.to_markdown(str(pdf_file), page_chunks=True)
            
            for global_idx, md_page in enumerate(md_pages, start=1):
                # PyMuPDF4LLM usa 'page_number' ao envés de 'page', mas o fallback pelo global_idx evita falhas
                page_number = md_page.get("metadata", {}).get("page_number", global_idx)
                page_text = normalize_text(md_page.get("text", ""))
                
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
        except Exception as e:
            print(f"Erro ao converter o documento {pdf_file.name} usando pymupdf4llm: {e}")

    return chunks

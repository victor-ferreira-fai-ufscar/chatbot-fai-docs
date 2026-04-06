from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs" / "sil"


@dataclass(frozen=True)
class Chunk:
    source: str
    page: int
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class RetrievalIndex:
    chunks: list[Chunk]
    vectorizer: TfidfVectorizer
    matrix: object


def list_pdf_files() -> list[Path]:
    return sorted(DOCS_DIR.glob("*.pdf"))


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 1400, overlap: int = 250) -> list[str]:
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


def extract_chunks(
    pdf_path: Path, chunk_size: int = 1400, overlap: int = 250
) -> list[Chunk]:
    reader = PdfReader(str(pdf_path))
    chunks: list[Chunk] = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = normalize_text(page.extract_text() or "")
        if not page_text:
            continue

        for chunk_text in split_text(page_text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(
                Chunk(source=pdf_path.name, page=page_number, text=chunk_text)
            )

    return chunks


def build_index(
    pdf_files: list[Path], chunk_size: int = 1400, overlap: int = 250
) -> RetrievalIndex | None:
    chunks: list[Chunk] = []
    for pdf_file in pdf_files:
        chunks.extend(extract_chunks(pdf_file, chunk_size=chunk_size, overlap=overlap))

    if not chunks:
        return None

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode")
    matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
    return RetrievalIndex(chunks=chunks, vectorizer=vectorizer, matrix=matrix)


def retrieve(
    index: RetrievalIndex, question: str, top_k: int = 4
) -> list[RetrievedChunk]:
    question_vector = index.vectorizer.transform([question])
    similarities = linear_kernel(question_vector, index.matrix).flatten()
    ranked_indexes = similarities.argsort()[::-1]

    results: list[RetrievedChunk] = []
    for item_index in ranked_indexes:
        score = float(similarities[item_index])
        if score <= 0:
            continue
        results.append(RetrievedChunk(chunk=index.chunks[item_index], score=score))
        if len(results) >= top_k:
            break

    return results


def build_context(retrieved_chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for item in retrieved_chunks:
        parts.append(
            f"Fonte: {item.chunk.source} | Página: {item.chunk.page} | Similaridade: {item.score:.3f}\n"
            f"Trecho: {item.chunk.text}"
        )
    return "\n\n".join(parts)


def ask_model(
    *,
    question: str,
    retrieved_chunks: list[RetrievedChunk],
    chat_history: list[dict[str, str]],
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    context = build_context(retrieved_chunks)

    history_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in chat_history[-6:]
        if item["role"] in {"user", "assistant"}
    ]

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é um assistente para consulta de manuais institucionais. "
                    "Responda em português do Brasil. Use apenas o contexto fornecido quando ele for suficiente. "
                    "Se a resposta não estiver clara nos trechos recuperados, diga isso explicitamente e indique a limitação."
                ),
            },
            *history_messages,
            {
                "role": "user",
                "content": (
                    "Pergunta do usuário:\n"
                    f"{question}\n\n"
                    "Contexto recuperado dos documentos:\n"
                    f"{context if context else 'Nenhum trecho relevante foi recuperado.'}\n\n"
                    "Ao responder, cite o nome do arquivo e a página quando usar informações do contexto."
                ),
            },
        ],
    )

    return response.choices[0].message.content or "Não foi possível gerar uma resposta."

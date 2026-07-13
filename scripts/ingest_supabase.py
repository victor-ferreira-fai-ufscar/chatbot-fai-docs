#!/usr/bin/env python3
"""Ingestao de UM PDF na base vetorial Supabase/pgvector (tabela document_chunks).

Primeiro momento do RAG vetorial: sobe o documento "da forma correta", com foco em
PRECISAO DE PAGINA. NAO liga a busca nem troca o motor do chat (segue LightRAG).

Pipeline (page-aware, sem cruzar fronteira de pagina -> pagina 100% exata):
  1. Extracao LAYOUT-AWARE por pagina via pdf_pages._extract_pages (descarta menu
     lateral / cabecalho por coordenada x, ordena as 2 colunas na ordem de leitura,
     remove a paginacao do PDF). A pagina retornada e 1-based = ancora #page=N.
  2. Chunking SENTENCE-AWARE dentro de cada pagina: empacota frases ate ~chunk_size
     chars com overlap de ~overlap chars (snap em fronteira de palavra); frase gigante
     e cortada em fronteira de palavra. O chunk recebe o prefixo "[PAGINA N] " no
     conteudo ARMAZENADO (compativel com o regex de citacao _PAGE_MARK_RE ja existente).
  3. Embedding com BAAI/bge-m3 (1024-dim, normalizado). O EMBEDDING usa o corpo LIMPO
     (sem o marcador) para casar com as queries futuras (que nao terao marcador).
  4. Upsert em document_chunks (recria a tabela em VECTOR(dim) se preciso).

Reutiliza (sem modificar) os utilitarios estaveis do pacote:
  pdf_pages._extract_pages, models.DocumentChunk, embeddings.EmbeddingClient,
  vector_store.build_vector_store.

Execucao (dentro do container backend, que tem DATABASE_URL, deps e o PDF montado):
  docker cp scripts/ingest_supabase.py fai_chatbot_backend:/tmp/ingest_supabase.py
  docker exec -w /app -e PYTHONPATH=/app fai_chatbot_backend \\
    python3 /tmp/ingest_supabase.py \\
      --pdf "/app/docs/manual/M-coordenadoresFAI-06-05- comentarios Silvana 01junho.pdf" \\
      --model BAAI/bge-m3 --dim 1024 --chunk-size 1000 --overlap 150 --reset
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections import Counter

# Utilitarios estaveis do pacote (PYTHONPATH=/app dentro do container)
from src.chatbot_fai_docs.pdf_pages import _extract_pages
from src.chatbot_fai_docs.models import DocumentChunk
from src.chatbot_fai_docs.embeddings import EmbeddingClient
from src.chatbot_fai_docs.vector_store import build_vector_store

import psycopg

# Fim de frase: ponto/!/?/:/; seguido de espaco. Mesma ideia do preprocess_page_marked.py.
_SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+")


def _hard_split(sentence: str, hard_cap: int) -> list[str]:
    """Quebra uma frase gigante (> hard_cap) em fronteira de palavra."""
    out: list[str] = []
    s = sentence.strip()
    while len(s) > hard_cap:
        cut = s.rfind(" ", 0, hard_cap)
        if cut <= 0:
            cut = hard_cap  # palavra unica gigantesca: corte seco
        out.append(s[:cut].strip())
        s = s[cut:].strip()
    if s:
        out.append(s)
    return out


def _pack_sentences(text: str, *, chunk_size: int, overlap: int, hard_cap: int) -> list[str]:
    """Empacota frases ate ~chunk_size chars, com overlap de ~overlap chars (snap em espaco)."""
    sents: list[str] = []
    for raw in _SENT_SPLIT.split(text):
        raw = raw.strip()
        if not raw:
            continue
        sents.extend(_hard_split(raw, hard_cap) if len(raw) > hard_cap else [raw])

    chunks: list[str] = []
    cur = ""
    for s in sents:
        if cur and len(cur) + 1 + len(s) > chunk_size:
            chunks.append(cur)
            if overlap > 0:
                tail = cur[-overlap:]
                sp = tail.find(" ")           # nao comeca no meio de uma palavra
                tail = tail[sp + 1:] if sp != -1 else tail
                cur = (tail + " " + s).strip()
            else:
                cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur:
        chunks.append(cur)
    return chunks


def build_page_chunks(
    pdf_bytes: bytes, source: str, *, chunk_size: int, overlap: int, add_marker: bool
) -> tuple[list[DocumentChunk], list[str], Counter]:
    """Retorna (chunks, embed_texts, chunks_por_pagina).

    - chunks[i].content  = "[PAGINA N] <corpo>"  (armazenado)
    - embed_texts[i]     = "<corpo>"             (o que sera embutido; sem marcador)
    """
    pages = _extract_pages(pdf_bytes)  # {pagina_1based: texto_limpo}
    chunks: list[DocumentChunk] = []
    embed_texts: list[str] = []
    per_page: Counter = Counter()

    hard_cap = chunk_size + 300
    for page in sorted(pages):
        body_text = " ".join(pages[page].split()).strip()
        if not body_text:
            continue
        parts = _pack_sentences(body_text, chunk_size=chunk_size, overlap=overlap, hard_cap=hard_cap)
        per_page[page] = len(parts)
        for idx, body in enumerate(parts, start=1):
            content = f"[PÁGINA {page}] {body}" if add_marker else body
            chunk_id = hashlib.sha1(f"{source}:{page}:{idx}".encode("utf-8")).hexdigest()
            content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    source=source,
                    page=page,
                    content=content,
                    content_hash=content_hash,
                )
            )
            embed_texts.append(body)
    return chunks, embed_texts, per_page


def prepare_table(database_url: str, dim: int, *, reset: bool) -> None:
    """Garante que document_chunks tenha a dimensao certa. DROP se dim divergir ou --reset.

    Toca APENAS em document_chunks; nunca em chat_conversations/chat_messages.
    """
    want = f"vector({dim})"
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.document_chunks')")
        exists = cur.fetchone()[0]
        if not exists:
            print("[tabela] document_chunks nao existe — sera criada em", want)
            return
        cur.execute(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid='public.document_chunks'::regclass AND attname='embedding'"
        )
        row = cur.fetchone()
        cur_type = row[0] if row else None
        if reset or (cur_type and cur_type != want):
            motivo = "--reset" if reset else f"dimensao divergente ({cur_type} != {want})"
            print(f"[tabela] DROP document_chunks ({motivo}) para recriar em {want}")
            cur.execute("DROP TABLE document_chunks")
            conn.commit()
        else:
            print(f"[tabela] document_chunks ja existe em {cur_type} — mantida")


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingestao de PDF em document_chunks (pgvector).")
    ap.add_argument("--pdf", required=True, help="Caminho do PDF (dentro do container).")
    ap.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    ap.add_argument("--dim", type=int, default=int(os.getenv("EMBEDDING_DIMENSION", "1024")))
    ap.add_argument("--chunk-size", type=int, default=int(os.getenv("CHUNK_SIZE", "1000")))
    ap.add_argument("--overlap", type=int, default=int(os.getenv("CHUNK_OVERLAP", "150")))
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--no-marker", action="store_true", help="Nao prefixar [PÁGINA N] no content.")
    ap.add_argument("--reset", action="store_true", help="DROP a tabela antes de ingerir.")
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = ap.parse_args()

    if not args.database_url:
        print("ERRO: DATABASE_URL nao definido (nem --database-url).", file=sys.stderr)
        return 2
    if not os.path.isfile(args.pdf):
        print(f"ERRO: PDF nao encontrado: {args.pdf}", file=sys.stderr)
        return 2

    source = os.path.basename(args.pdf)
    with open(args.pdf, "rb") as fh:
        pdf_bytes = fh.read()

    print(f"== Ingestao Supabase/pgvector ==")
    print(f"PDF     : {source} ({len(pdf_bytes)/1_048_576:.2f} MB)")
    print(f"Modelo  : {args.model}  dim={args.dim}")
    print(f"Chunking: sentence-aware, chunk_size={args.chunk_size} overlap={args.overlap} "
          f"marcador={'nao' if args.no_marker else '[PÁGINA N]'}")

    # 1-2) Extracao layout-aware + chunking page-bounded
    chunks, embed_texts, per_page = build_page_chunks(
        pdf_bytes, source,
        chunk_size=args.chunk_size, overlap=args.overlap, add_marker=not args.no_marker,
    )
    n_pages = len(per_page)
    print(f"\nPaginas com texto: {n_pages}")
    print(f"Total de chunks  : {len(chunks)}")
    if per_page:
        dist = Counter(per_page.values())
        print("Distribuicao chunks/pagina (chunks -> nº de paginas):",
              {k: dist[k] for k in sorted(dist)})
        media = len(chunks) / n_pages
        print(f"Media chunks/pagina: {media:.2f}")
    if not chunks:
        print("ERRO: nenhum chunk gerado.", file=sys.stderr)
        return 1

    # 3) Embedding (carrega o modelo -> download unico ~2.2GB na 1a vez)
    print(f"\nCarregando modelo de embedding e verificando dimensao...")
    embedder = EmbeddingClient(args.model)
    got_dim = embedder.dimension
    if got_dim != args.dim:
        print(f"ERRO: dim do modelo ({got_dim}) != --dim ({args.dim}).", file=sys.stderr)
        return 1
    print(f"OK: modelo carregado, dimensao {got_dim}.")

    # 4) Tabela + upsert
    prepare_table(args.database_url, args.dim, reset=args.reset)
    store = build_vector_store(database_url=args.database_url, embedding_dimension=args.dim)
    store.ensure_ready()
    store.delete_by_source([source])  # idempotencia (re-ingest do mesmo arquivo)

    total = len(chunks)
    for i in range(0, total, args.batch_size):
        batch = chunks[i:i + args.batch_size]
        texts = embed_texts[i:i + args.batch_size]
        embeddings = embedder.embed_texts(texts)
        store.upsert(batch, embeddings)
        print(f"  upsert {min(i + len(batch), total)}/{total} chunks")

    final = store.count()
    print(f"\nOK: {final} chunks em document_chunks (source={source}).")
    print("Amostras (pagina | inicio do content):")
    for c in chunks[:3] + chunks[-2:]:
        preview = c.content[:90].replace("\n", " ")
        print(f"  p.{c.page:>3} | {preview}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Adaptador Cohere -> TEI para reranking.

O LightRAG so fala com rerankers via bindings cohere/jina/aliyun, cujo protocolo
(request com `documents`, resposta `{results:[{index, relevance_score}]}`) NAO bate
com o do TEI (HuggingFace Text Embeddings Inference), que usa `texts` e responde
`[{index, score}]`. Como o TEI e o unico que roda o cross-encoder na GPU desta
maquina (RTX 5090 / Blackwell; ver docker-compose), este micro-servico traduz:

    LightRAG --(Cohere /rerank)--> [adaptador] --(TEI /rerank)--> TEI (GPU)

E proposital ser minimo e sem estado: so reescreve campos de ida e volta.
"""
import os

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Endpoint do TEI (mesma maquina, network_mode host). Sobrescrevivel por env.
TEI_URL = os.environ.get("TEI_URL", "http://127.0.0.1:7998").rstrip("/")
# Timeout generoso: na GPU o rerank e ~25ms, mas cobrimos load/lentidao eventual.
TEI_TIMEOUT = float(os.environ.get("TEI_TIMEOUT", "60"))

app = FastAPI(title="Cohere->TEI rerank adapter")


@app.get("/health")
def health():
    """Saudavel apenas se o TEI responde — assim o healthcheck do container (e o
    depends_on:service_healthy do lightrag) refletem a prontidao real do reranker."""
    try:
        r = requests.get(f"{TEI_URL}/health", timeout=5)
        if r.status_code == 200:
            return {"status": "ok", "tei": TEI_URL}
    except requests.RequestException:
        pass
    return JSONResponse(status_code=503, content={"status": "tei_unavailable", "tei": TEI_URL})


def _as_text(doc):
    # Cohere aceita documents como strings OU objetos {"text": ...}; normalizamos.
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        return doc.get("text") or doc.get("document") or ""
    return str(doc)


@app.post("/rerank")
def rerank(payload: dict):
    """Recebe um request de rerank no formato Cohere e devolve no formato Cohere,
    delegando o trabalho pesado ao TEI."""
    query = payload.get("query", "")
    documents = payload.get("documents", []) or []
    top_n = payload.get("top_n")
    texts = [_as_text(d) for d in documents]

    if not texts:
        return {"results": []}

    try:
        resp = requests.post(
            f"{TEI_URL}/rerank",
            json={"query": query, "texts": texts, "raw_scores": False},
            timeout=TEI_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Falha do TEI: 502 para o LightRAG tratar como rerank indisponivel.
        return JSONResponse(status_code=502, content={"error": type(e).__name__})

    # TEI: [{"index": i, "score": s}, ...] (ja ordenado desc). Cohere espera
    # {"results": [{"index": i, "relevance_score": s}, ...]}.
    tei = resp.json()
    results = [
        {"index": item["index"], "relevance_score": item["score"]}
        for item in tei
        if isinstance(item, dict) and "index" in item and "score" in item
    ]
    if isinstance(top_n, int) and top_n > 0:
        results = results[:top_n]
    return {"results": results}

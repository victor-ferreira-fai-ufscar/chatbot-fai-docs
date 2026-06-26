"""Proxy-shim Ollama: injeta reasoning "high" no gpt-oss.

O LightRAG (binding ollama 1.5.2) NAO repassa o campo de topo `think` da API do
Ollama, e Modelfile/SYSTEM "Reasoning: high" nao setam o nivel (o template harmony
ignora) -> o modelo de sintese raciocina raso (medium). Este micro-servico fica
ENTRE o LightRAG e o Ollama (mesmo padrao do adaptador cohere->TEI):

    LightRAG --(/api/chat)--> [shim :11435] --(/api/chat + think:high)--> Ollama :11434

IDA: injeta think="high" (STRING; boolean e ignorado pelo gpt-oss) em /api/chat e
/api/generate quando o modelo casa com THINK_MODELS. VOLTA: remove o campo `thinking`
das respostas (NDJSON streaming e JSON unico) para o raciocinio NUNCA vazar no texto.
Demais rotas/modelos passam transparentes. Sem estado.
"""
import json
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

UPSTREAM = os.environ.get("OLLAMA_UPSTREAM", "http://127.0.0.1:11434").rstrip("/")
THINK_LEVEL = os.environ.get("THINK_LEVEL", "high")          # low | medium | high
THINK_MODELS = os.environ.get("THINK_MODELS", "gpt-oss")     # substring do nome do modelo
STRIP_THINKING = os.environ.get("STRIP_THINKING", "true").lower() == "true"
INJECT_PATHS = {"/api/chat", "/api/generate"}

# Headers hop-by-hop / recalculados pelo httpx e StreamingResponse — nao repassar.
_DROP_REQ_HEADERS = {"host", "content-length", "connection", "accept-encoding"}
_DROP_RESP_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}

app = FastAPI(title="Ollama think-shim (gpt-oss reasoning=high)")
# Timeout generoso: raciocinio "high" gera por ~15s; o LightRAG usa TIMEOUT=600.
client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))


@app.on_event("shutdown")
async def _close():
    await client.aclose()


@app.get("/health")
async def health():
    """Saudavel apenas se o Ollama upstream responde — assim o healthcheck (e o
    depends_on:service_healthy do lightrag) refletem a prontidao real do caminho do LLM."""
    try:
        r = await client.get(f"{UPSTREAM}/api/version", timeout=5)
        if r.status_code == 200:
            return {"status": "ok", "upstream": UPSTREAM, "think": THINK_LEVEL}
    except httpx.HTTPError:
        pass
    return JSONResponse(status_code=503, content={"status": "upstream_unavailable", "upstream": UPSTREAM})


def _strip_thinking(obj):
    """Remove o raciocinio: chat -> message.thinking; generate -> thinking de topo."""
    if isinstance(obj, dict):
        msg = obj.get("message")
        if isinstance(msg, dict):
            msg.pop("thinking", None)
        obj.pop("thinking", None)
    return obj


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
async def proxy(path: str, request: Request):
    full_path = "/" + path
    raw = await request.body()

    # IDA: injeta think=high em chat/generate de modelos-alvo.
    if raw and full_path in INJECT_PATHS:
        try:
            body = json.loads(raw)
            if isinstance(body, dict) and THINK_MODELS in str(body.get("model", "")):
                body["think"] = THINK_LEVEL
                raw = json.dumps(body).encode()
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # corpo nao-JSON: repassa intacto

    url = f"{UPSTREAM}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQ_HEADERS}

    upstream = await client.send(
        client.build_request(request.method, url, headers=headers, content=raw),
        stream=True,
    )
    ctype = upstream.headers.get("content-type", "")
    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESP_HEADERS}

    # VOLTA streaming NDJSON (Ollama usa application/x-ndjson quando stream=true).
    if "x-ndjson" in ctype:
        async def gen_ndjson():
            try:
                async for line in upstream.aiter_lines():
                    if not line:
                        continue
                    out = line
                    if STRIP_THINKING:
                        try:
                            out = json.dumps(_strip_thinking(json.loads(line)), ensure_ascii=False)
                        except json.JSONDecodeError:
                            out = line
                    yield out + "\n"
            finally:
                await upstream.aclose()
        return StreamingResponse(gen_ndjson(), status_code=upstream.status_code,
                                 headers=resp_headers, media_type=ctype)

    # VOLTA JSON unico (nao-streaming).
    if "application/json" in ctype:
        body_bytes = await upstream.aread()
        await upstream.aclose()
        if STRIP_THINKING:
            try:
                body_bytes = json.dumps(_strip_thinking(json.loads(body_bytes)), ensure_ascii=False).encode()
            except json.JSONDecodeError:
                pass
        return Response(content=body_bytes, status_code=upstream.status_code,
                        headers=resp_headers, media_type=ctype)

    # VOLTA qualquer outra coisa: passa os bytes crus sem modificar.
    async def gen_raw():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
    return StreamingResponse(gen_raw(), status_code=upstream.status_code,
                             headers=resp_headers, media_type=ctype or "application/octet-stream")

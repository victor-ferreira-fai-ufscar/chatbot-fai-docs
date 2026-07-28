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
# Instrumentacao do RACIOCINIO (2026-07-28). O shim descarta `thinking`, entao o custo
# do raciocinio e' INVISIVEL: uma abstencao de 277 chars podia consumir 222s. Aqui
# medimos, no exato ponto em que o texto seria jogado fora, quantos chars de raciocinio
# foram gerados contra quantos de resposta — mais as metricas que o proprio Ollama
# devolve no ultimo chunk (eval_count, eval_duration). Log-only: nao altera resposta.
# Desligue com LOG_THINK_STATS=false.
LOG_THINK_STATS = os.environ.get("LOG_THINK_STATS", "true").lower() == "true"

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


def _pedacos(obj):
    """-> (chars_de_raciocinio, chars_de_resposta) deste chunk. Cobre os dois formatos:
    /api/chat (message.thinking / message.content) e /api/generate (thinking / response)."""
    if not isinstance(obj, dict):
        return 0, 0
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    pensa = (msg.get("thinking") or "") + (obj.get("thinking") or "")
    resp = (msg.get("content") or "") + (obj.get("response") or "")
    return len(pensa), len(resp)


def _loga(modelo, pensa, resp, final):
    """UMA linha por request, no chunk final. `final` traz as metricas do Ollama."""
    ev = final.get("eval_count") or 0
    evd = (final.get("eval_duration") or 0) / 1e9          # ns -> s
    pev = final.get("prompt_eval_count") or 0
    tot = (final.get("total_duration") or 0) / 1e9
    carga = (final.get("load_duration") or 0) / 1e9
    # fracao do texto gerado que foi raciocinio DESCARTADO
    frac = pensa / (pensa + resp) if (pensa + resp) else 0.0
    print(
        f"[think] modelo={modelo} nivel={THINK_LEVEL} "
        f"raciocinio={pensa}ch resposta={resp}ch descartado={frac:.0%} "
        f"tokens_saida={ev} prompt={pev} "
        f"total={tot:.1f}s geracao={evd:.1f}s carga={carga:.1f}s "
        f"tok_por_s={(ev/evd if evd else 0):.1f}",
        flush=True,
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
async def proxy(path: str, request: Request):
    full_path = "/" + path
    raw = await request.body()

    # IDA: injeta think=high em chat/generate de modelos-alvo.
    alvo = None          # nome do modelo quando ele e' alvo do think (habilita o log)
    if raw and full_path in INJECT_PATHS:
        try:
            body = json.loads(raw)
            if isinstance(body, dict) and THINK_MODELS in str(body.get("model", "")):
                body["think"] = THINK_LEVEL
                raw = json.dumps(body).encode()
                alvo = str(body.get("model", ""))
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
            pensa = resp_ch = 0          # acumuladores do request (raciocinio × resposta)
            try:
                async for line in upstream.aiter_lines():
                    if not line:
                        continue
                    out = line
                    obj = None
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        pass
                    if obj is not None:
                        # conta ANTES de descartar — e' o unico ponto em que o
                        # raciocinio ainda existe.
                        if LOG_THINK_STATS and alvo:
                            p, r = _pedacos(obj)
                            pensa += p
                            resp_ch += r
                            if obj.get("done"):
                                _loga(alvo, pensa, resp_ch, obj)
                        if STRIP_THINKING:
                            out = json.dumps(_strip_thinking(obj), ensure_ascii=False)
                    yield out + "\n"
            finally:
                await upstream.aclose()
        return StreamingResponse(gen_ndjson(), status_code=upstream.status_code,
                                 headers=resp_headers, media_type=ctype)

    # VOLTA JSON unico (nao-streaming).
    if "application/json" in ctype:
        body_bytes = await upstream.aread()
        await upstream.aclose()
        try:
            obj = json.loads(body_bytes)
            if LOG_THINK_STATS and alvo:
                p, r = _pedacos(obj)
                _loga(alvo, p, r, obj if isinstance(obj, dict) else {})
            if STRIP_THINKING:
                body_bytes = json.dumps(_strip_thinking(obj), ensure_ascii=False).encode()
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

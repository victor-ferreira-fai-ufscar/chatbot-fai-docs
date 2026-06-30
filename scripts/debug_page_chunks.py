#!/usr/bin/env python3
"""Diagnostico do off-by-one de PAGINA: mostra os chunks que o LightRAG recupera para
uma pergunta e os marcadores [PÁGINA N] embutidos em cada um.

A pagina exibida nas fontes e DETERMINISTICA: vem do marcador [PÁGINA N] no inicio de
cada pagina (inserido por scripts/preprocess_page_marked.py na indexacao), NAO de o
modelo escrever a citacao. Logo, se a fonte cita 26 mas o conteudo e da pagina 27, o
problema esta na ORIGEM (marcador errado na indexacao) ou em chunk ANTIGO ainda no
LightRAG (reindex que nao apagou o anterior). Este script revela qual dos dois e.

Uso (do host; o LightRAG responde em localhost:9621):
    LIGHTRAG_API_KEY=... python3 scripts/debug_page_chunks.py "TEXTO DA PERGUNTA" [--mode mix] [--full]

  --mode   modo de busca do LightRAG (default: mix; igual ao chat)
  --full   imprime o conteudo COMPLETO de cada chunk (default: trecho de 300 chars)
"""
import argparse
import json
import os
import re
import sys
import urllib.request

# Mesmas regex do lightrag_service.py (mantidas em sincronia).
_PAGE_MARK_RE = re.compile(r"\[P[ÁA]GINA\s+(\d{1,4})\]")
_CHUNKS_BLOCK_RE = re.compile(r"Document Chunks.*?```json(.*?)```", re.S | re.I)


def marker_pages(content: str) -> list:
    return [int(m.group(1)) for m in _PAGE_MARK_RE.finditer(content or "")]


def query_context(url: str, key: str, question: str, mode: str) -> str:
    payload = json.dumps({
        "query": question,
        "mode": mode,
        "stream": False,
        "only_need_context": True,
        "conversation_history": [],
        "history_turns": 5,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    req = urllib.request.Request(f"{url}/query", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8", "ignore"))
    text = data.get("response", "") if isinstance(data, dict) else data
    return text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--mode", default="mix")
    p.add_argument("--full", action="store_true")
    p.add_argument("--url", default=os.environ.get("LIGHTRAG_API_URL", "http://localhost:9621").rstrip("/"))
    p.add_argument("--key", default=os.environ.get("LIGHTRAG_API_KEY", ""))
    p.add_argument("--raw", action="store_true", help="despeja o texto de contexto cru e sai")
    a = p.parse_args(argv)

    ctx = query_context(a.url, a.key, a.question, a.mode)
    if a.raw:
        print(ctx)
        return 0

    m = _CHUNKS_BLOCK_RE.search(ctx)
    if not m:
        print("!! Bloco 'Document Chunks' nao encontrado na resposta de contexto.")
        print("   (rode com --raw para ver o texto cru retornado pelo LightRAG)\n")
        print(ctx[:2000])
        return 1

    print(f"=== Pergunta: {a.question!r}  (mode={a.mode}) ===\n")
    by_ref_pages = {}
    n = 0
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        n += 1
        ref = str(obj.get("reference_id", "")).strip()
        fp = obj.get("file_path") or obj.get("file") or "?"
        content = obj.get("content", "") or ""
        pages = marker_pages(content)
        by_ref_pages.setdefault(ref, []).extend(pages)
        snippet = content if a.full else (content[:300] + ("..." if len(content) > 300 else ""))
        print(f"--- chunk #{n}  ref={ref}  file={fp}")
        print(f"    [PÁGINA] no chunk: {pages or '(NENHUM marcador!)'}")
        print(f"    conteudo: {snippet}\n")

    print("=== RESUMO paginas por reference_id ===")
    for ref, pages in sorted(by_ref_pages.items()):
        uniq = sorted(set(pages))
        print(f"  ref {ref}: {uniq}")
    if n == 0:
        print("  (nenhum chunk parseado)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

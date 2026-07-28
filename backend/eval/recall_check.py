#!/usr/bin/env python3
"""Checagem de RECALL: as falsas negativas conhecidas (com gabarito humano de página)
viraram resposta fundamentada citando a página certa?

Casos em `recall_set.json` — as 10 falsas negativas das baterias de 2026-07-14
(9 do Manual do Sistema + COORD-15), todas com a resposta COMPROVADAMENTE no manual
(docs/teste_perguntas_manual_*.md, campo "Páginas de referência"). Fraseado
coloquial/sintomático preservado de propósito: é o gap lexical sob teste.

PASS por item = não-negativa E não-swallow E manual citado = esperado E
(páginas citadas ∩ gabarito ≠ ∅).

  # run completo com rótulo (grava .recall_<tag>.json):
  python3 backend/eval/recall_check.py --tag baseA
  # subconjunto / meta customizada:
  python3 backend/eval/recall_check.py --tag posB --ids SIST-02,COORD-15 --min-pass 1

Exit code != 0 se PASS < --min-pass (default 6/10, critério do plano).
PRÉ-REQUISITO: os DOIS manuais no índice LightRAG (kv_store_doc_status.json).
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bateria_consolidado import ask  # noqa: E402  (reusa SSE + classify)

RECALL_SET = HERE / "recall_set.json"

_PAGE_RE = re.compile(r"p[áa]gs?\.?\s*([\d][\d\s,\-]*)", re.I)
_INLINE_CITE_RE = re.compile(r"\[([^\[\]]+?\.pdf)\s*,([^\]]*)\]", re.I)
_SRC_FILE_RE = re.compile(r"^[-\s]*([^()]+?\.pdf)", re.I)


def _pages_in(text: str) -> set:
    pages = set()
    for m in _PAGE_RE.finditer(text or ""):
        for tok in re.split(r"[,\s]+", m.group(1).strip()):
            for part in tok.split("-"):
                if part.isdigit():
                    pages.add(int(part))
    return pages


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def cited_pages_for_manual(r: dict, manual: str) -> set:
    """Páginas citadas ATRIBUÍDAS ao manual esperado (cards + citações inline)."""
    want = _norm(manual)
    pages = set()
    for s in r.get("sources", []):
        m = _SRC_FILE_RE.match(s)
        if m and _norm(m.group(1)) == want:
            pages |= _pages_in(s)
    for m in _INLINE_CITE_RE.finditer(r.get("answer", "")):
        if _norm(m.group(1)) == want:
            pages |= _pages_in(m.group(2))
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="rótulo do run (ex.: baseA, posB)")
    ap.add_argument("--ids", help="subconjunto: SIST-02,COORD-15,...")
    ap.add_argument("--min-pass", type=int, default=6, help="meta (exit!=0 abaixo disso)")
    args = ap.parse_args()

    cases = json.loads(RECALL_SET.read_text(encoding="utf-8"))
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in wanted]

    results, passed = [], 0
    for i, c in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {c['id']}: {c['question'][:70]}...", flush=True)
        r = ask(c["question"])
        hits = cited_pages_for_manual(r, c["manual"])
        page_ok = bool(hits & set(c["pages"]))
        ok = (not r["error"] and not r["abstained"] and not r["swallowed"] and page_ok)
        passed += ok
        results.append({**c, **r, "cited_pages_expected_manual": sorted(hits),
                        "page_match": page_ok, "pass": ok})
        why = ("ERRO" if r["error"] else "negativa" if r["abstained"] else
               "swallow" if r["swallowed"] else
               f"páginas {sorted(hits)} ∌ gabarito {c['pages']}" if not page_ok else "")
        print(f"    -> {'PASS' if ok else 'FAIL'} ({why or 'ok'}) · {r['elapsed']}s", flush=True)

    out = HERE / f".recall_{args.tag}.json"
    out.write_text(json.dumps({"tag": args.tag, "results": results,
                               "passed": passed, "total": len(cases)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== RECALL [{args.tag}]: {passed}/{len(cases)} PASS "
          f"(meta {args.min_pass}) -> {out.name} ===")
    return 0 if passed >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Harness de avaliação de PRECISÃO do chatbot da FAI sobre o Manual do Coordenador.

Roda as perguntas reais (docs/perguntas, congeladas em eval_questions.json) contra
o chatbot AO VIVO e aplica VERIFICAÇÕES de fundamentação/citação + um placar de
correção. Sem dependências externas (só stdlib): roda no host.

  # 1) coleta as respostas ao vivo (lento, ~20 min; precisa backend no ar)
  python3 backend/eval/eval_manual_qa.py --collect
  # 2) verificações DURAS (rápido; exit code != 0 se houver violação) -> é o "teste"
  python3 backend/eval/eval_manual_qa.py --check
  # 3) placar de correção vs gabarito (juiz = gpt-oss local via Ollama)
  python3 backend/eval/eval_manual_qa.py --judge
  # tudo de uma vez:
  python3 backend/eval/eval_manual_qa.py --all

Verificações DURAS (anti-alucinação; falham o teste):
  A. fonte_fabricada     -> citou um arquivo que NÃO é um manual conhecido.
  B. pagina_invalida     -> citou página fora de [1, N] do MANUAL citado (per-manual;
                            páginas sem manual atribuível: teto global).
  C. ref_legal_fabricada -> citou Lei/Decreto/Resolução/Portaria cujo número NÃO
                            existe no texto indexado do manual (alucinação factual).
Verificação MOLE (reportada, não falha): resposta factual sem nenhuma fonte.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # backend/eval -> backend -> raiz do repo
QUESTIONS = HERE / "eval_questions.json"
RUN_OUT = HERE / ".last_run.json"
MANUAL_DOCS = ROOT / "lightrag" / "data" / "rag_storage" / "kv_store_full_docs.json"

API = "http://localhost:8000/api/v1/chat/stream"
OLLAMA = "http://localhost:11434/api/chat"
JUDGE_MODEL = "gpt-oss:latest"

# Manuais conhecidos (normalizados) -> nº de páginas. A validação de página é POR
# manual citado (a global de 73 deixava passar "pág. 60" no manual do Sistema, que
# tem 42). A grafia antiga ("Manual do Coordenador.pdf") fica p/ runs históricos.
MANUAL_PAGES = {
    "manualdoscoordenadorespdf": 73,
    "manualdosistemaareacoordenadorespdf": 42,
    "manualdocoordenadorpdf": 73,  # grafia antiga (histórico)
}
MAX_PAGES_ANY = max(MANUAL_PAGES.values())

# 2026-07-21: + fornece|apresenta|... (sincronizado com bateria/probe).
ABSTENTION_RE = re.compile(
    r"n[ãa]o\s+(consta|detalha|est[áa]\s+detalhad|especifica|menciona|trata|aborda|"
    r"fornece|apresenta|oferece|traz|inclui|cobre|indica|descreve|explica|define|informa|"
    r"foi\s+poss[íi]vel|encontr|disp[oõ]e|h[áa]\s+informa)", re.I)
# Negativa por token-sentinela substituida pela mensagem oficial de direcionamento —
# nao casa o ABSTENTION_RE; sem isto, a negativa oficial era contada como "factual
# sem fonte" no check mole (2026-07-21; sincronizado com bateria/probe).
NO_CONTEXT_SIG_RE = re.compile(
    r"(recomendo entrar em contato com o Gestor|Supervisor de Projetos (Espec|Gerais))", re.I)


def norm_file(s: str) -> str:
    """Normaliza nome de arquivo p/ comparação (minúsculo, sem acento/espaço/_)."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ----------------------------------------------------------------- coleta (ao vivo)
def ask(question: str):
    body = json.dumps({"question": question, "user_id": "eval-harness", "mode": "hybrid"}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    content, sources, err = "", [], None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in r:
                ln = raw.decode("utf-8", "ignore").strip()
                if not ln.startswith("data:"):
                    continue
                try:
                    ev = json.loads(ln[5:].strip())
                except Exception:
                    continue
                if "content" in ev:
                    content += ev["content"]
                if ev.get("error"):
                    err = ev["error"]
                if ev.get("done"):
                    sources = ev.get("sources", [])
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return {"answer": content.strip(), "sources": sources, "elapsed": round(time.time() - t0, 1), "error": err}


def collect():
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    out = []
    for i, q in enumerate(qs):
        r = ask(q["question"])
        out.append({**q, **r})
        RUN_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{i+1}/{len(qs)}] {q['id']:14} {r['elapsed']}s err={r['error']} "
              f"chars={len(r['answer'])} src={r['sources'][:1]}", flush=True)
    print(f"\nColeta salva em {RUN_OUT} ({len(out)} respostas)")


# ----------------------------------------------------------------- verificações duras
def load_manual_text() -> str:
    try:
        d = json.loads(MANUAL_DOCS.read_text(encoding="utf-8"))
        return " ".join(v.get("content", "") for v in d.values())
    except Exception as e:
        print(f"AVISO: não consegui ler o manual indexado ({e}); checagem de refs legais desativada.")
        return ""


_CITE_FILE_RE = re.compile(r"\[([^\[\]]+?\.pdf)[,\]]", re.I)          # "[arquivo.pdf, ...]" inline
_SRC_FILE_RE = re.compile(r"^[-\s]*([^()]+?\.pdf)", re.I)              # "- arquivo.pdf (pág...)" na lista
_PAGE_RE = re.compile(r"p[áa]gs?\.?\s*([\d][\d\s,\-]*)", re.I)
# Captura o NÚMERO-BASE da norma (antes do /ano), p/ casar com o manual mesmo quando o
# modelo acrescenta o ano (ex.: manual cita "Lei 5.452"; modelo escreve "5.452/1943").
_LEGAL_RE = re.compile(
    r"(?:Lei(?:\s+Complementar)?|Decreto(?:[-\s]?Lei)?|Resolu[çc][ãa]o|Portaria|"
    r"Instru[çc][ãa]o\s+Normativa|Medida\s+Provis[óo]ria)[^.;:\n]{0,45}?"
    r"(\d{1,4}(?:\.\d{1,3})*)\s*(?:/\s*\d{2,4})?", re.I)


def cited_files(res) -> list:
    files = set()
    for s in res.get("sources", []):
        m = _SRC_FILE_RE.match(s)
        if m:
            files.add(m.group(1).strip())
    for m in _CITE_FILE_RE.finditer(res.get("answer", "")):
        files.add(m.group(1).strip())
    return sorted(files)


def _pages_in(text: str) -> set:
    pages = set()
    for m in _PAGE_RE.finditer(text or ""):
        for tok in re.split(r"[,\s]+", m.group(1).strip()):
            for part in tok.split("-"):
                if part.isdigit():
                    pages.add(int(part))
    return pages


# Citação inline "[arquivo.pdf, pág(s). N, M]" — associa páginas ao manual citado.
_INLINE_CITE_RE = re.compile(r"\[([^\[\]]+?\.pdf)\s*,([^\]]*)\]", re.I)


def cited_file_pages(res) -> tuple:
    """-> (pares [(arquivo, página)], páginas soltas sem manual atribuível).

    Pares vêm dos cards ("- arquivo.pdf (pág. N ...)") e das citações inline.
    Páginas do corpo que não aparecem em nenhum par ficam "soltas" (validadas
    contra o teto global — conservador, não fabrica violação por manual errado).
    """
    pairs, loose = set(), set()
    for s in res.get("sources", []):
        m = _SRC_FILE_RE.match(s)
        ps = _pages_in(s)
        if m:
            pairs |= {(m.group(1).strip(), p) for p in ps}
        else:
            loose |= ps
    ans = res.get("answer", "")
    for m in _INLINE_CITE_RE.finditer(ans):
        pairs |= {(m.group(1).strip(), p) for p in _pages_in(m.group(2))}
    attributed = {p for _, p in pairs}
    loose |= (_pages_in(ans) - attributed)
    return sorted(pairs), sorted(loose)


def cited_legal_refs(res) -> list:
    return sorted({m.group(1) for m in _LEGAL_RE.finditer(res.get("answer", ""))})


def _load_results(path: Path) -> list:
    """Carrega .last_run.json OU um JSON da bateria (sintetiza id Professor:N)."""
    results = json.loads(path.read_text(encoding="utf-8"))
    for r in results:
        if "id" not in r:
            prof = (r.get("professor") or "?").split()[-1]
            r["id"] = f"{prof}:{r.get('num', '?')}"
    return results


def check(input_path: Path = None):
    src = input_path or RUN_OUT
    if not src.exists():
        print(f"Sem coleta em {src}. Rode primeiro: --collect (ou passe --input)"); return 2
    results = _load_results(src)
    manual = load_manual_text()
    # números-base de norma que EXISTEM no manual (allowlist); ref citada fora disso = fabricada.
    manual_law_bases = {m.group(1).replace(" ", "") for m in _LEGAL_RE.finditer(manual)}

    hard = 0
    soft = 0
    rows = []
    for r in results:
        viol = []
        # A) fonte fabricada
        for f in cited_files(r):
            if norm_file(f) not in MANUAL_PAGES:
                viol.append(f"fonte_fabricada:{f}")
        # B) página inválida — POR manual citado; páginas soltas contra o teto global
        pairs, loose = cited_file_pages(r)
        for f, p in pairs:
            limit = MANUAL_PAGES.get(norm_file(f))
            if limit and (p < 1 or p > limit):
                viol.append(f"pagina_invalida:{f}:{p}")
        for p in loose:
            if p < 1 or p > MAX_PAGES_ANY:
                viol.append(f"pagina_invalida:{p}")
        # C) ref legal fabricada (número não existe no manual)
        if manual_law_bases:
            for ref in cited_legal_refs(r):
                if ref not in manual_law_bases:
                    viol.append(f"ref_legal_fabricada:{ref}")
        is_abst = bool(ABSTENTION_RE.search(r.get("answer", ""))
                       or NO_CONTEXT_SIG_RE.search(r.get("answer", "")))
        # D) (mole) resposta factual sem fonte
        factual_no_src = (len(r.get("answer", "")) > 200 and not r.get("sources") and not is_abst)
        if factual_no_src:
            soft += 1
        if viol:
            hard += 1
        rows.append((r["id"], viol, factual_no_src, is_abst))

    print("=== VERIFICAÇÕES DURAS (anti-alucinação / citação) ===")
    for rid, viol, fns, abst in rows:
        if viol:
            print(f"  ✗ {rid:14} {', '.join(viol)}")
    print(f"\nResumo: {len(results)} perguntas | {hard} com violação DURA | "
          f"{soft} factuais sem fonte (mole) | "
          f"{sum(1 for _,_,_,a in rows if a)} abstenções")
    if hard == 0:
        print("✅ Nenhuma violação dura: sem fonte fabricada, sem página inválida, sem ref. legal inventada.")
    else:
        print(f"❌ {hard} pergunta(s) com violação dura — ver acima.")
    return 1 if hard else 0


# ----------------------------------------------------------------- placar (juiz LLM)
def _ollama_judge(question, reference, answer) -> dict:
    prompt = (
        "Você avalia a resposta de um chatbot que responde SÓ com base no Manual do "
        "Coordenador da FAI-UFSCar. Compare a RESPOSTA ao GABARITO (resposta humana).\n"
        "Classifique em 'verdict': 'correto' (captura o fato-chave do gabarito), "
        "'parcial' (incompleto), 'incorreto' (contradiz/erra), ou 'abstencao_ok' (a resposta "
        "diz que não consta no manual E o gabarito é regra de financiador/sistema fora do manual). "
        "Responda SÓ JSON: {\"verdict\":\"...\"}.\n\n"
        f"PERGUNTA: {question}\nGABARITO: {reference}\nRESPOSTA: {answer[:1500]}")
    body = json.dumps({"model": JUDGE_MODEL, "stream": False, "format": "json",
                       "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(OLLAMA, data=body,
                headers={"Content-Type": "application/json"}), timeout=180) as r:
            data = json.loads(r.read())
        return json.loads(data["message"]["content"])
    except Exception as e:
        return {"verdict": f"erro:{type(e).__name__}"}


def judge():
    if not RUN_OUT.exists():
        print("Sem coleta. Rode primeiro: --collect"); return 2
    results = json.loads(RUN_OUT.read_text(encoding="utf-8"))
    counts = {}
    for i, r in enumerate(results):
        v = _ollama_judge(r["question"], r.get("reference", ""), r.get("answer", "")).get("verdict", "erro")
        counts[v] = counts.get(v, 0) + 1
        print(f"[{i+1}/{len(results)}] {r['id']:14} -> {v}", flush=True)
    print("\n=== PLACAR DE CORREÇÃO (vs gabarito) ===")
    for k in sorted(counts):
        print(f"  {k:16} {counts[k]}")
    aceit = counts.get("correto", 0) + counts.get("parcial", 0) + counts.get("abstencao_ok", 0)
    print(f"  ---\n  aceitável (correto+parcial+abstencao_ok): {aceit}/{len(results)}")
    return 0


def main(argv):
    # Consome "--input <path>" (ou "--input=<path>") ANTES de montar as flags — sem
    # isso o path vazava para `flags` e "--input x.json" sozinho virava no-op.
    args = list(argv)
    input_path = None
    for i, a in enumerate(args):
        if a == "--input":
            try:
                input_path = Path(args[i + 1])
            except IndexError:
                print("--input exige um caminho de JSON"); return 2
            del args[i:i + 2]
            break
        if a.startswith("--input="):
            input_path = Path(a.split("=", 1)[1])
            del args[i]
            break
    flags = set(args)
    if "--collect" in flags or "--all" in flags:
        collect()
    rc = 0
    if "--check" in flags or "--all" in flags or not flags:
        rc = check(input_path)
    if "--judge" in flags or "--all" in flags:
        judge()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

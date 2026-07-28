#!/usr/bin/env python3
"""Bateria das perguntas CONSOLIDADAS dos professores (Manual do Coordenador).

Percorre as perguntas de `docs/Perguntas Manual Coordenador - Consolidado.md`
(seções `## Professor`, itens numerados) e faz cada uma pela rota REAL do chatbot
(/api/v1/chat/stream), na configuração DEFAULT do servidor (agêntico conforme
AGENT_ENABLED, LightRAG mix). Grava o resultado INCREMENTALMENTE em Markdown
(sobrevive a queda no meio) + um JSON de apoio para análise posterior.

Diferente do consistency_probe (estabilidade) e do eval_manual_qa (correção com
ground-truth), aqui o objetivo é só COLETAR as respostas reais para leitura humana.

  # bateria completa (68 perguntas, ~40-70 min):
  python3 backend/eval/bateria_consolidado.py
  # fumaça com as N primeiras:
  python3 backend/eval/bateria_consolidado.py --limit 2
  # subconjunto por professor/número (Nome:N, Nome:* = todas do professor):
  python3 backend/eval/bateria_consolidado.py --ids "Alberto:2,Fujihara:*"
  # run rotulado (NÃO sobrescreve a saída default — p/ A/B):
  python3 backend/eval/bateria_consolidado.py --tag posB
  # pergunta avulsa (validação do plumbing, fora da lista p/ não poluir o cache 24h):
  python3 backend/eval/bateria_consolidado.py --question "O que é a FAI?"
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # raiz do repo (backend/eval -> repo)
# 2026-07-21: banco de perguntas movido pelo usuário p/ docs/Perguntas e respostas
# Recentes/ (mesmo arquivo de 14/07 — numeração compatível com os baselines).
# Sobrescrevível com --questions.
QUESTIONS_DIR = ROOT / "docs" / "Perguntas e respostas Recentes"
QUESTIONS_MD = QUESTIONS_DIR / "Perguntas Manual Coordenador - Consolidado.md"
OUT_MD = QUESTIONS_DIR / "Perguntas Manual Coordenador - Consolidado - RESPOSTAS.md"
OUT_JSON = HERE / ".bateria_consolidado.json"
API = "http://localhost:8000/api/v1/chat/stream"
USER_ID = "bateria-consolidado"

# Reusa o predicado social do backend p/ detectar SWALLOW: pergunta REAL respondida
# como se fosse social. Usa is_social_turn (permissivo — o MESMO que o guard de
# grounding usa), não is_smalltalk (alta precisão): um agradecimento de forma livre
# ("muito obrigado, consegui enviar o relatório!") respondido com cortesia é
# comportamento CORRETO e não pode contar como swallow. Import como módulo top-level
# p/ não disparar o __init__ pesado do pacote (mesmo truque do agent/test_agent.py).
sys.path.insert(0, str(ROOT / "backend" / "src" / "chatbot_fai_docs"))
from smalltalk_gate import is_social_turn  # noqa: E402

# Mesma heurística de abstenção do consistency_probe.py (mantida em sincronia).
# 2026-07-21: + fornece|apresenta|oferece|traz|inclui|cobre|indica|descreve|explica|
# define|informa — "não fornece informações" (Nilva Q11, SIST-02) escapava e era
# contada como resposta. O guard "> Fonte:" abaixo evita falso-positivo em resposta
# fundamentada que observa "o manual não detalha [sub-ponto]" (regra 2.2).
ABSTENTION_RE = re.compile(
    r"n[ãa]o\s+(consta|detalha|est[áa]\s+detalhad|especifica|menciona|trata|aborda|"
    r"fornece|apresenta|oferece|traz|inclui|cobre|indica|descreve|explica|define|informa|"
    r"foi\s+poss[íi]vel|encontr|disp[oõ]e|h[áa]\s+informa)", re.I)
NO_CONTEXT_SIG_RE = re.compile(
    r"(recomendo entrar em contato com o Gestor|Supervisor de Projetos (Espec|Gerais))", re.I)


def classify(ans: str, sources: list, question: str, err) -> tuple:
    """Classifica uma resposta: (abstained, swallowed).

    abstained = negativa/direcionamento (sentinela ou frase de negativa SEM fonte).
    swallowed = pergunta REAL (não-social) respondida SEM nenhuma âncora (sem card,
    sem "> Fonte:") e sem ser negativa — ex.: saudação a uma pergunta operacional
    (bug Alberto Q2, invisível na métrica antiga). NÃO depende de skills==[]: o
    swallow observado ocorreu MESMO com a skill chamada (sources vazios).
    """
    abstained = bool(NO_CONTEXT_SIG_RE.search(ans)) \
        or (bool(ABSTENTION_RE.search(ans)) and "> Fonte:" not in ans)
    swallowed = (not err and not abstained and not sources
                 and "> Fonte:" not in ans
                 and not is_social_turn(question))
    return abstained, swallowed


def parse_questions(md_path: Path):
    """Extrai [(professor, numero, pergunta)] das seções `## Nome` + itens `N. ...`."""
    out, prof = [], None
    for ln in md_path.read_text(encoding="utf-8").splitlines():
        m_prof = re.match(r"^##\s+(.+)$", ln)
        if m_prof:
            prof = m_prof.group(1).strip()
            continue
        m_q = re.match(r"^(\d+)\.\s+(.+)$", ln.strip())
        if m_q and prof:
            out.append((prof, int(m_q.group(1)), m_q.group(2).strip()))
    return out


def ask(question: str):
    """Uma pergunta pela rota real; devolve resposta, fontes, skills e latência."""
    body = json.dumps({"question": question, "user_id": USER_ID}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    content, sources, skills, err = "", [], [], None
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
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
                if "tool_status" in ev:
                    skills.append(str(ev["tool_status"]))
                if ev.get("error"):
                    err = ev["error"]
                if ev.get("done"):
                    sources = ev.get("sources", [])
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    ans = content.strip()
    abstained, swallowed = classify(ans, sources, question, err)
    return {
        "answer": ans,
        "sources": sources,
        "skills": skills,
        "abstained": abstained,
        "swallowed": swallowed,
        "elapsed": round(time.time() - t0, 1),
        "error": err,
    }


def md_header(total: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        "# Respostas — Perguntas Consolidadas dos Professores (Manual do Coordenador)\n\n"
        f"> **Execução:** {now} · **Perguntas:** {total}\n"
        "> **Origem:** `docs/Perguntas Manual Coordenador - Consolidado.md`\n"
        "> **Config do chat:** defaults do servidor via `/api/v1/chat/stream` "
        "(modo agêntico conforme `AGENT_ENABLED`, LightRAG `mix`, mitigações multi-manual ativas)\n\n"
        "---\n"
    )


def md_entry(prof: str, num: int, question: str, r: dict, idx: int, total: int) -> str:
    lines = [f"\n## {idx}/{total} — {prof} · Q{num}\n",
             f"**Pergunta:** {question}\n"]
    status = []
    if r["error"]:
        status.append(f"ERRO: {r['error']}")
    if r["abstained"]:
        status.append("abstenção/negativa")
    if r.get("swallowed"):
        status.append("SWALLOW (pergunta real sem âncora)")
    tag = f" · {' · '.join(status)}" if status else ""
    lines.append(f"**Resposta do chatbot** *(latência {r['elapsed']}s{tag})*:\n")
    lines.append(r["answer"] if r["answer"] else "_(sem conteúdo)_")
    if r["sources"]:
        lines.append("\n**Fontes (cards da sidebar):**\n")
        lines.extend(f"- {s}" for s in r["sources"])
    lines.append("\n---\n")
    return "\n".join(lines)


def _parse_ids(spec: str):
    """"Alberto:2,Fujihara:*" -> [(nome, num|None)]; nome casa por substring."""
    out = []
    for tok in spec.split(","):
        name, _, n = tok.strip().partition(":")
        if not name:
            continue
        n = n.strip()
        out.append((name.lower(), int(n) if n.isdigit() else None))
    return out


def _match_ids(prof: str, num: int, wanted) -> bool:
    return any(name in prof.lower() and (n is None or n == num) for name, n in wanted)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="só as N primeiras (fumaça)")
    ap.add_argument("--questions", help="caminho do MD de perguntas (default: %(default)s)",
                    default=str(QUESTIONS_MD))
    ap.add_argument("--ids", help='subconjunto "Nome:N,Nome:*" (nome por substring)')
    ap.add_argument("--tag", help="rótulo do run: grava em arquivos sufixados, "
                                  "preservando a saída default (p/ A/B)")
    ap.add_argument("--question", help="pergunta avulsa (não grava nos arquivos de saída)")
    args = ap.parse_args()

    if args.question:
        r = ask(args.question)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    out_md, out_json = OUT_MD, OUT_JSON
    if args.tag:
        out_md = OUT_MD.with_name(f"{OUT_MD.stem}.{args.tag}.md")
        out_json = HERE / f".bateria_consolidado.{args.tag}.json"

    qs = parse_questions(Path(args.questions))
    if args.ids:
        wanted = _parse_ids(args.ids)
        qs = [(p, n, q) for p, n, q in qs if _match_ids(p, n, wanted)]
    if args.limit:
        qs = qs[: args.limit]
    total = len(qs)
    print(f"[bateria] {total} perguntas -> {out_md.name}", flush=True)

    out_md.write_text(md_header(total), encoding="utf-8")
    results = []
    for i, (prof, num, q) in enumerate(qs, 1):
        print(f"[{i}/{total}] {prof} Q{num}: {q[:70]}...", flush=True)
        r = ask(q)
        results.append({"professor": prof, "num": num, "question": q, **r})
        # Incremental: anexa a entrada e regrava o JSON a cada pergunta.
        with out_md.open("a", encoding="utf-8") as f:
            f.write(md_entry(prof, num, q, r, i, total))
        out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        flag = "ERRO" if r["error"] else (
            "NEG" if r["abstained"] else ("SWAL" if r["swallowed"] else "ok"))
        print(f"    -> {flag} · {r['elapsed']}s · {len(r['sources'])} fontes", flush=True)

    errs = sum(1 for r in results if r["error"])
    negs = sum(1 for r in results if r["abstained"] and not r["error"])
    swal = sum(1 for r in results if r.get("swallowed"))
    lat = [r["elapsed"] for r in results if not r["error"]]
    print(f"[bateria] fim: {total} perguntas · {errs} erros · {negs} negativas · "
          f"{swal} swallows · latência média {sum(lat)/len(lat):.1f}s" if lat
          else "[bateria] fim (sem sucessos)",
          flush=True)


if __name__ == "__main__":
    main()

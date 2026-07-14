#!/usr/bin/env python3
"""Probe de CONSISTÊNCIA da síntese (responde vs. abstém para a MESMA pergunta).

Análogo ao probe de recuperação (8/8 idêntico), mas para a ponta geradora: faz a
MESMA pergunta R vezes pela rota REAL do chatbot (/api/v1/chat/stream — passa pelo
agente, se AGENT_ENABLED) e mede se o resultado FLIPA entre resposta-fundamentada e
abstenção. É esse flip que o usuário percebe como "às vezes responde, às vezes não".

NÃO confunde com qualidade: aqui só importa a ESTABILIDADE da decisão. Use o
eval_manual_qa.py (--check/--judge) para correção/fundamentação.

  # baseline no nível atual do shim (high):
  python3 backend/eval/consistency_probe.py --tag high --repeats 4
  # depois de trocar THINK_LEVEL -> medium e reiniciar o shim:
  python3 backend/eval/consistency_probe.py --tag medium --repeats 4
  # comparar dois runs salvos:
  python3 backend/eval/consistency_probe.py --compare high medium

Métrica-chave: questões INSTÁVEIS = aquelas que em R repetições deram TANTO resposta
fundamentada QUANTO abstenção (o flip). 0 instáveis = decisão reproduzível.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "eval_questions.json"
API = "http://localhost:8000/api/v1/chat/stream"

# Mesma heurística de abstenção do eval_manual_qa.py (mantida em sincronia).
ABSTENTION_RE = re.compile(
    r"n[ãa]o\s+(consta|detalha|est[áa]\s+detalhad|especifica|menciona|trata|aborda|"
    r"foi\s+poss[íi]vel|encontr|disp[oõ]e|h[áa]\s+informa)", re.I)
# Negativa por TOKEN-SENTINELA: o sistema substitui o token pela mensagem fixa de
# direcionamento (NO_CONTEXT_MSG), que NÃO casa o regex acima. Detecta essa forma
# nova pela assinatura estável do direcionamento ao Gestor/Supervisores.
NO_CONTEXT_SIG_RE = re.compile(
    r"(recomendo entrar em contato com o Gestor|Supervisor de Projetos (Espec|Gerais))", re.I)

# Subconjunto-padrão: mistura controles "fáceis" (devem SEMPRE responder) com casos de
# fronteira (financiador/autônomos/prazos) onde o flip costuma aparecer. Sobrescrevível
# com --ids id1,id2,...; --all usa as 53.
DEFAULT_IDS = [
    "Projetos-01",   # limite financeiro de contratação direta (controle, deve responder)
    "Projetos-08",   # contratação de autônomos PF (fronteira)
    "Projetos-03",   # prazos de obras de engenharia (fronteira)
    "Projetos-06",   # prazo de processo logístico internacional (fronteira)
    "TI-01",         # trocar e-mail (controle)
]


def ask(question: str, mode: str):
    body = json.dumps({"question": question, "user_id": "consistency-probe", "mode": mode}).encode()
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
    ans = content.strip()
    return {
        "answer": ans,
        "sources": sources,
        # Abstencao real = mensagem de direcionamento (sentinela) OU frase de negativa SEM
        # nenhuma linha de fonte. Uma resposta fundamentada que observa "o manual nao
        # detalha [sub-ponto]" (regra 2.2 do prompt) NAO e abstencao — com o "> Fonte:"
        # presente, o nucleo foi respondido (falso-positivo corrigido em 2026-07-14).
        "abstained": bool(NO_CONTEXT_SIG_RE.search(ans))
                     or (bool(ABSTENTION_RE.search(ans)) and "> Fonte:" not in ans),
        "has_sources": bool(sources),
        "chars": len(ans),
        "elapsed": round(time.time() - t0, 1),
        "error": err,
    }


def run(tag: str, ids, repeats: int, mode: str):
    qs = {q["id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    sel = [qs[i] for i in ids if i in qs] if ids else list(qs.values())
    out = []
    for q in sel:
        runs = []
        for r in range(repeats):
            res = ask(q["question"], mode)
            runs.append(res)
            flag = "ERR" if res["error"] else ("ABST" if res["abstained"] else "ANS")
            print(f"  {q['id']:14} [{r+1}/{repeats}] {flag:4} "
                  f"{res['elapsed']}s chars={res['chars']} src={len(res['sources'])}", flush=True)
        n_ans = sum(1 for x in runs if not x["abstained"] and not x["error"])
        n_abst = sum(1 for x in runs if x["abstained"])
        n_err = sum(1 for x in runs if x["error"])
        unstable = n_ans > 0 and n_abst > 0  # flipou entre responder e abster
        out.append({"id": q["id"], "question": q["question"], "runs": runs,
                    "n_ans": n_ans, "n_abst": n_abst, "n_err": n_err, "unstable": unstable})
        print(f"  -> {q['id']:14} ANS={n_ans} ABST={n_abst} ERR={n_err} "
              f"{'*** INSTÁVEL ***' if unstable else 'estável'}\n", flush=True)
    path = HERE / f".probe_{tag}.json"
    path.write_text(json.dumps({"tag": tag, "mode": mode, "repeats": repeats, "results": out},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    _summary(tag, out)
    print(f"\nSalvo em {path}")


def _summary(tag: str, out: list):
    n = len(out)
    unstable = [r["id"] for r in out if r["unstable"]]
    lat = [x["elapsed"] for r in out for x in r["runs"] if not x["error"]]
    chars = [x["chars"] for r in out for x in r["runs"] if not x["error"]]
    print(f"=== RESUMO [{tag}] ===")
    print(f"  questões: {n} | INSTÁVEIS (flip resp/abst): {len(unstable)} {unstable}")
    if lat:
        print(f"  latência média: {sum(lat)/len(lat):.1f}s (min {min(lat)} / max {max(lat)})")
        print(f"  tamanho médio:  {sum(chars)/len(chars):.0f} chars")


def compare(tag_a: str, tag_b: str):
    a = json.loads((HERE / f".probe_{tag_a}.json").read_text(encoding="utf-8"))
    b = json.loads((HERE / f".probe_{tag_b}.json").read_text(encoding="utf-8"))
    ai = {r["id"]: r for r in a["results"]}
    bi = {r["id"]: r for r in b["results"]}
    print(f"=== COMPARAÇÃO  {tag_a} (mode {a['mode']})  vs  {tag_b} (mode {b['mode']}) ===")
    print(f"{'id':14} {tag_a+' ANS/ABST':>16} {tag_b+' ANS/ABST':>16}  estabilidade")
    for i in sorted(set(ai) | set(bi)):
        ra, rb = ai.get(i), bi.get(i)
        sa = f"{ra['n_ans']}/{ra['n_abst']}" if ra else "-"
        sb = f"{rb['n_ans']}/{rb['n_abst']}" if rb else "-"
        ua = "INSTÁVEL" if ra and ra["unstable"] else "ok"
        ub = "INSTÁVEL" if rb and rb["unstable"] else "ok"
        print(f"{i:14} {sa:>16} {sb:>16}  {ua} -> {ub}")
    for tag, run in ((tag_a, a), (tag_b, b)):
        lat = [x["elapsed"] for r in run["results"] for x in r["runs"] if not x["error"]]
        un = sum(1 for r in run["results"] if r["unstable"])
        if lat:
            print(f"  [{tag}] instáveis={un}  lat.média={sum(lat)/len(lat):.1f}s")


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--tag", help="rótulo do run (ex.: high, medium)")
    p.add_argument("--repeats", type=int, default=4)
    p.add_argument("--mode", default="mix")
    p.add_argument("--ids", help="lista de ids separada por vírgula")
    p.add_argument("--all", action="store_true", help="usa todas as 53 perguntas")
    p.add_argument("--compare", nargs=2, metavar=("TAG_A", "TAG_B"))
    a = p.parse_args(argv)
    if a.compare:
        compare(*a.compare)
        return 0
    if not a.tag:
        p.error("informe --tag (ex.: --tag high) ou --compare A B")
    ids = None if a.all else (a.ids.split(",") if a.ids else DEFAULT_IDS)
    run(a.tag, ids, a.repeats, a.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

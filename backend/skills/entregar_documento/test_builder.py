"""Teste host da logica pura da skill entregar_documento (_pick_object).

Roda sem Docker:
    python3 backend/skills/entregar_documento/test_builder.py

Nao exercita o resolvedor por IA nem o Storage (deps do projeto); cobre a logica
de decisao matched/candidatos, que e onde mora a complexidade. Carrega handler.py
por caminho (modulo-level so usa stdlib).
"""
import importlib.util
import sys
from pathlib import Path

_HANDLER = Path(__file__).resolve().parent / "handler.py"
_spec = importlib.util.spec_from_file_location("_ed_handler", _HANDLER)
mod = importlib.util.module_from_spec(_spec)
sys.modules["_ed_handler"] = mod
_spec.loader.exec_module(mod)


def main():
    fails = []

    def chk(cond, msg):
        print(("OK   " if cond else "FALHA ") + msg)
        if not cond:
            fails.append(msg)

    objs = ["Manual do Coordenador.pdf", "Regimento.pdf", "Edital 2026.pdf"]

    # 1) match claro
    m, c = mod._pick_object(
        {"wants_download": True, "object_name": "Regimento.pdf", "candidates": []}, objs
    )
    chk(m == "Regimento.pdf" and c == [], "match claro -> matched, sem candidatos")

    # 2) ambiguo -> candidatos (filtrados aos que existem no bucket)
    m, c = mod._pick_object(
        {"wants_download": True, "object_name": None,
         "candidates": ["Manual do Coordenador.pdf", "Inexistente.pdf"]},
        objs,
    )
    chk(m is None and c == ["Manual do Coordenador.pdf"],
        "ambiguo -> sem match, candidatos filtrados ao bucket")

    # 3) nao e download
    m, c = mod._pick_object({"wants_download": False, "object_name": None, "candidates": []}, objs)
    chk(m is None and c == [], "wants_download False -> nada")

    # 4) object_name fora da lista (defensivo) -> nao casa
    m, c = mod._pick_object(
        {"wants_download": True, "object_name": "Fantasma.pdf", "candidates": []}, objs
    )
    chk(m is None and c == [], "object_name fora do bucket -> nao casa")

    # 5) decisao vazia/None
    m, c = mod._pick_object({}, objs)
    chk(m is None and c == [], "decisao vazia -> nada")

    print()
    if fails:
        print(f"=== {len(fails)} FALHA(S) ===")
        sys.exit(1)
    print("=== CHECKS OK ===")


if __name__ == "__main__":
    main()

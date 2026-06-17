"""Teste host da funcao pura de geracao da skill gerar_documento_pdf.

Roda sem Docker:
    python3 backend/skills/gerar_documento_pdf/test_builder.py

Testa a geracao do PDF apenas se `markdown` e `weasyprint` estiverem disponiveis
no ambiente (deps pesadas, presentes na imagem do backend). Caso contrario, faz
SKIP. Carrega handler.py por caminho (modulo-level so usa stdlib).
"""
import importlib.util
import sys
from pathlib import Path

_HANDLER = Path(__file__).resolve().parent / "handler.py"
_spec = importlib.util.spec_from_file_location("_pdf_handler", _HANDLER)
mod = importlib.util.module_from_spec(_spec)
sys.modules["_pdf_handler"] = mod
_spec.loader.exec_module(mod)


def main():
    fails = []

    def chk(cond, msg):
        print(("OK   " if cond else "FALHA ") + msg)
        if not cond:
            fails.append(msg)

    try:
        import markdown  # noqa: F401
        import weasyprint  # noqa: F401
        has_deps = True
    except Exception:
        has_deps = False

    if not has_deps:
        print("SKIP pdf (markdown/weasyprint ausentes neste ambiente)")
        print("\n=== CHECKS OK (skip) ===")
        return

    md = "## Secao\n\nTexto com **negrito**.\n\n- item 1\n- item 2\n"
    pdf = mod._build_pdf_bytes("Relatorio FAI", md, rodape="FAI - UFSCar")
    chk(isinstance(pdf, bytes) and len(pdf) > 0, "pdf: bytes nao-vazios")
    chk(pdf[:5] == b"%PDF-", "pdf: assinatura %PDF-")

    print()
    if fails:
        print(f"=== {len(fails)} FALHA(S) ===")
        sys.exit(1)
    print("=== CHECKS OK ===")


if __name__ == "__main__":
    main()

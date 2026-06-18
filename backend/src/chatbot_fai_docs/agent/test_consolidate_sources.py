"""Testes de consolidate_sources (funde linhas '> Fonte:' do mesmo arquivo).

    python3 backend/src/chatbot_fai_docs/agent/test_consolidate_sources.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.agent_service import consolidate_sources  # noqa: E402

failures = 0


def check(cond, msg):
    global failures
    if not cond:
        failures += 1
    print(f"[{'ok ' if cond else 'FALHOU'}] {msg}")


# Caso do usuario: 3 linhas do mesmo arquivo -> 1 linha com paginas agrupadas
entrada = (
    "Texto da resposta.\n"
    "> Fonte: [M-coordenadoresFAI-01-06_1.pdf, pág. 26]\n"
    "> Fonte: [M-coordenadoresFAI-01-06_1.pdf, pág. 30]\n"
    "> Fonte: [M-coordenadoresFAI-01-06_1.pdf, pág. 31]"
)
out = consolidate_sources(entrada)
check("> Fonte: [M-coordenadoresFAI-01-06_1.pdf, págs. 26, 30, 31]" in out,
      f"funde 3 linhas do mesmo arquivo ({out!r})")
check(out.count("Fonte:") == 1, "sobra apenas UMA linha de fonte")
check(out.startswith("Texto da resposta."), "preserva o corpo da resposta")

# Pagina unica repetida -> dedup + 'pág.' singular
entrada2 = "> Fonte: [Manual.pdf, pág. 5]\n> Fonte: [Manual.pdf, pág. 5]"
out2 = consolidate_sources(entrada2)
check(out2 == "> Fonte: [Manual.pdf, pág. 5]", f"dedup + singular ({out2!r})")

# Dois arquivos distintos -> uma linha por arquivo, na ordem de aparicao
entrada3 = (
    "> Fonte: [A.pdf, pág. 3]\n"
    "> Fonte: [B.pdf, pág. 9]\n"
    "> Fonte: [A.pdf, pág. 7]"
)
out3 = consolidate_sources(entrada3)
check("> Fonte: [A.pdf, págs. 3, 7]" in out3, f"agrupa A ({out3!r})")
check("> Fonte: [B.pdf, pág. 9]" in out3, "mantem B")
check(out3.index("[A.pdf") < out3.index("[B.pdf"), "ordem de 1a aparicao preservada")

# Uma unica fonte -> intacta (nada a fundir)
uma = "Resposta.\n> Fonte: [X.pdf, pág. 12]"
check(consolidate_sources(uma) == uma, "uma fonte so: inalterada")

# Sem fonte -> intacto
semf = "Apenas texto, sem citacao."
check(consolidate_sources(semf) == semf, "sem fonte: inalterado")

# Intervalo na citacao expande e reagrupa
entrada4 = "> Fonte: [Y.pdf, págs. 10-12]\n> Fonte: [Y.pdf, pág. 15]"
out4 = consolidate_sources(entrada4)
check("> Fonte: [Y.pdf, págs. 10, 11, 12, 15]" in out4, f"expande intervalo ({out4!r})")

# Citacao no meio de paragrafo (nao e linha isolada) -> nao mexe
inline = "Veja em > Fonte: [Z.pdf, pág. 1] e tambem aqui."
check(consolidate_sources(inline) == inline, "citacao inline (nao-linha) intacta")

print()
print("RESULTADO:", "TODOS OK" if failures == 0 else f"{failures} FALHA(S)")
sys.exit(1 if failures else 0)

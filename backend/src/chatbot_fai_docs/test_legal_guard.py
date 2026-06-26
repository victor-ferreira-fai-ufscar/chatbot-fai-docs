"""Testes da lógica pura do guard anti-alucinação de referência legal.

    python3 backend/src/chatbot_fai_docs/test_legal_guard.py

Carrega legal_guard.py ISOLADO (só depende de `re`), evitando o __init__ pesado do pacote.
"""
import importlib.util
import sys
from pathlib import Path

_mod = Path(__file__).resolve().parent / "legal_guard.py"
_spec = importlib.util.spec_from_file_location("_legal_guard_under_test", _mod)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

failures = 0


def check(cond, msg):
    global failures
    if not cond:
        failures += 1
    print(f"[{'ok ' if cond else 'FALHOU'}] {msg}")


# allowlist simulando o manual: contém 8.241, 5.452, 10.406, 14.133; NÃO contém 116
allowed = {"8.241", "5.452", "10.406", "14.133", "013"}

# --- law_numbers_in: extrai o NÚMERO-BASE (antes do /ano) ---
check(m.law_numbers_in("conforme o Decreto nº 8.241/2014") == {"8.241"}, "extrai numero-base com ano")
check(m.law_numbers_in("Lei Complementar nº 116/2003 (ISS)") == {"116"}, "extrai 116 da LC")
check(m.law_numbers_in("texto sem norma nenhuma") == set(), "sem norma -> vazio")
check("5.452" in m.law_numbers_in("Decreto-Lei nº 5.452/1943 (CLT)"), "extrai 5.452 da CLT")

g = lambda: m.LegalRefGuard(allowed)

out = (lambda gd: gd.feed("A compra segue o Decreto nº 8.241/2014. ") + gd.flush())(g())
check("8.241" in out, "mantem frase que cita lei do manual (8.241)")

out = (lambda gd: gd.feed("O serviço é regido pela Lei Complementar nº 116/2003 (ISS). ") + gd.flush())(g())
check(out.strip() == "", "descarta frase que cita lei AUSENTE no manual (116/2003)")

out = (lambda gd: gd.feed("Os autônomos seguem o Decreto-Lei nº 5.452/1943 e a Lei nº 10.406/2002. ") + gd.flush())(g())
check("5.452" in out, "mantem CLT/Codigo Civil referenciados no manual mesmo com ano acrescentado")

out = (lambda gd: gd.feed("Aplica-se a Lei 8.241/2014 e a Lei Complementar 116/2003 ao caso. ") + gd.flush())(g())
check("116" not in out, "remove frase mista que contem lei fabricada")

# streaming: número partido entre chunks não deve ser quebrado pela divisão de frases
gd = g()
out = gd.feed("Vale o Decreto-Lei 5.4") + gd.feed("52/1943 aqui. fim disso. ") + gd.flush()
check("5.452/1943" in out, "nao quebra o numero entre chunks de streaming")

out = (lambda gd: gd.feed("O prazo é de 7 dias úteis. ") + gd.flush())(g())
check("7 dias" in out, "frase normal sem norma passa intacta")

# fallback verificado contém as leis que o manual realmente referencia (incl. ISS 116)
check("8.241" in m._FALLBACK_ALLOWED and "116" in m._FALLBACK_ALLOWED
      and "999.999" not in m._FALLBACK_ALLOWED,
      "fallback contem leis do manual (incl. ISS 116) e nao numeros arbitrarios")

# A citacao '[...]' NAO pode ser partida pelo ponto de "pág."/"págs." (senao a
# normalizacao do nome do arquivo, a jusante, nao casa o '[...]' inteiro e o nome
# errado escrito pelo modelo vaza no corpo da resposta).
gd = g()
out = gd.feed("Texto base. ") + gd.feed("> Fonte: [Arquivo.pdf, pá") + gd.feed("gs. 38, 39, 40]") + gd.flush()
check("[Arquivo.pdf, págs. 38, 39, 40]" in out, "mantem a citacao '[...]' INTEIRA apesar do ponto de 'págs.'")
gd = g()
out = gd.feed("Resp. ") + gd.feed("> Fonte: [X.pdf, pág. 25]") + gd.flush()
check("[X.pdf, pág. 25]" in out, "mantem a citacao com 'pág.' singular inteira")

print(f"\n{'TODOS OK' if not failures else str(failures) + ' FALHA(S)'}")
sys.exit(1 if failures else 0)

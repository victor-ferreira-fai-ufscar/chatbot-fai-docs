"""Teste do gate social (is_smalltalk) — protege a fronteira social/factual que o
guard de grounding do agente e o campo `swallowed` da bateria passam a usar.

    python3 backend/src/chatbot_fai_docs/test_smalltalk_gate.py

Import direto do módulo (sem o __init__ pesado do pacote): o gate só usa stdlib.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smalltalk_gate import is_smalltalk, is_social_turn  # noqa: E402

# (mensagem, esperado). Reais = as do guard set das baterias (perguntas curtas com
# cara de social são o caso perigoso: TÊM que ir para o manual).
CASES = [
    # sociais genuínas -> True
    ("bom dia", True),
    ("Obrigado!", True),
    ("quem é você?", True),
    ("ok, entendi", True),
    ("tchau", True),
    ("Olá, tudo bem?", True),
    ("valeu Lina", True),
    # perguntas REAIS -> False (guard set)
    ("Como verificar se o produto que preciso adquirir já possui uma ata de "
     "registro de preços vigente?", False),
    ("Qual o primeiro passo para cadastrar um projeto?", False),
    ("Qual o percentual de participantes externos permitido no projeto?", False),
    ("Como ter acesso ao site da FAI?", False),
    ("Como acessar o sistema Assina FAI?", False),
    # mistas / pedido de ajuda com tema -> False (o tema manda)
    ("oi, como faço uma solicitação de compra?", False),
    ("bom dia, preciso de ajuda com a prestação de contas", False),
    # vazia / longa demais -> False
    ("", False),
    ("obrigado " * 20, False),
]


# is_social_turn: predicado PERMISSIVO do guard de grounding — deve aceitar social
# de forma livre (fora do vocabulario fechado) mas NUNCA uma pergunta/pedido real.
SOCIAL_TURN_CASES = [
    # sociais de forma livre -> True (is_smalltalk daria False nestes)
    ("Muito obrigado pela ajuda, consegui enviar o relatório de prestação de "
     "contas, tenha um ótimo dia!", True),
    ("Obrigado pela ajuda!", True),
    ("deu tudo certo com o relatório, obrigado!", True),
    ("valeu, você salvou meu dia", True),
    ("bom dia", True),  # via is_smalltalk
    # perguntas/pedidos reais -> False
    ("Como verificar se o produto já possui ata de registro de preços vigente?", False),
    ("obrigado! e como faço a prestação de contas?", False),
    ("bom dia, preciso de ajuda com a prestação de contas", False),
    ("me manda o manual", False),
    ("gera uma planilha com os prazos", False),
    ("Qual o limite de compra direta?", False),
]


def main():
    failures = []
    for msg, want in CASES:
        got = is_smalltalk(msg)
        ok = got is want or got == want
        print(("OK   " if ok else "FALHA ") + f"is_smalltalk({msg[:60]!r}) = {got} (esperado {want})")
        if not ok:
            failures.append(msg)
    for msg, want in SOCIAL_TURN_CASES:
        got = is_social_turn(msg)
        ok = got == want
        print(("OK   " if ok else "FALHA ") + f"is_social_turn({msg[:60]!r}) = {got} (esperado {want})")
        if not ok:
            failures.append(msg)
    print()
    if failures:
        print(f"=== {len(failures)} FALHA(S) ===")
        sys.exit(1)
    print("=== TODOS OS CHECKS PASSARAM ===")


if __name__ == "__main__":
    main()

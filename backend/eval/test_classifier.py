"""Teste de regressão do CLASSIFICADOR da bateria (classify: abstained/swallowed).

    python3 backend/eval/test_classifier.py

Fixtures tiradas de respostas REAIS do .bateria_consolidado.json (2026-07-15):
o medidor precisa detectar o que a heurística antiga deixava passar (swallow do
Alberto Q2; "não fornece" da Nilva Q11) sem criar falso-positivo nas fundamentadas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bateria_consolidado import classify  # noqa: E402

Q_REAL = ("Como verificar se o produto que preciso adquirir já possui uma ata "
          "de registro de preços vigente?")
Q_SOCIAL = "bom dia"

# (nome, answer, sources, question, err, abstained_esperado, swallowed_esperado)
CASES = [
    # Alberto Q2 real: saudação a pergunta operacional, skill chamada, 0 fontes
    ("swallow Alberto Q2",
     "Olá! Sou a Lina, assistente virtual da FAI•UFSCar. Como posso ajudar?",
     [], Q_REAL, None, False, True),
    # Nilva Q11: "não fornece" escapava do regex antigo -> agora abstenção
    ("abstenção 'não fornece'",
     "O manual não fornece informações sobre o percentual de participantes externos.",
     [], "Qual o percentual de externos?", None, True, False),
    # direcionamento oficial (sentinela substituída) -> abstenção
    ("abstenção direcionamento",
     "Para essa questão, recomendo entrar em contato com o Gestor da sua área ou "
     "com o Supervisor de Projetos Específicos.",
     [], Q_REAL, None, True, False),
    # resposta fundamentada com card e citação -> nenhum flag
    ("fundamentada",
     "O limite de compra direta é R$ 17.600,00.\n\n> Fonte: [Manual dos "
     "Coordenadores.pdf, pág. 32]",
     ["- Manual dos Coordenadores.pdf (pág. 32 · 91%)"], "Qual o limite?", None,
     False, False),
    # regra 2.2: fundamentada que observa "não detalha sub-ponto" COM fonte -> ok
    ("2.2 não-detalha com fonte",
     "O manual prevê o remanejamento até 20%. O manual não detalha o caso de "
     "rubricas de capital.\n\n> Fonte: [Manual dos Coordenadores.pdf, pág. 59]",
     ["- Manual dos Coordenadores.pdf (pág. 59 · 88%)"], "Posso remanejar?", None,
     False, False),
    # citação inline SEM card (follow-up legítimo) -> não é swallow
    ("inline sem card",
     "Como citado antes, o prazo é 30 dias.\n> Fonte: [Manual dos Coordenadores.pdf, pág. 12]",
     [], "e o prazo?", None, False, False),
    # saudação a mensagem SOCIAL -> não é swallow
    ("social legítimo",
     "Olá! Sou a Lina. Como posso ajudar?",
     [], Q_SOCIAL, None, False, False),
    # social de forma LIVRE (fora do vocabulário do is_smalltalk) com resposta
    # cordial -> não é swallow (medido na validação pós-deploy: falso-positivo
    # quando a métrica usava is_smalltalk em vez de is_social_turn)
    ("social livre não é swallow",
     "Fico feliz em ajudar com o envio do relatório. Tenha um ótimo dia!",
     [], "Muito obrigado pela ajuda, consegui enviar o relatório, tenha um ótimo dia!",
     None, False, False),
    # erro de transporte -> nenhum flag de swallow
    ("erro", "", [], Q_REAL, "TimeoutError: x", False, False),
]


def main():
    failures = []
    for name, ans, sources, question, err, want_abst, want_swal in CASES:
        abst, swal = classify(ans, sources, question, err)
        ok = (abst == want_abst) and (swal == want_swal)
        print(("OK   " if ok else "FALHA ")
              + f"{name}: abstained={abst} (esp. {want_abst}) swallowed={swal} (esp. {want_swal})")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"=== {len(failures)} FALHA(S) ===")
        sys.exit(1)
    print("=== TODOS OS CHECKS PASSARAM ===")


if __name__ == "__main__":
    main()

"""Gate conversacional: decide se uma mensagem e *puramente social* (saudacao,
agradecimento, despedida ou pergunta sobre quem e a assistente) e portanto NAO
precisa acionar a busca documental (LightRAG).

Principio de projeto: ALTA PRECISAO para "pular o RAG". O erro perigoso e pular
a busca numa pergunta que de fato precisa de documento (a Lina responderia sem
ancoragem). Por isso o gate so retorna True quando a mensagem INTEIRA se resolve
em termos sociais conhecidos; qualquer coisa fora disso cai no fluxo normal
(LightRAG). Em caso de duvida, NAO pula.
"""
import re
import unicodedata


def _normalize(text: str) -> str:
    """minusculas, sem acentos, sem pontuacao/emoji, espacos colapsados."""
    text = (text or "").strip().lower()
    # remove acentos (ç->c, ã->a) para casar com os padroes sem acento
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    # tudo que nao for letra/numero/espaco vira espaco (tira pontuacao, emoji, etc.)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Uma "unidade" social: saudacao, como-vai, agradecimento, despedida, confirmacao
# de encerramento de assunto. Mensagens sociais costumam ser uma ou mais destas
# unidades encadeadas ("ola tudo bem", "ok obrigado", "valeu lina").
_UNIT = (
    r"(?:"
    r"oi+|ola+|opa+|eai|e ai|alo+|hello|hi+|hey+|hola|"          # saudacoes
    r"bom dia|boa tarde|boa noite|boas|"                          # saudacoes por periodo
    r"tudo bem|tudo bom|tudo certo|como vai|como voce esta|como esta|"  # como-vai
    r"obrigad[oa]|muito obrigad[oa]|mto obrigad[oa]|obg|valeu|vlw|grat[oa]|agradecid[oa]|agradeco|"  # agradecimento
    r"ok|okay|okk?|certo|entendi|entendido|perfeito|otim[oa]|excelente|show|legal|massa|joia|bacana|maravilha|"  # encerramento
    r"beleza|blz|ta bom|ta certo|ta otimo|"                       # encerramento informal
    r"tchau+|ate logo|ate mais|ate breve|ate a proxima|adeus|falou|flw|abracos?|abs|"  # despedida
    r"lina|bom|boa|por favor|pf"                                  # fillers aceitos junto das unidades
    r")"
)

# Mensagem inteira = uma unidade, possivelmente seguida de mais unidades
# (separadas por espaco, virgula ja virou espaco, ou "e").
_SMALLTALK_RE = re.compile(rf"^{_UNIT}(\s+(?:e\s+)?{_UNIT})*$")

# Perguntas sobre a propria assistente (identidade/funcao). A persona ja sabe
# se apresentar e tem regra de blindagem para "como voce funciona" — nenhuma
# dessas exige consultar manuais. Ancoradas: so casam a frase inteira.
_IDENTITY_RE = re.compile(
    r"^(?:oi+|ola+|opa+|bom dia|boa tarde|boa noite)?\s*(?:"
    r"quem (?:e|es|eh) (?:voce|vc|tu|(?:a )?lina)|"
    r"qual (?:e |eh )?(?:o )?(?:seu|teu) nome|"
    r"como (?:voce|vc|tu) (?:se chama|funciona|trabalha)|"
    r"o que (?:voce|vc) (?:faz|sabe fazer|pode fazer|consegue fazer)|"
    r"(?:voce|vc) (?:e|eh) (?:um|uma) (?:rob[oa]|ia|inteligencia artificial|assistente|bot|maquina|programa)|"
    r"qual (?:e |eh )?(?:a )?sua funcao|"
    r"(?:para|pra) que (?:voce|vc) serve|"
    r"(?:voce|vc) pode me ajudar"
    r")\s*$"
)

# Teto de tamanho: mensagens sociais sao curtas. Acima disso, mesmo que casem,
# preferimos o RAG (defesa extra contra falsos positivos).
_MAX_LEN = 80


def is_smalltalk(question: str) -> bool:
    """True somente se a mensagem inteira for social/identitaria e curta.
    Qualquer conteudo fora do conjunto conhecido -> False (vai para o LightRAG)."""
    norm = _normalize(question)
    if not norm or len(norm) > _MAX_LEN:
        return False
    return bool(_SMALLTALK_RE.match(norm) or _IDENTITY_RE.match(norm))


# ── Predicado PERMISSIVO p/ o guard de grounding do agente (2026-07-21) ─────────
# O is_smalltalk foi desenhado p/ ALTA PRECISAO com recall baixo: o falso-negativo
# social custava so uma consulta RAG a mais. O guard de grounding INVERTE esse
# trade-off: la, um falso-negativo social ("Muito obrigado pela ajuda, consegui
# enviar o relatorio!") viraria "pergunta real sem fonte" -> 2 retries corretivos
# num agradecimento. Este predicado aceita mensagens sociais de forma LIVRE
# (agradecimento/despedida/elogio) desde que NAO haja marcador de pedido real —
# o custo do falso-positivo aqui e apenas "guard pulado neste turno" (comportamento
# pre-guard), nao "RAG pulado". O gate legado continua usando is_smalltalk.
_SOCIAL_HINT_RE = re.compile(
    r"(?:obrigad|valeu|vlw|agradec|grat[oa]|tchau|ate logo|ate mais|ate breve|"
    r"abraco|abracos|abs\b|otimo dia|boa semana|bom fim de semana|bom final de semana|"
    r"parabens|excelente|muito bom|perfeito|deu tudo certo|deu certo|consegui|"
    r"bom dia|boa tarde|boa noite)"
)
_TASK_HINT_RE = re.compile(
    r"(?:^|\s)(?:como|qual|quais|quando|onde|quem|por ?que|preciso|quero|gostaria|"
    r"pode(?:ria)? me|me (?:envia|manda|passa|ajuda|explica|mostra|diz|informa)|"
    r"gera|gere|faca|faz|crie|cria|baixa|baixar|download|duvida|ajuda com)(?:\s|$)"
)


def is_social_turn(question: str) -> bool:
    """True se a mensagem e um turno social (mesmo fora do vocabulario fechado do
    is_smalltalk): contem sinal social explicito E nenhum marcador de pergunta/pedido.
    Uso: guard de grounding do agente (question_is_social)."""
    if is_smalltalk(question):
        return True
    if "?" in (question or ""):
        return False
    norm = _normalize(question)
    if not norm:
        return False
    return bool(_SOCIAL_HINT_RE.search(norm)) and not _TASK_HINT_RE.search(norm)

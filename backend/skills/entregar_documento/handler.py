"""Skill entregar_documento: entrega um arquivo JA EXISTENTE no repositorio.

Reusa o resolvedor por IA da Fase 6 (document_resolver.resolve_document_request)
para casar a `referencia` (incl. pronomes/contexto) com um objeto do bucket e
gera um link assinado. Se ambiguo, devolve candidatos para o modelo perguntar.

A funcao `_pick_object` e PURA (decide matched/candidatos a partir do dict do
resolver) para teste isolado no host; os imports do projeto sao preguicosos
(dentro de `executar`), entao o modulo carrega so com stdlib e o loader o
descobre mesmo fora do container.
"""


def _pick_object(decision: dict, object_names: list) -> tuple:
    """A partir da decisao do resolver, devolve (matched|None, candidates).

    - matched: nome do objeto a entregar (garantido presente em object_names).
    - candidates: lista (<=8) de nomes para o modelo pedir esclarecimento.
    """
    if not decision or not decision.get("wants_download"):
        return None, []
    matched = decision.get("object_name")
    if matched and matched in object_names:
        return matched, []
    candidates = [c for c in (decision.get("candidates") or []) if c in object_names][:8]
    return None, candidates


def executar(args: dict, ctx) -> "object":
    from src.chatbot_fai_docs.agent.types import SkillResult
    from src.chatbot_fai_docs.document_resolver import resolve_document_request

    referencia = (args.get("referencia") or "").strip()
    if not referencia:
        return SkillResult(
            for_model="Erro: entregar_documento requer 'referencia' (como o usuario chamou o documento).",
            error=True,
        )
    if ctx.storage is None:
        return SkillResult(
            for_model="Erro: armazenamento (Storage) indisponivel para entregar o documento.",
            error=True,
        )
    if ctx.llm_settings is None:
        return SkillResult(
            for_model="Erro: configuracao de LLM indisponivel para resolver qual documento entregar.",
            error=True,
        )

    try:
        object_names = [
            o.get("name", "") for o in ctx.storage.list_objects(limit=100) if o.get("name")
        ]
    except Exception as e:  # noqa: BLE001
        return SkillResult(for_model=f"Erro ao listar documentos do repositorio: {e}", error=True)

    if not object_names:
        return SkillResult(
            for_model="Nao ha documentos disponiveis no repositorio para entregar.",
            error=True,
        )

    # O modelo ja decidiu entregar (chamou esta skill): sintetizamos a intencao de
    # download explicita e deixamos o resolver focar em QUAL documento + candidatos.
    pergunta = f"Por favor, envie/baixe para mim este documento: {referencia}"
    try:
        decision = resolve_document_request(
            question=pergunta,
            conversation_history=ctx.conversation_history,
            cited_sources=ctx.sources,  # fontes citadas nesta interacao (ex.: consultar_base_conhecimento)
            available_objects=object_names,
            settings=ctx.llm_settings,
        )
    except Exception as e:  # noqa: BLE001
        return SkillResult(for_model=f"Erro ao resolver qual documento entregar: {e}", error=True)

    matched, candidates = _pick_object(decision, object_names)

    if matched:
        try:
            url = ctx.storage.create_signed_url(matched, expires_in=ctx.signed_url_ttl)
        except Exception as e:  # noqa: BLE001
            return SkillResult(for_model=f"Erro ao gerar link de download de '{matched}': {e}", error=True)
        return SkillResult(
            for_model=(
                f"Documento '{matched}' localizado. O link de download sera anexado "
                f"automaticamente a resposta."
            ),
            downloads=[(matched, url)],
        )

    listed = ", ".join(candidates) if candidates else "(nenhum candidato claro)"
    return SkillResult(
        for_model=(
            f"Nao identifiquei com certeza qual documento entregar a partir de '{referencia}'. "
            f"Peca ao usuario para escolher um destes e chame a skill de novo com o nome exato: {listed}."
        ),
    )

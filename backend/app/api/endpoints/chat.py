import json
import re
import time
import requests
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.schemas.chat_schema import ChatRequest
from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.llm import ChatSettings, ChatClient
from src.chatbot_fai_docs.repository import get_repo_from_url
from src.chatbot_fai_docs.lightrag_service import LightRagService, NO_CONTEXT_MSG
from src.chatbot_fai_docs.lightrag_resolver import resolve_lightrag_url
from src.chatbot_fai_docs.smalltalk_gate import is_smalltalk, is_social_turn
from src.chatbot_fai_docs.storage_service import StorageService
from src.chatbot_fai_docs.document_resolver import resolve_document_request
from src.chatbot_fai_docs.response_cache import ResponseCache, make_key, prompts_fingerprint
from pathlib import Path

router = APIRouter()

# Token-sentinela de negativa: o modelo o emite SOZINHO (regra 2.1 do Prompt.md) quando o
# manual nao responde ao nucleo da pergunta. O gate abaixo o troca DETERMINISTICAMENTE pela
# frase fixa (NO_CONTEXT_MSG), sem preambulo e sem fontes. Assim a negativa sai sempre
# identica, em vez de depender de o modelo reproduzir a frase palavra por palavra.
NEGATIVA_SENTINEL = "SENTINELA_SEM_RESPOSTA_NO_MANUAL"


class _SentinelGate:
    """Intercepta o token-sentinela de negativa em QUALQUER posicao do stream.

    Numa negativa o modelo DEVERIA emitir so o token (regra 2.1), mas as vezes antepoe um
    preambulo ("O manual nao detalha...") ANTES do token. A versao anterior so olhava o
    INICIO da resposta, entao um token vindo DEPOIS do preambulo vazava CRU para o usuario.
    Aqui procuramos o token em qualquer posicao: seguramos os ultimos len(token)-1 chars do
    buffer (para apanha-lo mesmo partido entre chunks) e, ao encontra-lo, emitimos so o que
    veio ANTES, descartamos o token e marcamos `tripped`. O chamador, ao ver `tripped`,
    troca a resposta por NO_CONTEXT_MSG. Assim o token cru NUNCA chega ao usuario.
    """

    def __init__(self):
        self._buf = ""
        self.tripped = False

    def feed(self, text: str) -> str:
        if self.tripped:
            return ""
        self._buf += text or ""
        idx = self._buf.find(NEGATIVA_SENTINEL)
        if idx != -1:
            self.tripped = True
            out, self._buf = self._buf[:idx], ""
            return out
        # Segura os ultimos len(token)-1 chars: o token pode estar partido entre chunks.
        keep = len(NEGATIVA_SENTINEL) - 1
        if len(self._buf) > keep:
            out, self._buf = self._buf[:-keep], self._buf[-keep:]
            return out
        return ""

    def flush(self) -> str:
        if self.tripped:
            return ""
        idx = self._buf.find(NEGATIVA_SENTINEL)
        if idx != -1:
            self.tripped = True
            out, self._buf = self._buf[:idx], ""
            return out
        out, self._buf = self._buf, ""
        return out


# Relevancia (%) que os cards de fonte carregam: '- Manual X.pdf (pág. 12 · 16%)'.
_CARD_SCORE_RE = re.compile(r"·\s*(\d+)\s*%")


def _max_retrieval_score(sources) -> "float | None":
    """Maior relevancia (0..1) entre os cards de fonte coletados no turno; None se nenhum
    card traz score (rerank-off / reranker fora do ar / sem fonte). Alimenta o gate por
    score de recuperacao: um turno cujo MELHOR trecho e' fraco tem so material tangencial."""
    vals = [int(m.group(1)) / 100.0
            for ln in (sources or []) for m in _CARD_SCORE_RE.finditer(ln or "")]
    return max(vals) if vals else None


# Assinatura de NEGATIVA EM PROSA (mesma heuristica das baterias / consistency_probe,
# mantida em sincronia): "nao consta/detalha/menciona/...". So conta como negativa quando
# NAO ha linha '> Fonte:' — uma resposta fundamentada que observa "o manual nao detalha
# [sub-ponto]" (regra 2.2) NAO e negativa.
_PROSE_ABSTENTION_RE = re.compile(
    r"n[ãa]o\s+(consta|detalha|est[áa]\s+detalhad|especifica|menciona|trata|aborda|"
    r"fornece|apresenta|oferece|traz|inclui|cobre|indica|descreve|explica|define|informa|"
    r"foi\s+poss[íi]vel|encontr|disp[oõ]e|h[áa]\s+informa)", re.I)


# --- Texto das paginas citadas p/ a verificacao de grounding ----------------------------
# Le o manual page-aware (marcadores [PÁGINA N]) e mapeia N -> texto da pagina, para o
# verificador conferir a resposta contra o conteudo REAL das paginas citadas. Cache por
# mtime (o arquivo e' bind-mount; editar reflete). Docs em parents[3]/docs (mesmo /app/docs).
_MANUAL_PAGES_CACHE: dict = {}
_PAGE_MARK_SPLIT_RE = re.compile(r"\[P[ÁA]GINA\s+(\d{1,4})\]")
_CARD_PAGE_NUMS_RE = re.compile(r"p[áa]gs?\.?\s*([\d,\s]+)", re.I)


def _load_manual_pages(filename: str) -> dict:
    """{numero_pagina -> texto} do manual page-aware; {} se ausente/ilegivel (fail-open)."""
    try:
        path = Path(__file__).resolve().parents[3] / "docs" / filename
        st = path.stat()
        hit = _MANUAL_PAGES_CACHE.get(filename)
        if hit and hit[0] == st.st_mtime_ns:
            return hit[1]
        parts = _PAGE_MARK_SPLIT_RE.split(path.read_text(encoding="utf-8"))
        pages: dict = {}
        for i in range(1, len(parts), 2):
            n = int(parts[i])
            body = parts[i + 1] if i + 1 < len(parts) else ""
            pages[n] = (pages.get(n, "") + " " + body).strip()
        pages = {n: " ".join(t.split()) for n, t in pages.items()}
        _MANUAL_PAGES_CACHE[filename] = (st.st_mtime_ns, pages)
        return pages
    except Exception as e:
        print(f"[grounding_verify] manual page-aware indisponivel ({filename}): "
              f"{type(e).__name__}: {e}", flush=True)
        return {}


def _cited_page_numbers(source_lines) -> list:
    """Numeros de pagina citados nos cards de fonte ('- Manual X.pdf (pág. 65 · 64%)')."""
    out: list = []
    for ln in source_lines or []:
        for m in _CARD_PAGE_NUMS_RE.finditer(ln or ""):
            for tok in re.findall(r"\d+", m.group(1)):
                n = int(tok)
                if n not in out:
                    out.append(n)
    return out


def _manual_excerpts(source_lines, filename: str, max_per_page: int = 1800) -> str:
    """Texto (capado) das paginas citadas, rotulado por pagina; '' se nao houver."""
    pages = _load_manual_pages(filename)
    if not pages:
        return ""
    blocks = []
    for n in _cited_page_numbers(source_lines):
        body = pages.get(n)
        if body:
            blocks.append(f"[PÁGINA {n}] {body[:max_per_page]}")
    return "\n\n".join(blocks)


# Arquivos de prompt cujo CONTEUDO entra na chave do cache (editar prompt -> cache novo).
# parents[3] = raiz do backend (/app no container): app/api/endpoints/chat.py -> backend/.
# 2026-07-21: + SKILL.md da skill do manual (a description do frontmatter guia a decisao
# do agente e a reescrita da consulta; editar ela muda a resposta -> invalida o cache).
_PROMPT_FILES = [
    Path(__file__).resolve().parents[3] / "src" / "IA" / "Prompt.md",
    Path(__file__).resolve().parents[3] / "src" / "IA" / "Prompt_Skills.md",
    Path(__file__).resolve().parents[3] / "skills" / "consultar_base_conhecimento" / "SKILL.md",
]

# Cache de resposta do processo (LRU+TTL). Singleton: vive entre requisicoes, zera no
# restart do backend. Ver response_cache.py para a politica (so 1o turno, so fundamentada).
_response_cache = ResponseCache(
    ttl_seconds=settings.RESPONSE_CACHE_TTL_S,
    max_entries=settings.RESPONSE_CACHE_MAX_ENTRIES,
)


def _replay_chunks(text: str, size: int = 60):
    """Fatia o texto cacheado em pedacos word-safe para reproduzir o efeito de digitacao
    no acerto de cache (o frontend concatena os eventos 'content')."""
    buf = ""
    for word in re.split(r"(\s+)", text):
        buf += word
        if len(buf) >= size:
            yield buf
            buf = ""
    if buf:
        yield buf


def _finalize_and_persist(repo, request, conversation_id, quoted_meta,
                          full_answer, source_lines, gen_time, last_usage):
    """Persiste o turno (cria conversa+titulo se nova; salva pergunta e resposta) e emite
    o evento final 'done'. Extraido para ser reutilizado pelo caminho normal E pelo acerto
    de cache. Gera eventos SSE (strings 'data: ...')."""
    try:
        if not conversation_id:
            chat_client = ChatClient()
            # Título SEMPRE por modelo LOCAL (Ollama), independente de OPENAI_API_KEY.
            # É uma chamada barata e frequente (uma por conversa nova): não deve gastar
            # cota da OpenAI nem migrar sozinha para a nuvem quando a chave for adicionada
            # para OUTRO fim (rollback da síntese / agente).
            # Modelo via OLLAMA_TITLE_MODEL — SEPARADO do OLLAMA_MODEL de propósito:
            # o título é o único uso auxiliar do caminho quente (toda conversa nova),
            # então um modelo grande aqui disputa VRAM com o gpt-oss da síntese e faz
            # o Ollama despejar/recarregar a cada pergunta (ver comentário no config).
            title_settings = ChatSettings(
                provider="Ollama local",
                api_key="ollama",
                model=settings.OLLAMA_TITLE_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )
            try:
                suggested_title = chat_client.generate_title(request.question, title_settings)
            except Exception as e:
                print(f"Erro ao gerar título: {e}")
                suggested_title = request.question[:30] + "..."
            conversation_id = repo.create_conversation(
                title=suggested_title, rag_engine=request.rag_engine, user_id=request.user_id,
            )
            repo.add_message(conversation_id, "user", request.question,
                             metadata={"quoted": quoted_meta} if quoted_meta else None)
        else:
            repo.add_message(conversation_id, "user", request.question,
                             metadata={"quoted": quoted_meta} if quoted_meta else None)

        repo.add_message(conversation_id, "assistant", full_answer,
                         metadata={"sources": source_lines, "gen_time": gen_time, "usage": last_usage})

        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'gen_time': gen_time, 'usage': last_usage, 'sources': source_lines})}\n\n"
    except Exception as e:
        print(f"Erro ao persistir histórico: {e}")
        yield f"data: {json.dumps({'error': 'Erro ao salvar histórico: ' + str(e)})}\n\n"

# Pre-filtro barato (regex) para decidir se vale a pena acionar o resolvedor de
# documentos por IA — evita uma chamada extra de LLM em perguntas puramente
# informativas. A decisao final (intencao real + qual documento) e do LLM.
# Sem \b final para casar conjugacoes (enviar, baixar, compartilhar...).
DOWNLOAD_INTENT_RE = re.compile(
    r"(?i)\b(envi[ae]|mand[ae]|baix[ae]|download|compartilh[ae]|disponibiliz[ae]|"
    r"me\s+passa|quero|gostaria|preciso|obter)"
)
DOC_NOUN_RE = re.compile(r"(?i)\b(arquivo|documento|manual|pdf|c[oó]pia|material)\b")
# Pronomes/referencias que apontam para um documento ja mencionado no contexto
# (ex.: "me envia esse documento", "manda ele", "quero o anterior").
DOC_REF_RE = re.compile(
    r"(?i)\b(esse|essa|este|esta|aquele|aquela|isso|ele|ela|anterior|"
    r"citad[oa]|mencionad[oa]|acima|mesmo)\b"
)


def _maybe_download_request(question: str) -> bool:
    """Pre-filtro: ha verbo de envio/obtencao + um alvo (substantivo de documento
    OU um pronome/referencia)? Se sim, o resolvedor por IA decide o resto."""
    has_verb = bool(DOWNLOAD_INTENT_RE.search(question))
    has_target = bool(DOC_NOUN_RE.search(question) or DOC_REF_RE.search(question))
    return has_verb and has_target


def _bucket_manual_names(storage=None) -> list:
    """Lista os documentos disponiveis a partir do bucket 'manuais' do Supabase
    Storage (fonte da verdade), em vez de uma pasta local. Alimenta {{LISTA_MANUAIS}}
    no system prompt. Retorna [] se o Storage estiver indisponivel ou em erro."""
    try:
        if storage is None:
            if not (settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY):
                return []
            storage = StorageService(
                base_url=settings.SUPABASE_URL,
                service_key=settings.SERVICE_ROLE_KEY,
                bucket=settings.SUPABASE_BUCKET,
            )
        from src.chatbot_fai_docs.config import is_retired_manual
        retired = settings.retired_manual_patterns()
        # Filtra manuais APOSENTADOS (removidos do indice por decisao de produto): nao
        # entram em {{LISTA_MANUAIS}} do prompt nem em known_names da citacao — assim o
        # modelo nunca os anuncia nem tem seu nome "legitimado" numa citacao inline.
        return [o.get("name", "") for o in storage.list_objects(limit=100)
                if o.get("name") and not is_retired_manual(o["name"], retired)]
    except Exception:
        return []


def _run_agent(config, question: str, agent_history: list, skill_history: list,
               question_is_social: bool = False):
    """Monta o AgentService (laco de tool calling + Skills) e devolve
    (gerador_de_tuplas, AgentContext). O ctx e populado DURANTE a iteracao do
    gerador (sources/downloads coletados a cada skill), entao leia ctx.sources /
    ctx.downloads APOS consumir o gerador. Imports do agente sao preguicosos para
    que o fluxo legado (AGENT_ENABLED=False) nunca os carregue.

    Split de historico: o AGENTE raciocina sobre `agent_history` (conversa PLENA),
    mas a RECUPERACAO (skill consultar_base_conhecimento -> LightRAG) recebe so
    `skill_history` (ultimos HISTORY_TURNS) via ctx.conversation_history.

    `question_is_social`: is_social_turn() sobre a pergunta CRUA (nao a efetiva, que
    pode ter bloco de citacao prefixado) — alimenta o guard de grounding nao-social."""
    from src.chatbot_fai_docs.agent import AgentService, ToolRegistry, AgentContext
    from src.IA.Models import OllamaModel, OpenAIModel, GeminiModel

    # Documentos disponiveis = objetos do bucket 'manuais' do Supabase (fonte da
    # verdade), nao uma pasta local. Mesmo conjunto que a skill entregar_documento usa.
    storage = None
    temp_storage = None
    manual_names: list = []
    if settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY:
        storage = StorageService(
            base_url=settings.SUPABASE_URL,
            service_key=settings.SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_BUCKET,
        )
        manual_names = _bucket_manual_names(storage)
        # Bucket separado para os documentos GERADOS (temporarios). As skills de
        # geracao sobem aqui; entregar_documento continua lendo de `storage` (manuais).
        temp_storage = StorageService(
            base_url=settings.SUPABASE_URL,
            service_key=settings.SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_TEMP_BUCKET,
        )

    llm_settings = ChatSettings(
        provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
        api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
        model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
        base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
    )
    if llm_settings.provider == "Ollama local":
        model = OllamaModel(base_url=llm_settings.base_url or "http://localhost:11434/v1", model_name=llm_settings.model)
    elif llm_settings.provider == "Google Gemini":
        model = GeminiModel(api_key=llm_settings.api_key, model_name=llm_settings.model)
    else:
        model = OpenAIModel(api_key=llm_settings.api_key, base_url=llm_settings.base_url, model_name=llm_settings.model)

    registry = ToolRegistry.from_dir(settings.SKILLS_DIR, tool_timeout_s=settings.TOOL_TIMEOUT_S)
    ctx = AgentContext(
        config=config,
        storage=storage,
        temp_storage=temp_storage,
        llm_settings=llm_settings,
        # RECUPERACAO (skill -> LightRAG) ve so os ultimos HISTORY_TURNS turnos.
        conversation_history=skill_history,
        history_turns=settings.HISTORY_TURNS,
        signed_url_ttl=settings.SIGNED_URL_TTL,
        available_docs=manual_names,
    )
    # Ha alguma fonte REAL citada em turno anterior do assistente? Sem isso, a
    # liberacao de follow-up por citacao inline aceitaria uma linha '> Fonte:'
    # FABRICADA no retry (a validacao par manual x pagina fica inerte sem skill no
    # turno) — e a corretiva nao deve sugerir "manter a fonte daquele turno" que
    # nunca existiu (finding da revisao adversarial).
    _FONTE_PAGE_RE = re.compile(r">\s*Fonte:.*p[áa]gs?\.?\s*\d", re.I)
    prior_fonte = any(
        m.get("role") == "assistant" and _FONTE_PAGE_RE.search(str(m.get("content", "")))
        for m in (agent_history or [])
    )

    def _grounding_checker(final_text: str, actx) -> "str | None":
        """Detecta resposta SEM nenhuma ancora. Dois guards, na ordem:

        GUARD NAO-SOCIAL (2026-07-21, bug Alberto Q2): pergunta REAL (nao casa o
        is_social_turn) respondida sem fontes/downloads dispara a corretiva
        INDEPENDENTE do tamanho — a saudacao de 69 chars a uma pergunta operacional
        escapava do limiar de tamanho.

        GUARD SUBSTANTIVO (existente): resposta >= MIN_CHARS sem ancora (padrao da
        bateria multi-manual: passos genericos sem consultar os manuais).

        Liberacoes deterministicas (sem gastar retry): skill com fontes/downloads;
        skill que FALHOU no turno (a resposta honesta e relatar a falha);
        entregar_documento sem download (caminho ambiguo: a resposta esperada E a
        pergunta de esclarecimento); follow-up com citacao inline QUANDO o
        historico contem fonte real (prior_fonte).

        Retorna a instrucao corretiva p/ o retry do laco, ou None (resposta ok)."""
        if not settings.AGENT_GROUNDING_RETRY_ENABLED:
            return None
        t = (final_text or "").strip()
        skills_called = actx.extras.get("skills_called") or []
        if NEGATIVA_SENTINEL in t:
            # Negativa emitida SEM NENHUMA consulta neste turno, em pergunta nao-social:
            # o protocolo exige consultar ANTES de negar. Modo de falha medido na
            # validacao pos-deploy (Alberto Q2: sentinela em 5,8s com skills=[] — o
            # modelo "aprendeu" a negar de cabeca). Negativas POS-consulta (skills_called
            # nao-vazio) seguem liberadas — fluxo proprio do gate.
            if (settings.AGENT_REQUIRE_GROUNDING_NONSOCIAL and not question_is_social
                    and not skills_called and not actx.sources):
                return (
                    "ATENCAO (verificacao automatica): voce emitiu o token de negativa SEM "
                    "consultar a base de conhecimento neste turno. NAO negue de cabeca. "
                    "Chame consultar_base_conhecimento AGORA (reescreva a consulta no "
                    "vocabulario formal dos manuais, mantendo as palavras-chave da pergunta); "
                    "se o resultado NAO cobrir o nucleo da pergunta, ai sim responda "
                    f"EXATAMENTE '{NEGATIVA_SENTINEL}', sozinho."
                )
            return None                      # negativa sinalizada pos-consulta: fluxo proprio (gate)
        if actx.sources or actx.downloads:
            return None                      # skill ancorou (fontes) ou entregou (download) NESTE turno
        if actx.extras.get("skill_errors"):
            return None                      # skill rodou e FALHOU: relatar a falha e honesto, nao punir
        if "entregar_documento" in skills_called:
            return None                      # ambiguo/sem match: a pergunta de esclarecimento e a resposta certa
        # Citacao inline SEM nenhuma fonte de skill no turno: legitima apenas em
        # FOLLOW-UP cujo historico TEM fonte real (o trecho pode ter vindo de la) e
        # COM pagina. Em 1o turno (ou conversa sem fonte previa) nenhum trecho foi
        # visto -> citacao e fabricada por definicao (medido: PRO-04 citou sem
        # consultar; SIS-04 inventou pagina).
        if prior_fonte and _FONTE_PAGE_RE.search(t):
            return None
        if settings.AGENT_REQUIRE_GROUNDING_NONSOCIAL and not question_is_social:
            return (
                "ATENCAO (verificacao automatica): a pergunta do usuario trata de um tema de "
                "trabalho, mas sua resposta NAO esta ancorada em nenhuma fonte dos manuais. "
                "NAO envie assim. Escolha UMA opcao e refaca: "
                "(1) chame consultar_base_conhecimento AGORA (reescreva a consulta no "
                "vocabulario formal dos manuais, mantendo as palavras-chave) e responda "
                "APENAS com o que ela retornar, citando manual e pagina (regra 4); "
                f"(2) se os manuais nao cobrirem o nucleo da pergunta, responda EXATAMENTE "
                f"'{NEGATIVA_SENTINEL}', sozinho; "
                + ("(3) se a resposta se apoia integralmente em conteudo ja consultado NESTA "
                   "conversa, reescreva-a mantendo a linha '> Fonte:' daquele turno; "
                   if prior_fonte else
                   "(3) se o tema for claramente alheio a FAI (conhecimento geral), reenvie "
                   "uma recusa breve, sem contatos; ")
                + "(4) se voce precisa de um esclarecimento do usuario antes de responder "
                "(ex.: qual documento), reenvie apenas a pergunta de esclarecimento; "
                "(5) APENAS se a mensagem do usuario nao contiver nenhuma pergunta nem "
                "pedido (so agradecimento/despedida), reenvie a resposta cordial breve."
            )
        if len(t) < settings.AGENT_GROUNDING_MIN_CHARS:
            return None                      # curta: social/confirmacao — nao punir
        return (
            "ATENCAO (verificacao automatica): sua resposta anterior e substantiva, mas NAO esta "
            "ancorada em nenhuma fonte — nenhuma consulta aos manuais retornou trechos e nao ha "
            "linha '> Fonte:'. NAO envie assim. Escolha UMA opcao e refaca: "
            "(1) se a pergunta envolve conteudo dos manuais (processos da FAI ou uso da Area de "
            "Coordenadores), chame consultar_base_conhecimento AGORA (reescreva a consulta com as "
            "palavras-chave da pergunta) e reescreva a resposta usando APENAS o que ela retornar, "
            "citando manual e pagina (regra 4); "
            f"(2) se os manuais nao cobrirem o nucleo da pergunta, responda EXATAMENTE '{NEGATIVA_SENTINEL}', sozinho; "
            "(3) apenas se a pergunta for puramente social/sobre voce (sem conteudo de manual), "
            "reescreva a resposta normalmente; "
            "(4) se voce precisa de um esclarecimento do usuario antes de responder, "
            "reenvie apenas a pergunta de esclarecimento."
        )

    def _exhausted_fallback(final_text: str, actx) -> "str | None":
        """Retries do guard esgotados e a resposta AINDA sem ancora: sob a flag
        STRICT_FAIL (off por padrao), troca pelo token de negativa (o _SentinelGate
        substitui pela mensagem oficial). Conjuncao estrita — 1o turno, pergunta
        nao-social, nenhuma fonte/download, nenhuma skill falha/desambiguacao —
        para nunca engolir social nem esclarecimento legitimos; o residuo
        indistinguivel e a recusa fora-de-escopo (regra 2.3), dai o default off."""
        if not settings.AGENT_GROUNDING_STRICT_FAIL:
            return None
        t = (final_text or "").strip()
        if NEGATIVA_SENTINEL in t or actx.sources or actx.downloads:
            return None
        if agent_history or question_is_social:
            return None
        # Desambiguacao/falha operacional: a resposta final legitima e a pergunta
        # de esclarecimento ou o relato da falha — nao trocar pela negativa.
        if actx.extras.get("skill_errors") or \
                "entregar_documento" in (actx.extras.get("skills_called") or []):
            return None
        return NEGATIVA_SENTINEL

    chat_client = ChatClient()
    agent = AgentService(
        model,
        registry,
        max_steps=settings.MAX_TOOL_STEPS,
        instructions_mode=settings.SKILL_INSTRUCTIONS_MODE,
        system_prompt_builder=lambda c: chat_client.build_agent_system_prompt(c.available_docs),
        grounding_checker=_grounding_checker,
        max_grounding_retries=settings.AGENT_GROUNDING_MAX_RETRIES,
        exhausted_fallback=_exhausted_fallback,
    )
    # O AGENTE raciocina sobre o historico PLENO (agent_history), nao o truncado.
    return agent.run_stream(question, agent_history, ctx), ctx


def get_repo():
    # Persistencia do historico independe do motor RAG: usa Postgres se DATABASE_URL
    # estiver configurado, senao cai no repo em memoria (fallback de desenvolvimento).
    repo = get_repo_from_url(settings.DATABASE_URL)
    # ensure_ready is a no-op for in-memory repo
    repo.ensure_ready()
    return repo

@router.post("/stream")
async def chat_stream(request: ChatRequest, repo = Depends(get_repo)):
    """
    Endpoint de chat com streaming. Usa LightRAG por padrão; também suporta mecanismos alternativos se configurados.
    """
    
    def generate_response():
        start_time = time.perf_counter()
        conversation_id = request.conversation_id
        # "Modo Agentico" por requisicao: a UI pode desligar o agente (tool calling + Skills)
        # para testar alucinacao. None -> usa o default do servidor (AGENT_ENABLED). Com o
        # agente desligado, NAO ha geracao de planilha/PDF/DOCX (skills) — so o RAG direto.
        agent_on = request.agentic if request.agentic is not None else settings.AGENT_ENABLED

        # 1. Preparar Contexto (resolve o LightRAG acessivel entre os candidatos)
        lightrag_api_url = resolve_lightrag_url(settings.lightrag_candidates())
        config = AppConfig(
            docs_dir=settings.DOCS_DIR,
            database_url=settings.DATABASE_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            reranker_model=settings.RERANKER_MODEL,
            reranker_threshold=settings.RERANKER_THRESHOLD,
            lightrag_api_url=lightrag_api_url,
            lightrag_api_key=settings.LIGHTRAG_API_KEY,
            rerank_url=settings.RERANK_URL,
            rerank_fallback_enabled=settings.RERANK_FALLBACK_ENABLED,
            supabase_fallback_enabled=settings.SUPABASE_FALLBACK_ENABLED,
            retrieval_deepen_enabled=settings.RETRIEVAL_DEEPEN_ENABLED,
            retrieval_weak_min_chunks=settings.RETRIEVAL_WEAK_MIN_CHUNKS,
            retrieval_weak_max_score=settings.RETRIEVAL_WEAK_MAX_SCORE,
            retrieval_escalation_enabled=settings.RETRIEVAL_ESCALATION_ENABLED,
            retrieval_escalation_top_k=settings.RETRIEVAL_ESCALATION_TOP_K,
            retrieval_escalation_chunk_top_k=settings.RETRIEVAL_ESCALATION_CHUNK_TOP_K,
            retrieval_escalation_entity_tokens=settings.RETRIEVAL_ESCALATION_ENTITY_TOKENS,
            retrieval_escalation_relation_tokens=settings.RETRIEVAL_ESCALATION_RELATION_TOKENS,
            query_rewrite_enabled=settings.QUERY_REWRITE_ENABLED,
            query_rewrite_pgvector_hints=settings.QUERY_REWRITE_PGVECTOR_HINTS,
            recall_channel_pgvector_enabled=settings.RECALL_CHANNEL_PGVECTOR_ENABLED,
            retired_manual_patterns=tuple(settings.retired_manual_patterns()),
        )

        # Carregar historico anterior da conversa (turnos previos) para dar contexto ao LightRAG.
        # A pergunta atual NAO entra aqui; ela vai separada no parametro `query`.
        try:
            prior = repo.get_messages(conversation_id, request.user_id) if conversation_id else []
            _hist = [
                {"role": m.role, "content": m.content}
                for m in prior if m.role in ("user", "assistant")
            ]
            # RECUPERACAO (skill LightRAG + fluxo legado): so os ultimos HISTORY_TURNS turnos.
            # HISTORY_TURNS<=0 -> SEM historico. Guard explicito: sem ele, _hist[-(0*2):] ==
            # _hist[0:] devolveria a conversa INTEIRA (slice [-0:]).
            conversation_history = (
                _hist[-(settings.HISTORY_TURNS * 2):] if settings.HISTORY_TURNS > 0 else []
            )
            # AGENTE: memoria conversacional PLENA (raciocina sobre a conversa inteira),
            # capada em AGENT_HISTORY_MAX_TURNS por seguranca de contexto.
            full_history = (
                _hist[-(settings.AGENT_HISTORY_MAX_TURNS * 2):]
                if settings.AGENT_HISTORY_MAX_TURNS > 0 else []
            )
        except Exception as e:
            print(f"Erro ao carregar historico: {e}")
            conversation_history = []
            full_history = []

        # Lista de manuais reais (objetos do bucket) — alimenta {{LISTA_MANUAIS}} no prompt
        # e o nome canonico das citacoes. Uma unica consulta, reutilizada nos dois usos.
        manual_names = _bucket_manual_names()

        # Citacao (estilo "responder" do WhatsApp): se o usuario mencionou uma mensagem
        # anterior, ela e anexada como contexto explicito a pergunta enviada ao LightRAG.
        # A pergunta original (sem o bloco de citacao) e o que fica salvo no historico;
        # a citacao em si e guardada no metadata da mensagem do usuario.
        effective_question = request.question
        quoted_meta = None
        if request.quoted and request.quoted.content.strip():
            quoted_meta = {"role": request.quoted.role, "content": request.quoted.content}
            quoted_label = "assistente" if request.quoted.role == "assistant" else "usuario"
            quoted_snippet = request.quoted.content.strip()[:1200]
            effective_question = (
                f"[O usuario esta se referindo a esta mensagem anterior do {quoted_label}]:\n"
                f"\"\"\"\n{quoted_snippet}\n\"\"\"\n\n"
                f"Com base nessa mensagem citada, responda:\n{request.question}"
            )

        # Cache de resposta (consistencia + latencia). Elegivel SO no 1o turno (sem
        # historico), sem citacao (quoted) e sem intencao de download (URL assinada expira):
        # nesses casos a resposta independe de estado da conversa, entao a MESMA pergunta
        # deve dar a MESMA resposta. cache_key=None desliga leitura E escrita para este turno.
        cache_key = None
        if (settings.RESPONSE_CACHE_ENABLED and not full_history and not conversation_history
                and not request.quoted and not _maybe_download_request(request.question)):
            cache_key = make_key(request.question, request.mode, agent_on,
                                 manual_names, settings.RESPONSE_CACHE_VERSION,
                                 prompts_fp=prompts_fingerprint(_PROMPT_FILES))
            cached = _response_cache.get(cache_key)
            if cached:
                # ACERTO: reproduz a resposta fundamentada ja gerada (byte-a-byte), em chunks
                # para manter o efeito de digitacao, e persiste o turno normalmente.
                for piece in _replay_chunks(cached["answer"]):
                    yield f"data: {json.dumps({'content': piece})}\n\n"
                yield from _finalize_and_persist(
                    repo, request, conversation_id, quoted_meta,
                    cached["answer"], cached["sources"],
                    time.perf_counter() - start_time, 0)
                return

        # Roteamento. Com AGENT_ENABLED, o AGENTE (laco de tool calling + Skills)
        # decide a cada turno se/qual skill usar — incl. consultar o LightRAG SO quando
        # ha necessidade documental. Desligado (default), segue o fluxo fixo atual
        # (gate social + LightRAG), permitindo rollback instantaneo via flag.
        agent_ctx = None
        try:
            if agent_on:
                answer, agent_ctx = _run_agent(
                    config, effective_question, full_history, conversation_history,
                    # Predicado social PERMISSIVO sobre a pergunta CRUA (a efetiva pode
                    # ter bloco de citacao prefixado): no guard de grounding, o
                    # falso-negativo social custaria 2 retries num agradecimento — o
                    # trade-off e o INVERSO do gate legado (is_smalltalk, alta precisao).
                    question_is_social=is_social_turn(request.question),
                )
            else:
                # Gate conversacional: turnos puramente sociais (oi, obrigado, "quem e voce?")
                # respondem direto pelo modelo auxiliar, SEM acionar o LightRAG (economiza o
                # custo de retrieval nesses turnos). Conservador: nunca pula quando ha citacao
                # de mensagem (quoted) ou intencao de download, e o gate so casa mensagens
                # 100% sociais — na duvida, cai no LightRAG.
                use_smalltalk_gate = (
                    settings.SMALLTALK_GATE_ENABLED
                    and not request.quoted
                    and not _maybe_download_request(request.question)
                    and is_smalltalk(request.question)
                )
                if use_smalltalk_gate:
                    manual_names = _bucket_manual_names()
                    gate_settings = ChatSettings(
                        provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                        api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                        model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                        base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
                    )
                    answer = ChatClient().answer_conversational(
                        question=request.question,
                        chat_history=conversation_history,
                        settings=gate_settings,
                        available_docs=manual_names,
                    )
                    source_lines = []
                else:
                    # Fluxo padrao: LightRAG (Grafo). Supabase/Postgres desativado.
                    lightrag_service = LightRagService(config=config)
                    answer, _, source_lines = lightrag_service.answer_question_stream(
                        effective_question,
                        request.mode,
                        conversation_history=conversation_history,
                        history_turns=settings.HISTORY_TURNS,
                        available_docs=manual_names,
                    )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # 2. Processar Resposta (Streaming ou String)
        full_answer = ""
        last_usage = 0
        # Predicado social PERMISSIVO sobre a pergunta CRUA (o mesmo passado ao guard de
        # grounding do agente): os gates de negativa (score / prosa) nunca disparam em turno
        # puramente social, para nao trocar uma saudacao/agradecimento pela negativa.
        _q_is_social = is_social_turn(request.question)

        # Guard determinístico anti-alucinação de referência legal: descarta frases que
        # citem norma cujo número-base não exista no manual (ex.: ISS Lei 116/2003 inventada).
        # Casa pelo número-base, então mantém leis que o manual referencia. Ver legal_guard.py.
        from src.chatbot_fai_docs.legal_guard import LegalRefGuard, manual_law_numbers
        from src.chatbot_fai_docs.pdf_pages import _extract_pages as _law_pages
        from src.chatbot_fai_docs.source_citation import canonical_manual_name, normalize_source_citations, canonicalize_source_line, _match_cited
        _law_storage = None
        if settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY:
            try:
                _law_storage = StorageService(base_url=settings.SUPABASE_URL,
                                              service_key=settings.SERVICE_ROLE_KEY,
                                              bucket=settings.SUPABASE_BUCKET)
            except Exception:
                _law_storage = None
        guard = LegalRefGuard(manual_law_numbers(_law_storage, _law_pages))

        # Nome canonico do manual (a partir dos documentos REAIS do bucket) para normalizar
        # as citacoes "> Fonte: [...]" que o modelo escreve no corpo da resposta — impede
        # nome de arquivo fabricado (ex.: "M-coordenadoresFAI-01-06_1.pdf"). Sem canonico,
        # o normalizador remove o nome e mantem so a pagina. Ver source_citation.py.
        _canon = canonical_manual_name(manual_names)
        _canon_display = _canon.replace("_", " ") if _canon else None
        # Nomes de exibicao de TODOS os manuais reais (bucket sanitizado -> espacos). Com
        # >1 manual, a normalizacao resolve o nome POR CITACAO (o citado e a dica), senao
        # um canonico unico colapsaria TODA citacao inline no primeiro manual do bucket,
        # misatribuindo a fonte no corpo (ex.: resposta do Manual dos Coordenadores citando
        # o Manual do Sistema). Ver source_citation.normalize_source_citations(known_names=...).
        _display_names = [n.replace("_", " ") for n in (manual_names or []) if n]

        _CARD_PAGES_RE = re.compile(r"^\s*-\s*(.+?)\s*\((p[áa]g[^)]*)\)", re.I)
        def _retrieved_pages_map() -> dict:
            """{nome_display -> set de paginas RECUPERADAS neste turno}, a partir dos cards
            de fonte que as skills coletaram (agent_ctx.sources, ex.: '- Manual X.pdf
            (pág. 40 · 99%)'). Chaves normalizadas p/ os nomes de exibicao do bucket via
            _match_cited (cobre acento/underscore do source do fallback). Avaliado em tempo
            de CHAMADA: quando a resposta final streama, as skills ja rodaram e o ctx esta
            populado. Fluxo legado (agent_ctx=None) -> mapa vazio -> validacao inerte."""
            out: dict = {}
            for ln in (agent_ctx.sources if agent_ctx else []):
                m = _CARD_PAGES_RE.match(ln or "")
                if not m:
                    continue
                key = _match_cited(m.group(1), _display_names)
                if not key:
                    continue
                for n in re.findall(r"\d+", m.group(2)):
                    out.setdefault(key, set()).add(int(n))
            return out

        # Barreira DURA de intervalo: pagina citada fora de [1, total do manual] cai
        # SEMPRE — cobre o caso do mapa de recuperados vazio (validacao por par inerte),
        # por onde uma 'pág. 74' fabricada vazou num manual de 73.
        try:
            _page_bounds = {k: int(v) for k, v in
                            json.loads(settings.MANUAL_PAGE_BOUNDS or "{}").items()}
        except Exception:
            _page_bounds = None

        def _fix_cites(text: str) -> str:
            # Indexacao page-aware com marcador [PÁGINA N] no INICIO da pagina -> o modelo
            # ja cita a pagina correta; sem necessidade de deslocar (page_shift=0).
            if len(_display_names) > 1:
                # Multi-doc: alem de resolver o nome POR CITACAO, valida cada par
                # (manual, paginas) contra o que a recuperacao devolveu neste turno
                # (mata etiqueta trocada tipo PRO-04 e paginas fabricadas).
                return normalize_source_citations(text, _canon_display, known_names=_display_names,
                                                  retrieved_pages=_retrieved_pages_map() or None,
                                                  page_bounds=_page_bounds)
            return normalize_source_citations(text, _canon_display, page_bounds=_page_bounds)

        # A CONSUMICAO do gerador e onde o streaming do LightRAG realmente acontece
        # (a chamada de rede e preguicosa). O try/except acima so cobre a INVOCACAO;
        # uma falha NO MEIO do stream (timeout do socket numa sintese lenta, ou o
        # servidor encerrando a conexao) subiria sem evento e o stream morreria mudo —
        # o usuario via a resposta truncar sem aviso (o "problema de conexao" percebido).
        # Capturamos aqui para emitir uma mensagem clara e ainda finalizar/persistir o
        # que ja foi gerado.
        # Gate de negativa: intercepta o token-sentinela emitido pelo modelo (regra 2.1) e,
        # se disparar, a resposta INTEIRA vira NO_CONTEXT_MSG (sem fontes). Fica DEPOIS do
        # guard/_fix_cites (opera no texto ja visivel ao usuario) e cobre os tres branches.
        gate = _SentinelGate()
        try:
            if agent_on:
                # Consumer dedicado do agente: mapeia as tuplas do laco para eventos SSE.
                # 'thought' (raciocinio do modelo) e suprimido; 'tool_status' vai como
                # evento proprio (o frontend ignora por ora; vira chip "Consultando..." depois).
                # O agente entrega a resposta final BUFFERIZADA de uma vez (agent_service so
                # emite ('answer', final) apos aprovar o grounding), entao acumulamos o texto
                # ja processado (guard legal + fix_cites + sentinel gate) e SO decidimos os
                # gates de score/prosa DEPOIS — nada streamou ao usuario ainda, o que torna a
                # troca por negativa deterministica (nao ha texto a "des-enviar").
                agent_out = ""
                for kind, payload in answer:
                    if kind == "usage":
                        last_usage = payload
                    elif kind == "answer":
                        agent_out += gate.feed(_fix_cites(guard.feed(payload)))
                    elif kind == "tool_status":
                        yield f"data: {json.dumps({'tool_status': payload})}\n\n"
                    # 'thought' suprimido de proposito (nao vai ao usuario)
                agent_out += gate.feed(_fix_cites(guard.flush())) + gate.flush()

                _agent_sources = agent_ctx.sources if agent_ctx else []
                _has_downloads = bool(agent_ctx and agent_ctx.downloads)

                # Gate por SCORE de recuperacao (grounding PARCIAL de BAIXO score): se a
                # MELHOR fonte do turno ficou abaixo do limiar, o material e' apenas
                # tangencial e a sintese tende a inventar procedimento -> forca a negativa.
                # So com score presente (rerank ON) e fora de turno social; downloads nunca
                # sao gateados por score.
                _top_score = _max_retrieval_score(_agent_sources)
                _score_trip = (
                    settings.RETRIEVAL_SCORE_GATE_ENABLED and _top_score is not None
                    and _top_score < settings.RETRIEVAL_SCORE_GATE_THRESHOLD
                    and not _q_is_social and not _has_downloads)

                # Gate de CITACAO FABRICADA: '> Fonte:' presente, mas NENHUMA fonte recuperada
                # no turno (skill voltou vazia) -> citacao (e conteudo) inventados -> negativa.
                _fab_cite_trip = (
                    settings.FABRICATED_CITATION_GATE_ENABLED and not _q_is_social
                    and not _agent_sources and not _has_downloads
                    and "> Fonte:" in agent_out)

                if gate.tripped or _score_trip or _fab_cite_trip:
                    # Negativa sinalizada (token) OU recuperacao fraca OU citacao fabricada:
                    # descarta tudo e emite a frase fixa de direcionamento, sem fontes.
                    if not gate.tripped:
                        _why = (f"score {_top_score:.2f} < {settings.RETRIEVAL_SCORE_GATE_THRESHOLD}"
                                if _score_trip else "citacao fabricada (0 fontes recuperadas)")
                        print(f"[gate] {_why} -> negativa forcada", flush=True)
                    full_answer = NO_CONTEXT_MSG
                    source_lines = []
                    yield f"data: {json.dumps({'content': NO_CONTEXT_MSG})}\n\n"
                else:
                    source_lines = _agent_sources
                    _skills = (agent_ctx.extras.get("skills_called") if agent_ctx else []) or []
                    # Gate de NEGATIVA EM PROSA (Nilva Q19): abstencao em texto livre (casa a
                    # assinatura de negativa) SEM token, SEM linha '> Fonte:' e SEM fontes
                    # coletadas, DEPOIS de consultar a base -> tambem recebe o direcionamento
                    # oficial (senao a abstencao saia crua, sem o contato ao Gestor). Exigir a
                    # consulta evita converter recusa fora-de-escopo (regra 2.3, sem contatos).
                    _prose_trip = (
                        settings.PROSE_NEGATIVA_GATE_ENABLED and not _q_is_social
                        and agent_out.strip() and not source_lines
                        and "> Fonte:" not in agent_out
                        and bool(_PROSE_ABSTENTION_RE.search(agent_out))
                        and "consultar_base_conhecimento" in _skills)

                    # Verificacao de GROUNDING (2a opiniao): resposta SUBSTANTIVA e FUNDAMENTADA
                    # -> confere se o NUCLEO aparece nos TRECHOS RECUPERADOS (os chunks em que a
                    # sintese se baseou, coletados pela skill em ctx.extras['kb_context']). Pega
                    # o grounding parcial de ALTO score (trecho tangencial com overlap lexical:
                    # Fernando Q6 recupera "contratacao direta" e responde OUTRA pergunta) que o
                    # gate por score nao pega. Verificar contra os CHUNKS (nao o texto da pagina)
                    # evita o falso-positivo do graph-RAG. Conservador (bloqueia so quando CLARO);
                    # pula sem contexto (fail-open). Nao roda em download.
                    _verify_trip = False
                    if (not _prose_trip and settings.GROUNDING_VERIFY_ENABLED
                            and source_lines and not _q_is_social and not _has_downloads
                            and len(agent_out.strip()) >= settings.GROUNDING_VERIFY_MIN_CHARS):
                        _excerpts = (agent_ctx.extras.get("kb_context") if agent_ctx else "") or ""
                        if _excerpts:
                            from src.chatbot_fai_docs.grounding_verify import answer_is_grounded
                            _verify_settings = ChatSettings(
                                provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                                api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                                model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                                base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
                            )
                            if not answer_is_grounded(request.question, agent_out, _excerpts, _verify_settings):
                                _verify_trip = True
                                print("[gate] verificacao de grounding: nucleo nao sustentado "
                                      "pelos trechos citados -> negativa", flush=True)

                    if _prose_trip or _verify_trip:
                        full_answer = NO_CONTEXT_MSG
                        source_lines = []
                        yield f"data: {json.dumps({'content': NO_CONTEXT_MSG})}\n\n"
                    else:
                        full_answer = agent_out
                        if agent_out:
                            yield f"data: {json.dumps({'content': agent_out})}\n\n"
                        # Downloads produzidos por skills (entregar_documento/gerar_*) -> links
                        # inline em Markdown, no MESMO formato do fluxo legado (sem mudar o front).
                        for nome, url in (agent_ctx.downloads if agent_ctx else []):
                            link_md = f"\n\n📎 [Baixar **{nome}**]({url})"
                            full_answer += link_md
                            yield f"data: {json.dumps({'content': link_md})}\n\n"
            elif isinstance(answer, str):
                gated = gate.feed(_fix_cites(guard.feed(answer) + guard.flush())) + gate.flush()
                if gate.tripped:
                    full_answer = NO_CONTEXT_MSG
                    source_lines = []
                else:
                    full_answer = gated
                yield f"data: {json.dumps({'content': full_answer, 'sources': source_lines})}\n\n"
            else:
                # Gerador de streaming
                for item in answer:
                    chunk_content = ""
                    if isinstance(item, tuple):
                        ctype, content = item
                        if ctype == "usage":
                            last_usage = content
                            continue
                        if ctype == "thought":
                            # Raciocinio interno NUNCA vai ao usuario (o consumer do agente ja
                            # suprime; aqui vazava como conteudo). Alem de expor cadeia interna
                            # (as vezes em ingles), mascarava o falso-vazio do painel de fontes:
                            # texto engolido pelo canal 'thought' aparecia ao usuario, mas nao
                            # existia para o parser de citacoes.
                            continue
                        chunk_content = content
                    else:
                        chunk_content = item

                    cleaned = gate.feed(_fix_cites(guard.feed(chunk_content)))
                    if cleaned:
                        full_answer += cleaned
                        yield f"data: {json.dumps({'content': cleaned})}\n\n"
                tail = gate.feed(_fix_cites(guard.flush())) + gate.flush()
                if tail:
                    full_answer += tail
                    yield f"data: {json.dumps({'content': tail})}\n\n"
                if gate.tripped:
                    full_answer = NO_CONTEXT_MSG
                    source_lines = []
                    yield f"data: {json.dumps({'content': NO_CONTEXT_MSG})}\n\n"
        except Exception as e:
            # Log completo no servidor (tipo + mensagem) para diagnostico; ao usuario,
            # so um aviso amigavel. Segue o fluxo (entrega de doc + persistencia) com o
            # texto parcial ja gerado, em vez de derrubar a conexao sem explicacao.
            print(f"Erro durante o streaming da resposta: {type(e).__name__}: {e}")
            aviso = (
                "\n\n_A conexão com a base de conhecimento foi interrompida durante a "
                "geração da resposta. Tente novamente em instantes._"
            )
            full_answer += aviso
            yield f"data: {json.dumps({'content': aviso})}\n\n"

        # 2.1. Entrega de documento (FLUXO LEGADO): se o usuario pediu para receber/baixar
        # um manual, um resolvedor por IA identifica QUAL documento ele quer e anexa um link
        # assinado ao final da resposta. No modo agente, isso e feito pela skill
        # entregar_documento (decisao do agente), entao este bloco e pulado.
        if (not agent_on and settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY
                and _maybe_download_request(request.question)):
            try:
                storage = StorageService(
                    base_url=settings.SUPABASE_URL,
                    service_key=settings.SERVICE_ROLE_KEY,
                    bucket=settings.SUPABASE_BUCKET,
                )
                object_names = [o.get("name", "") for o in storage.list_objects(limit=100) if o.get("name")]

                resolver_settings = ChatSettings(
                    provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                    api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                    model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                    base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
                )
                decision = resolve_document_request(
                    question=effective_question,
                    conversation_history=conversation_history,
                    cited_sources=source_lines,
                    available_objects=object_names,
                    settings=resolver_settings,
                )

                if decision.get("wants_download"):
                    matched = decision.get("object_name")
                    if matched:
                        signed_url = storage.create_signed_url(matched, expires_in=settings.SIGNED_URL_TTL)
                        link_md = f"\n\n📎 [Baixar **{matched}**]({signed_url})"
                        full_answer += link_md
                        yield f"data: {json.dumps({'content': link_md})}\n\n"
                    else:
                        # Pedido de download ambiguo: perguntar ao usuario qual documento enviar.
                        candidates = decision.get("candidates") or object_names
                        candidates = [c for c in candidates if c in object_names][:8]
                        listed = "\n".join(f"- {c}" for c in candidates)
                        ask_md = (
                            "\n\nNão consegui identificar com certeza qual documento você deseja baixar. "
                            "Poderia me dizer qual destes você quer?\n\n" + listed
                        )
                        full_answer += ask_md
                        yield f"data: {json.dumps({'content': ask_md})}\n\n"
            except Exception as e:
                print(f"Erro ao resolver/anexar documento: {e}")

        # Unifica o nome exibido nas fontes (cards) com o nome canonico citado no texto,
        # quando ha um unico manual — evita "dois nomes para o mesmo documento" (LightRAG
        # cita 'Manual do Coordenador.pdf'; o bucket guarda 'Manual_dos_Coordenadores.pdf').
        if _canon_display and len(manual_names) == 1 and source_lines:
            source_lines = [canonicalize_source_line(s, _canon_display) for s in source_lines]

        # 3. Finalizar e Salvar no Backend
        final_time = time.perf_counter() - start_time

        # Grava no cache de resposta SOMENTE quando: elegivel (cache_key setado = 1o turno
        # sem quoted/download), resposta FUNDAMENTADA (tem fontes), sem erro/truncamento e
        # sem link de download (URL assinada expira). Assim nunca trava uma abstencao; quando
        # responde certo, fixa o resultado -> consistencia para repeticoes da MESMA pergunta.
        if (cache_key and full_answer and source_lines
                and "conexão com a base de conhecimento foi interrompida" not in full_answer
                and "📎 [Baixar" not in full_answer):
            _response_cache.put(cache_key, {"answer": full_answer, "sources": source_lines})

        yield from _finalize_and_persist(repo, request, conversation_id, quoted_meta,
                                         full_answer, source_lines, final_time, last_usage)

    return StreamingResponse(generate_response(), media_type="text/event-stream")

@router.get("/ollama/models")
async def get_ollama_models():
    """
    Busca os modelos locais disponíveis no Ollama.
    """
    # Usando o padrão /api/tags que é a API correta do Ollama
    base_url = settings.OLLAMA_BASE_URL.rstrip("/") if hasattr(settings, "OLLAMA_BASE_URL") and settings.OLLAMA_BASE_URL else "http://localhost:11434"
    # Ajuste: se a URL terminar em /v1, removemos pois tags fica em /api/tags
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
        
    try:
        url = f"{base_url}/api/tags"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                param_size = item.get("details", {}).get("parameter_size", "unknown")
                models.append({"name": name, "label": f"{name} ({param_size})"})
            return models
        else:
            return []
    except Exception as e:
        print(f"Erro ao buscar modelos Ollama: {e}")
        return []

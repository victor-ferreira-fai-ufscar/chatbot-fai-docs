import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT: Path = BASE_DIR.parent
    DOCS_DIR: Path = PROJECT_ROOT / "docs" / "sil"
    
    # API Settings
    PROJECT_NAME: str = "FAI Chatbot API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # LLM Settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_THRESHOLD: float = 0.0
    
    # Provider Settings
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    # Modelo do Ollama usado em tarefas auxiliares (titulo de conversa,
    # resolucao de documentos) quando nao ha OPENAI_API_KEY configurada.
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    # External Services
    DATABASE_URL: Optional[str] = None
    LIGHTRAG_API_URL: str = "http://localhost:9621"
    # Lista de candidatos (separados por virgula); o backend usa o primeiro acessivel.
    LIGHTRAG_API_URLS: Optional[str] = None
    # API key do servidor LightRAG (header X-API-Key), usada quando ele exige autenticacao
    LIGHTRAG_API_KEY: Optional[str] = None
    # Endpoint do reranker (adaptador Cohere->TEI). O backend chama p/ RE-PONTUAR os
    # chunks finais e exibir a relevancia (%) por pagina nas fontes do frontend.
    RERANK_URL: str = "http://localhost:7997/rerank"
    # Fallback de recuperacao (gap lexical): quando a busca COM reranker devolve contexto
    # VAZIO (nenhum chunk de texto passa o corte MIN_RERANK_SCORE do servidor LightRAG), a
    # sintese absteria sem fonte mesmo com o tema no manual — ex.: "reforma de laboratorio"
    # nao casa "obra/servico de engenharia" no cross-encoder do reranker. Nesse caso, refaz
    # com enable_rerank=False: os chunks voltam pela ordem do EMBEDDING (bge-m3), que
    # recupera esses sinonimos. Desligue com RERANK_FALLBACK_ENABLED=false.
    RERANK_FALLBACK_ENABLED: bool = True
    # Fallback de RESILIENCIA: quando o LightRAG falha (fora do ar/timeout/erro/vazio),
    # responde pela base vetorial Supabase/pgvector (RagService legado) + sintese Ollama
    # local. Modo DEGRADADO, acionado SO em falha do motor principal (uma negativa legitima
    # do LightRAG NAO aciona). Ver src/chatbot_fai_docs/supabase_fallback.py. Desligue com
    # SUPABASE_FALLBACK_ENABLED=false. Requer DATABASE_URL com a tabela document_chunks populada.
    SUPABASE_FALLBACK_ENABLED: bool = True

    # ── Cascata de APROFUNDAMENTO do retrieval (2026-07-21) ─────────────────────────
    # Motivada pelas 10 falsas negativas com gabarito das baterias (gap lexical: fraseado
    # coloquial nao casa o vocabulario do manual — prova A/B no caso COORD-15). Quando a
    # 1a sonda de contexto vem FRACA (poucos chunks OU score maximo baixo), escala em
    # estagios ANTES da sintese: (1) knobs mais fundos por request (valores da Onda 5);
    # (2) reformulacao canonica da query (gemma local + dicas de vocabulario do pgvector);
    # (3) rerank-off (fallback existente, generalizado p/ "fraco" alem de "vazio").
    # Latencia extra SO no caminho de falha (~5-13s); caminho feliz inalterado (a sonda
    # ja existia e os scores passam a ser REUSADOS na montagem das fontes).
    # Rollback instantaneo: RETRIEVAL_DEEPEN_ENABLED=false (volta ao fallback binario).
    RETRIEVAL_DEEPEN_ENABLED: bool = True
    # Contagem minima de chunks: criterio de fraqueza usado APENAS quando nao ha
    # scores do reranker (rerank_url ausente/fora do ar). Com scores, decide o corte
    # abaixo — 1 chunk com score alto e retrieval BOM p/ pergunta pontual.
    RETRIEVAL_WEAK_MIN_CHUNKS: int = 3
    # Corte de "contexto fraco" pelo re-score do cross-encoder (sigmoide 0..1). Medicao
    # previa (docker-compose MIN_RERANK_SCORE): ruido <=0.10, legitimo >=0.42 -> 0.35
    # fica no vale da distribuicao bimodal.
    RETRIEVAL_WEAK_MAX_SCORE: float = 0.35
    RETRIEVAL_ESCALATION_ENABLED: bool = True
    RETRIEVAL_ESCALATION_TOP_K: int = 32           # default do servidor: 24
    RETRIEVAL_ESCALATION_CHUNK_TOP_K: int = 20     # default do servidor: 16
    RETRIEVAL_ESCALATION_ENTITY_TOKENS: int = 5000
    RETRIEVAL_ESCALATION_RELATION_TOKENS: int = 4500
    # Reformulacao canonica (estagio 2): 1 chamada curta ao modelo auxiliar (OLLAMA_MODEL)
    # traduz a pergunta coloquial p/ vocabulario formal de manual + keywords hi/lo level
    # (enviadas por request -> pula a extracao de keywords do gpt-oss no re-probe).
    QUERY_REWRITE_ENABLED: bool = True
    # Dicas de vocabulario p/ o reformulador: top-3 chunks do pgvector (bge-m3 atravessa o
    # gap lexical). Os trechos NUNCA chegam a sintese/usuario — so orientam a reescrita.
    # Degrada suave p/ [] sem DATABASE_URL. 1o uso paga o load do bge-m3 CPU (~90s, singleton).
    QUERY_REWRITE_PGVECTOR_HINTS: bool = True
    # Variante (ii) — pgvector como CANAL de recall quando o LightRAG NEGA (nao so quando
    # falha): OFF ate calibrar limiar de cosseno (o kNN sempre devolve vizinhos, mesmo
    # fora de escopo -> risco de alimentar a sintese com trecho irrelevante).
    RECALL_CHANNEL_PGVECTOR_ENABLED: bool = False

    # Manuais APOSENTADOS do indice (removidos por decisao de produto) que NAO podem
    # reaparecer em NENHUMA saida ao usuario. Lista de substrings (case-insensitive,
    # separadas por virgula): um manual e' filtrado se seu nome CONTEM qualquer uma.
    # Aplica-se em (a) _bucket_manual_names -> {{LISTA_MANUAIS}} do prompt + known_names
    # da citacao, e (b) vector_store.search (fallback pgvector + dicas de vocabulario),
    # onde os chunks ainda existem (mantidos p/ resiliencia/reversibilidade — supabase_
    # vector_rag_ingest). "sistema" cobre "Manual do Sistema Area Coordenadores.pdf"
    # (com/sem underscore/acento) sem casar "Manual dos Coordenadores.pdf". Vazio = nada
    # filtrado (comportamento antigo). Para RE-ATIVAR o 2o manual, esvazie esta lista.
    RETIRED_MANUAL_PATTERNS: str = "sistema"

    def retired_manual_patterns(self) -> list:
        """Substrings normalizadas (lower) dos manuais aposentados; [] desliga o filtro."""
        return [p.strip().lower() for p in (self.RETIRED_MANUAL_PATTERNS or "").split(",")
                if p.strip()]

    # Total de paginas de cada manual (JSON nome->paginas): barreira DURA da citacao —
    # pagina citada fora de [1, total] e removida SEMPRE, mesmo quando a validacao por
    # par (manual,pagina)xrecuperado esta inerte (mapa vazio — o furo por onde uma
    # 'pág. 74' fabricada vazou num manual de 73; caso do prof. Fernando, 2026-07-22).
    # ATUALIZAR ao reindexar um manual com paginacao diferente.
    # NOTA: o Manual do Sistema foi APOSENTADO (RETIRED_MANUAL_PATTERNS) e removido daqui
    # p/ nao deixar resquicio; re-adicione o bound se um dia voltar ao indice.
    MANUAL_PAGE_BOUNDS: str = '{"Manual dos Coordenadores.pdf": 73}'
    # Default RAG engine to use when multiple are available: 'LightRAG' or 'Supabase'
    DEFAULT_RAG_ENGINE: str = "LightRAG"
    # Numero de turnos (pares user/assistant) do historico enviados a RECUPERACAO
    # (LightRAG / skill consultar_base_conhecimento / fluxo legado) como contexto de busca.
    HISTORY_TURNS: int = 5
    # Turnos MAXIMOS de historico que o AGENTE enxerga (memoria conversacional plena):
    # o agente raciocina sobre a conversa INTEIRA, enquanto a RECUPERACAO ve so os
    # ultimos HISTORY_TURNS. Teto de seguranca p/ nao estourar o contexto do modelo em
    # conversas longas. 0 = agente sem historico.
    AGENT_HISTORY_MAX_TURNS: int = 40
    # Gate conversacional: quando True, mensagens puramente sociais (saudacao,
    # agradecimento, despedida, pergunta sobre quem e a Lina) respondem direto pelo
    # modelo auxiliar, SEM acionar a busca no LightRAG (economiza ~13s nesses turnos).
    # Conservador por design: na duvida, cai no LightRAG. Desligue com env=false.
    SMALLTALK_GATE_ENABLED: bool = True

    # Agente (Fase 8: tool calling + Skills). Desligado por padrao -> rollback
    # instantaneo para o fluxo RAG fixo atual. Skills ficam em backend/skills/*/SKILL.md
    # (uma pasta por skill com SKILL.md + handler). Ver docs/plano-agente-tool-calling.md.
    AGENT_ENABLED: bool = False

    # Cache de RESPOSTA no backend (consistencia + latencia). O LightRAG nao cacheia
    # streaming, entao a sintese nao-deterministica re-roda toda vez ("as vezes responde,
    # as vezes nao"). Este cache devolve a MESMA resposta para a mesma pergunta dentro do
    # TTL. So 1o turno (sem historico) e so resposta FUNDAMENTADA (com fontes). Ver
    # src/chatbot_fai_docs/response_cache.py. Desligue com RESPONSE_CACHE_ENABLED=false.
    RESPONSE_CACHE_ENABLED: bool = True
    RESPONSE_CACHE_TTL_S: int = 86400          # 24h: estavel dentro do dia
    RESPONSE_CACHE_MAX_ENTRIES: int = 2000
    # Suba este valor (qualquer string nova) para ESTOURAR o cache na mao apos REINDEXAR
    # um manual (mesmo nome de arquivo, conteudo novo). Mudancas no Prompt.md NAO precisam
    # mais de bump: o conteudo dos prompts entra na chave via prompts_fingerprint()
    # (response_cache.py) e invalida automaticamente.
    # 2026-07-21: "2" -> "3" (SKILL.md da skill do manual mudou; agora ele tambem entra
    # no fingerprint via _PROMPT_FILES, mas o bump garante a invalidacao desta virada).
    RESPONSE_CACHE_VERSION: str = "3"

    # Guard de GROUNDING do agente: resposta sem NENHUMA fonte (nem citacao inline, nem
    # fonte de skill, nem download) volta ao modelo com instrucao corretiva (consultar a
    # base / token de negativa / reafirmar se social). Mata o padrao da bateria
    # multi-manual (passos genericos sem grounding).
    # Rollback instantaneo: AGENT_GROUNDING_RETRY_ENABLED=false no .env (master switch).
    AGENT_GROUNDING_RETRY_ENABLED: bool = True
    # 2026-07-21: 350 -> 250. Com o guard nao-social (abaixo) cobrindo respostas curtas
    # sem fonte, o papel residual do limiar e alucinacao curta POS-skill; 250 pega a
    # maioria sem punir confirmacoes/perguntas de esclarecimento (~100-200 chars).
    AGENT_GROUNDING_MIN_CHARS: int = 250
    # 2026-07-21: retry unico -> contador. O cenario encadeado tipico (resposta sem skill
    # -> retry -> consulta -> resposta sem citacao -> retry -> resposta citada) precisa
    # de 2; cabe nos MAX_TOOL_STEPS=5.
    AGENT_GROUNDING_MAX_RETRIES: int = 2
    # Guard NAO-SOCIAL (2026-07-21, bug Alberto Q2): pergunta real (nao casa o gate
    # is_smalltalk) respondida SEM nenhuma ancora dispara a corretiva INDEPENDENTE do
    # tamanho — a saudacao de 69 chars a uma pergunta operacional passava pelo limiar.
    AGENT_REQUIRE_GROUNDING_NONSOCIAL: bool = True
    # Ao ESGOTAR os retries ainda em violacao (1o turno, nao-social, sem fontes): trocar
    # a resposta pelo token de negativa em vez de aceitar texto sem ancora. OFF por
    # padrao: a conjuncao nao distingue uma recusa fora-de-escopo legitima (regra 2.3)
    # de alucinacao — reavaliar com a bateria.
    AGENT_GROUNDING_STRICT_FAIL: bool = False

    # Gate por SCORE de recuperacao (anti-alucinacao de grounding PARCIAL): o guard de
    # grounding acima so cobre "SEM nenhuma fonte"; este cobre "TEM fonte, mas TANGENCIAL".
    # Quando a MELHOR fonte recuperada no turno (relevancia % do cross-encoder, ja exibida
    # nos cards da sidebar) fica abaixo do limiar, o manual NAO cobre o nucleo perguntado e
    # a sintese tende a INVENTAR procedimento a partir do trecho vizinho (medido: Maria
    # Stela Q1 "como solicitar planilha orcamentaria" -> unica mencao e BDI de obras, pag.
    # 65, recuperada a 16% -> alucinou o procedimento). Nesse caso o endpoint FORCA a
    # negativa (NO_CONTEXT_MSG) em vez de deixar a resposta sair. So atua no caminho
    # AGENTICO e SO quando ha score (rerank ON); sem score (rerank-off / reranker fora) fica
    # inerte para nao super-abster. Limiar < RETRIEVAL_WEAK_MAX_SCORE (0.35): a cascata ja
    # escala ate 0.35; o que termina abaixo de 0.30 e' irrecuperavel. Rollback: =false.
    RETRIEVAL_SCORE_GATE_ENABLED: bool = True
    RETRIEVAL_SCORE_GATE_THRESHOLD: float = 0.30
    # Gate de NEGATIVA EM PROSA: o _SentinelGate so troca pela mensagem oficial de
    # direcionamento quando o modelo emite o TOKEN exato (regra 2.1). As vezes ele abstem em
    # texto livre ("nao foi possivel localizar...", "o manual nao menciona...") SEM o token
    # -> a abstencao saia CRUA, sem o direcionamento ao Gestor/Supervisores (bug Nilva Q19).
    # Aqui, uma resposta que CASA a assinatura de negativa, SEM linha '> Fonte:' e SEM fontes
    # coletadas, DEPOIS de a base ter sido consultada no turno, tambem vira NO_CONTEXT_MSG.
    # Conservador: exige que a skill consultar_base_conhecimento tenha rodado (sinal de
    # tema-da-FAI) para NAO converter uma recusa fora-de-escopo (regra 2.3, sem contatos).
    # Rollback: =false.
    PROSE_NEGATIVA_GATE_ENABLED: bool = True

    # Gate de CITACAO FABRICADA (deterministico): resposta que traz uma linha '> Fonte:'
    # mas NENHUMA fonte foi recuperada no turno (a skill voltou vazia) -> o modelo inventou
    # a citacao E, tipicamente, o conteudo (procedimento). Forca a negativa. Complementa a
    # validacao de citacao por par (source_citation), que fica INERTE quando nao ha par
    # recuperado (1 manual): uma 'pág. N' fabricada dentro dos limites [1, total] passava.
    # Medido: Q1 "planilha orcamentaria" com retrieval VAZIO -> inventou passo a passo +
    # '> Fonte: [Manual..., pág. X]'. Rollback: =false.
    FABRICATED_CITATION_GATE_ENABLED: bool = True

    # Verificacao de GROUNDING por LLM (2a opiniao) — DESLIGADA (INVIAVEL neste graph-RAG).
    # Ideia: apos resposta substantiva/fundamentada, 1 chamada ao modelo LOCAL confere se o
    # NUCLEO aparece nos trechos. Duas versoes tentadas em 2026-07-24, AMBAS deram LIQUIDO
    # NEGATIVO (over-abstencao de respostas LEGITIMAS e cobertas):
    #   (1) contra o texto das PAGINAS CITADAS — derrubou Q3 compras e Nilva Q19;
    #   (2) contra os CHUNKS recuperados (last_retrieved_context) — derrubou Q3 compras e Q7.
    # Causa RAIZ arquitetural: o LightRAG e' graph-RAG e a sintese usa ENTIDADES/RELACOES do
    # grafo que vao ALEM de qualquer subconjunto de texto que o backend consiga reconstruir
    # para verificar; entao o verificador sempre marca fatos legitimos como "inventados".
    # NAO ligar sem outra fonte de evidencia (ex.: o proprio contexto que o LightRAG usou na
    # sintese, hoje nao exposto). Codigo mantido (grounding_verify.py + kb_context) inerte.
    # A alucinacao de grounding PARCIAL e' tratada pelos gates determinísticos + contra-
    # exemplos no Prompt (1.5c/1.9b), que NAO super-abstem.
    GROUNDING_VERIFY_ENABLED: bool = False
    GROUNDING_VERIFY_MIN_CHARS: int = 200
    GROUNDING_VERIFY_MANUAL_TXT: str = "manual_coordenadores_page_marked.txt"

    MAX_TOOL_STEPS: int = 5            # teto de iteracoes do laco (guarda anti-loop)
    # 2026-07-21: 60 -> 180. A cascata de aprofundamento soma ~5-13s ao pior caso da skill
    # consultar_base_conhecimento ANTES da sintese, e a sintese gpt-oss think=high sozinha
    # pode passar de 60s — o timeout antigo matava o handler no meio (catraca do registry).
    TOOL_TIMEOUT_S: int = 180          # timeout por execucao de skill
    SKILLS_DIR: Path = BASE_DIR / "skills"
    SKILL_INSTRUCTIONS_MODE: str = "preamble"   # preamble | on_demand (disclosure)

    # Transcricao de Audio (Fase 4: Speech-to-Text via Whisper local)
    # WHISPER_DEVICE: 'auto' (cuda se disponivel, senao cpu) | 'cuda' | 'cpu'
    WHISPER_ENABLED: bool = True
    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "auto"
    WHISPER_LANGUAGE: str = "pt"

    # Supabase Storage (Fase 6: repositorio de documentos e entrega ao usuario)
    SUPABASE_URL: Optional[str] = None
    SERVICE_ROLE_KEY: Optional[str] = None
    ANON_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "manuais"
    SIGNED_URL_TTL: int = 3600
    # Bucket SEPARADO para documentos GERADOS pelo agente (planilhas/PDF/DOCX).
    # Mantem o bucket de manuais limpo; estes arquivos sao TEMPORARIOS e removidos
    # automaticamente apos TEMP_DOC_TTL_DAYS (varredura a cada TEMP_DOC_SWEEP_HOURS).
    SUPABASE_TEMP_BUCKET: str = "gerados"
    TEMP_DOC_CLEANUP_ENABLED: bool = True
    TEMP_DOC_TTL_DAYS: int = 3
    TEMP_DOC_SWEEP_HOURS: int = 6

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

    def lightrag_candidates(self) -> list[str]:
        """Lista de URLs candidatas do LightRAG, normalizadas (sem barra final)."""
        raw = self.LIGHTRAG_API_URLS or self.LIGHTRAG_API_URL or ""
        urls = [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
        return urls or [self.LIGHTRAG_API_URL.rstrip("/")]

settings = Settings()

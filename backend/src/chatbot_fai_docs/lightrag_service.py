import json
import logging
import re
import requests
from pathlib import Path
from typing import Generator, Tuple, Any

logger = logging.getLogger(__name__)

# Detecta o inicio de uma secao de "References"/"Referencias" adicionada pelo servidor LightRAG,
# para corta-la do texto final (cobre titulos "### References", "**References**" e "References:").
REF_SECTION_RE = re.compile(
    r"(?is)\n[ \t]*(?:#{1,6}[ \t]*|\*\*[ \t]*)?(?:references|refer[eê]ncias|fontes consultadas)\b.*\Z"
)

# Mensagens de fallback do servidor LightRAG quando nao ha contexto relevante recuperado.
FALLBACK_RE = re.compile(
    r"(?i)(no relevant context found|sorry,?\s*i'?m not able to provide an answer|\[no-context\])"
)
# Negativa amigavel em portugues (alinhada ao protocolo de negativa do Prompt.md).
# FONTE UNICA da mensagem: o endpoint (_SentinelGate e os gates deterministicos) troca o
# token-sentinela por ESTA constante. Ao alterar o texto, ajuste TAMBEM os detectores de
# abstencao das baterias, que casam por frase: bateria_consolidado.py, consistency_probe.py
# e eval_manual_qa.py -- e a descricao da regra 2.4 do Prompt.md, que diz ao modelo o que
# o token codifica.
# 2026-07-28: reescrita a pedido do usuario. Sai a mencao aos Supervisores de Projetos
# (que nunca tiveram contato direto para divulgar) e ao telefone; fica o e-mail geral.
NO_CONTEXT_MSG = (
    "Para melhor atender a essa demanda, sugerimos entrar em contato com o gestor do seu "
    "projeto. Caso ainda não tenha um gestor designado, entrar em contato com a FAI, "
    "através do e-mail: fai@fai.ufscar.br"
)

from src.chatbot_fai_docs.config import AppConfig
from src.chatbot_fai_docs.utils import get_current_date_time_pt_br
from src.chatbot_fai_docs.pdfs import list_pdf_files

# Marcador de pagina inserido no INICIO de cada pagina na indexacao page-aware:
# "[PÁGINA N]". O conteudo que SEGUE o marcador e da pagina N -> sem off-by-one (ao
# contrario do antigo rodape, que ficava no FIM da pagina e exigia +1). E daqui que
# extraimos a pagina REAL, de forma deterministica, sem depender de o modelo cita-la.
_PAGE_MARK_RE = re.compile(r"\[P[ÁA]GINA\s+(\d{1,4})\]")
# Bloco "Document Chunks" da resposta de contexto do LightRAG (only_need_context):
# um objeto JSON por linha dentro de uma cerca ```json ... ```.
_CHUNKS_BLOCK_RE = re.compile(r"Document Chunks.*?```json(.*?)```", re.S | re.I)


def _marker_pages(content: str) -> list:
    """Numeros de pagina a partir dos marcadores [PÁGINA N] (inicio de cada pagina),
    em ordem. O trecho que segue o marcador e da pagina N (sem off-by-one)."""
    return [int(m.group(1)) for m in _PAGE_MARK_RE.finditer(content or "")]


def _compact_pages(pages) -> str:
    """Formata paginas como faixas compactas: [4,5,6,9] -> '4-6, 9'. Vazio se nao houver."""
    uniq = sorted({p for p in pages if p > 0})
    if not uniq:
        return ""
    ranges = []
    start = prev = uniq[0]
    for n in uniq[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = prev = n
    ranges.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def _parse_pages_by_reference(context_text: str) -> dict:
    """A partir do texto de contexto do LightRAG (only_need_context), devolve
    {reference_id: [paginas...]} agregando os rodapes de todos os chunks daquela
    referencia. O reference_id e por DOCUMENTO (todos os chunks de um arquivo
    compartilham o mesmo id), entao o resultado e o conjunto de paginas daquele
    documento que de fato alimentaram a resposta."""
    m = _CHUNKS_BLOCK_RE.search(context_text or "")
    if not m:
        return {}
    by_ref: dict = {}
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        ref = str(obj.get("reference_id", "")).strip()
        if not ref:
            continue
        by_ref.setdefault(ref, []).extend(_marker_pages(obj.get("content", "")))
    return by_ref


def _parse_chunks(context_text: str) -> list:
    """A partir do texto de contexto do LightRAG (only_need_context), devolve
    [(reference_id, content)] por CHUNK (granularidade fina). Usado para re-pontuar
    cada trecho no reranker e mapear o score de volta para as paginas (rodape)."""
    m = _CHUNKS_BLOCK_RE.search(context_text or "")
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        ref = str(obj.get("reference_id", "")).strip()
        if ref:
            out.append((ref, obj.get("content", "") or ""))
    return out


# Modelos costumam escrever o nome do arquivo/citacao com tracos e espacos
# Unicode (hifen nao-quebravel U+2011, espaco estreito U+202F etc.), o que
# quebraria o match com o nome real (ASCII). Normalizamos para ASCII antes.
_UNICODE_FIX = {
    **dict.fromkeys(map(ord, "‐‑‒–—―−"), "-"),
    **dict.fromkeys(map(ord, "    "), " "),
}


def _norm(s: str) -> str:
    return (s or "").translate(_UNICODE_FIX)


# Citacao de pagina que o modelo escreve no corpo da resposta:
# "[arquivo.pdf, pág. 12]" / "[arquivo.pdf, págs. 4-6]" / "[arquivo.pdf - pag 12]".
_CITED_PAGE_RE = re.compile(r"\[([^\[\]]+?)[,;\s\-]+p[aá]gs?\.?\s*([\d\s,\-]+?)\]", re.I)
_PAGE_TOKEN_RE = re.compile(r"(\d{1,3})(?:\s*-\s*(\d{1,3}))?$")
# Linha de fonte "> Fonte: ..." (so no INICIO da linha). Usada para capturar a
# citacao mesmo quando o modelo foge dos colchetes — ex.: em italico/markdown
# "> Fonte: *arquivo.pdf, pág. N*" ou sem delimitador "> Fonte: arquivo.pdf, pág N".
_FONTE_LINE_RE = re.compile(r"(?im)^\s*>?\s*fonte\s*:\s*(.+)$")
# Citacao SEM colchetes dentro da linha de fonte: <arquivo>.<ext> ... pag N.
_LOOSE_CITE_RE = re.compile(
    r"([^\s,;*_\[\]][^,;*_\[\]\n]*?\.(?:pdf|docx?|txt|md))[\"'*_\]\s,;\-]+p[aá]gs?\.?\s*([\d\s,\-]+)",
    re.I,
)


def _expand_page_tokens(tok_str: str) -> list:
    """Expande "4-6, 9" -> [4,5,6,9] (faixas e isolados; descarta intervalos absurdos)."""
    pages = []
    for tok in re.split(r"[,\s]+", tok_str):
        mm = _PAGE_TOKEN_RE.match(tok.strip())
        if not mm:
            continue
        a = int(mm.group(1))
        b = int(mm.group(2)) if mm.group(2) else a
        if 0 < a <= b and b - a < 200:
            pages.extend(range(a, b + 1))
    return pages


def _parse_cited_pages(answer_text: str) -> dict:
    """{nome_do_arquivo_lower: [paginas]} a partir das citacoes que o MODELO
    escreveu na resposta. Captura o formato com colchetes ('[arquivo.pdf, pág. N]')
    E o formato solto na linha '> Fonte:' (italico/markdown ou sem delimitador),
    pois o modelo as vezes foge dos colchetes. Essa pagina e por-trecho (o modelo
    escolhe a do conteudo que usou), logo mais precisa que o conjunto recuperado;
    por isso ela e validada (anti-alucinacao) contra esse conjunto antes de usar."""
    txt = _norm(answer_text)
    out: dict = {}

    def _add(fname_raw: str, pages_str: str) -> None:
        fname = (fname_raw.strip().lower().rsplit("/", 1)[-1]
                 .rsplit("\\", 1)[-1].strip(" *_\"'"))
        pages = _expand_page_tokens(pages_str)
        if fname and pages:
            out.setdefault(fname, []).extend(pages)

    for m in _CITED_PAGE_RE.finditer(txt):
        _add(m.group(1), m.group(2))
    # Formato solto, APENAS nas linhas "> Fonte:" (evita capturar nomes de arquivo
    # mencionados no corpo da resposta).
    for fl in _FONTE_LINE_RE.finditer(txt):
        for m in _LOOSE_CITE_RE.finditer(fl.group(1)):
            _add(m.group(1), m.group(2))
    # Dedup + ordena (colchetes e formato solto podem capturar a mesma citacao).
    return {fn: sorted(set(pp)) for fn, pp in out.items()}


def _cited_pages_for(file_path: str, cited_map: dict) -> list:
    """Paginas que o modelo citou para `file_path` (match frouxo do nome, ja que
    o modelo costuma reproduzir o nome do arquivo como aparece nas fontes)."""
    fn = _norm(Path(file_path).name.lower())
    for cited_fn, pages in cited_map.items():
        if cited_fn == fn or cited_fn in fn or fn in cited_fn:
            return pages
    return []


# Entradas da secao "References" NATIVA do LightRAG ("- [1] Manual X.pdf"), que o
# REF_SECTION_RE corta do texto exibido. Nao traz pagina, mas e sinal claro de resposta
# FUNDAMENTADA (o modelo atribuiu fontes) -> habilita o reparo deterministico do painel,
# em vez de destruir a evidencia junto com a secao.
_NATIVE_REF_RE = re.compile(r"(?m)^\s*[-*]\s*\[\d{1,2}\]\s+(\S[^\n]*)$")


def _resolve_pages(retrieved: set, cited: list) -> list:
    """Paginas a exibir, dirigidas pela CITACAO do modelo (validada), nunca pelo
    conjunto recuperado cru. Se o modelo citou paginas: mostra as que se confirmam
    no recuperado (anti-alucinacao); se o recuperado nao veio (falha de rede),
    confia no citado. Se o modelo NAO citou pagina, NAO exibe nada — em especial,
    nunca despeja o conjunto recuperado inteiro (numa pergunta ampla ele traz
    dezenas de paginas e estoura o painel; negativa que escorrega do protocolo
    citando solto fica sem fonte)."""
    if not cited:
        return []
    if not retrieved:
        return list(cited)
    return [p for p in cited if p in retrieved]


def _format_source_line(file_path: str, pages) -> str:
    """Linha de fonte para o frontend. Com paginas: '- arquivo.pdf (pág. N)' ou
    '- arquivo.pdf (págs. 4-6, 9)'. Sem paginas: '- arquivo.pdf'."""
    compact = _compact_pages(pages)
    if not compact:
        return f"- {file_path}"
    label = "pág." if compact.isdigit() else "págs."
    return f"- {file_path} ({label} {compact})"


def _format_source_line_scored(file_path: str, page: int, score) -> str:
    """Linha de fonte por PAGINA com a relevancia (%) do rerank, quando disponivel:
    '- arquivo.pdf (pág. 14 · 98%)'. Sem score: '- arquivo.pdf (pág. 14)'. O '· N%' so
    e lido pela SourcesPanel (card); a lista inline da resposta o remove."""
    if score is not None and score > 0:
        return f"- {file_path} (pág. {page} · {round(score * 100)}%)"
    return f"- {file_path} (pág. {page})"


class LightRagService:
    def __init__(self, config: AppConfig):
        self.config = config

    def _build_user_prompt(self, available_docs: list | None = None) -> str:
        # Path via __file__ (mesmo padrao do llm.py): o relativo anterior dependia do CWD
        # e, rodando fora do container a partir da raiz do repo, carregava silenciosamente
        # uma copia obsoleta de src/IA (sem as regras anti-alucinacao).
        prompt_path = Path(__file__).resolve().parent.parent / "IA" / "Prompt.md"
        if prompt_path.exists():
            base_prompt = prompt_path.read_text(encoding="utf-8").strip()
            date_str, time_str = get_current_date_time_pt_br()

            # Fonte da verdade da lista de manuais = bucket (passado pelo chamador). So
            # cai na pasta local (legado) se nenhuma lista vier. Sem isso, {{LISTA_MANUAIS}}
            # ficava vazio e o modelo fabricava nomes de arquivo ao citar a fonte.
            if available_docs:
                docs_str = ", ".join(available_docs)
            elif self.config.docs_dir.exists():
                pdf_files = list_pdf_files(self.config.docs_dir)
                docs_str = ", ".join([f.name for f in pdf_files]) if pdf_files else "Nenhum documento detectado."
            else:
                docs_str = "Nenhum documento detectado."
            
            return (
                base_prompt
                .replace("{{DATA_ATUAL}}", date_str)
                .replace("{{HORA_ATUAL}}", time_str)
                .replace("{{LISTA_MANUAIS}}", docs_str)
            )
        return "Você é um assistente de IA configurado localmente."

    def _fetch_pages_by_reference(self, base_payload: dict, headers: dict) -> dict:
        """Chamada de RECUPERACAO (only_need_context) ao LightRAG, com o MESMO
        query/mode/historico da resposta, para obter os chunks usados e extrair
        deles as paginas REAIS (rodape). Deterministico: a pagina nao depende de
        o modelo escreve-la. Falha de forma suave (retorna {}), preservando o
        comportamento antigo (fonte sem pagina) caso o LightRAG nao coopere."""
        try:
            ctx_payload = dict(base_payload)
            ctx_payload["stream"] = False
            ctx_payload["only_need_context"] = True
            resp = requests.post(
                f"{self.config.lightrag_api_url}/query",
                json=ctx_payload, timeout=60, headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "") if isinstance(data, dict) else data
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            return _parse_pages_by_reference(text)
        except Exception:
            return {}

    def _fetch_context_chunks(self, base_payload: dict, headers: dict) -> list:
        """Como _fetch_pages_by_reference, mas devolve os chunks finais (pos-rerank)
        como [(reference_id, content)] — granularidade por trecho, para extrair a
        pagina (rodape) E re-pontuar a relevancia. Falha suave -> []."""
        try:
            ctx_payload = dict(base_payload)
            ctx_payload["stream"] = False
            ctx_payload["only_need_context"] = True
            resp = requests.post(
                f"{self.config.lightrag_api_url}/query",
                json=ctx_payload, timeout=60, headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "") if isinstance(data, dict) else data
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            return _parse_chunks(text)
        except Exception:
            return []

    def _rerank_scores(self, query: str, contents: list) -> list:
        """Re-pontua os chunks finais chamando o MESMO reranker do LightRAG (adaptador
        Cohere->TEI). O LightRAG nao expoe o score na resposta, entao recalculamos aqui
        para exibir a relevancia (%) por pagina. Devolve scores [0..1] alinhados a
        `contents`; falha suave -> [] (fontes saem sem %)."""
        if not getattr(self.config, "rerank_url", None) or not contents:
            return []
        try:
            resp = requests.post(
                self.config.rerank_url,
                json={"model": self.config.reranker_model, "query": query, "documents": contents},
                timeout=15,
            )
            resp.raise_for_status()
            scores = [0.0] * len(contents)
            for r in resp.json().get("results", []):
                i, s = r.get("index"), r.get("relevance_score")
                if isinstance(i, int) and 0 <= i < len(contents) and isinstance(s, (int, float)):
                    scores[i] = float(s)
            return scores
        except Exception:
            return []

    # ── Cascata de APROFUNDAMENTO do retrieval (2026-07-21) ─────────────────────────
    # Generaliza o fallback rerank-off: alem de "contexto VAZIO", trata contexto FRACO
    # (poucos chunks / score maximo baixo) escalando em estagios ANTES da unica sintese.
    # Motivacao: 10 falsas negativas com gabarito nas baterias (gap lexical coloquial ->
    # formal); o binario vazio/nao-vazio nao cobria o caso "veio pouco e ruim" (ex.:
    # Ernesto Q7 "reforma de laboratorio", o proprio exemplo do comentario do fallback).

    def _probe(self, payload: dict, headers: dict) -> tuple:
        """Sonda only_need_context + re-score no cross-encoder. -> (chunks, scores),
        alinhados. Falha suave -> ([], [])."""
        chunks = self._fetch_context_chunks(payload, headers)
        scores = self._rerank_scores(payload.get("query", ""), [c for _, c in chunks])
        return chunks, scores

    def _is_weak(self, chunks: list, scores: list) -> bool:
        """Contexto fraco = nada recuperado OU nenhum score acima do corte. Só faz
        sentido com rerank ON (scores do cross-encoder); o estagio rerank-off e
        terminal e nunca e julgado por aqui.

        O criterio principal e o SCORE: um unico chunk com score alto e um
        retrieval BOM para pergunta pontual (cascatear ali adicionaria latencia ao
        caminho feliz). A contagem minima so decide quando NAO ha scores
        (rerank_url ausente / reranker fora do ar: _rerank_scores devolve []) —
        um soluco do reranker nao pode disparar a cascata em toda consulta."""
        cfg = self.config
        if not chunks:
            return True
        if scores:
            return max(scores) < getattr(cfg, "retrieval_weak_max_score", 0.35)
        return len(chunks) < getattr(cfg, "retrieval_weak_min_chunks", 3)

    def _deepen_retrieval(self, payload: dict, headers: dict, query_rewriter=None) -> tuple:
        """Cascata base -> escalada -> reformulacao -> rerank-off. Cada estagio so roda
        se o anterior ficou FRACO. MUTA `payload` (a sintese herda a query/knobs do
        estagio vencedor). -> (chunks, scores, rerank_off, stage).

        - escalada: knobs mais fundos POR REQUEST (QueryRequest do LightRAG aceita
          top_k/chunk_top_k/max_*_tokens); as keywords da query ficam em cache no
          servidor -> re-probe custa ~1-2s.
        - reformulacao: `query_rewriter(question)` -> (consulta, hl, ll) | None. As
          keywords vao por request (pula a extracao gpt-oss). NUNCA piora: se o probe
          reformulado pontuar abaixo do melhor anterior, reverte query/keywords.
        - rerank-off: estagio terminal (sem MIN_RERANK_SCORE nao ha corte, entao o
          probe nunca vem "vazio" — avaliar fraqueza pelo proprio cross-encoder seria
          circular). Mantem a semantica do fallback antigo, sobre a MELHOR query."""
        cfg = self.config
        chunks, scores = self._probe(payload, headers)
        if not self._is_weak(chunks, scores):
            return chunks, scores, False, "base"

        stage = "base"
        if getattr(cfg, "retrieval_escalation_enabled", False):
            payload["top_k"] = getattr(cfg, "retrieval_escalation_top_k", 32)
            payload["chunk_top_k"] = getattr(cfg, "retrieval_escalation_chunk_top_k", 20)
            payload["max_entity_tokens"] = getattr(cfg, "retrieval_escalation_entity_tokens", 5000)
            payload["max_relation_tokens"] = getattr(cfg, "retrieval_escalation_relation_tokens", 4500)
            chunks, scores = self._probe(payload, headers)
            stage = "escalated"
            if not self._is_weak(chunks, scores):
                return chunks, scores, False, stage

        if query_rewriter is not None:
            rewritten = None
            try:
                rewritten = query_rewriter(payload.get("query", ""))
            except Exception as e:
                print(f"[deepen] query_rewriter falhou: {type(e).__name__}: {e}", flush=True)
            if rewritten:
                new_query, hl, ll = rewritten
                prev_query = payload.get("query", "")
                payload["query"] = new_query
                if hl:
                    payload["hl_keywords"] = hl
                if ll:
                    payload["ll_keywords"] = ll
                r_chunks, r_scores = self._probe(payload, headers)
                # A reescrita so e ADOTADA se tornar o retrieval FORTE — a sintese
                # entao responde a query reformulada (o agente re-contextualiza p/ o
                # fraseado do usuario). Se continuou fraco, REVERTE sempre: comparar
                # "fraco vs fraco" por score seria circular (0.0 >= 0.0 adotaria ate
                # probe vazio) e a deriva semantica de uma reescrita que nem ajudou
                # nao vale o risco de responder OUTRA pergunta (pior que negativa).
                if not self._is_weak(r_chunks, r_scores):
                    return r_chunks, r_scores, False, "rewritten"
                payload["query"] = prev_query
                payload.pop("hl_keywords", None)
                payload.pop("ll_keywords", None)

        if getattr(cfg, "rerank_fallback_enabled", False):
            payload["enable_rerank"] = False
            chunks = self._fetch_context_chunks(payload, headers)
            return chunks, [], True, "rerank_off"
        return chunks, scores, False, stage

    def answer_question_stream(
        self,
        question: str,
        mode: str,
        conversation_history: list | None = None,
        history_turns: int = 5,
        available_docs: list | None = None,
        query_rewriter=None,
    ) -> Tuple[Generator[Tuple[str, str], None, None], list, list]:
        """
        Retorna um gerador (para os chunks de resposta e pensamentos), uma lista vazia de search_results
        (para manter a tipagem unificada se necessário), e uma lista formatada das sources_lines originais.

        `conversation_history` é uma lista de dicts {"role", "content"} com os turnos anteriores da
        conversa, repassada ao LightRAG para manter o contexto. `history_turns` limita quantos turnos
        o LightRAG considera. `available_docs` alimenta {{LISTA_MANUAIS}} no prompt (nomes reais do bucket).
        `query_rewriter` (opcional): callable(question) -> (consulta, hl, ll) | None, usado pelo
        estagio de reformulacao da cascata de aprofundamento (retrieval_deepen_enabled).
        """
        user_prompt = self._build_user_prompt(available_docs)

        payload = {
            "query": question,
            "mode": mode,
            "stream": True,
            "user_prompt": user_prompt,
            "conversation_history": conversation_history or [],
            "history_turns": history_turns,
        }

        headers = {}
        if self.config.lightrag_api_key:
            headers["X-API-Key"] = self.config.lightrag_api_key

        # Sondagem/aprofundamento do contexto ANTES da sintese. Dois modos:
        # - CASCATA (retrieval_deepen_enabled): base -> escalada -> reformulacao ->
        #   rerank-off, cada estagio so quando o anterior vem FRACO (_is_weak). A sonda
        #   vencedora VIRA o contexto final (chunks E scores reusados abaixo) -> caminho
        #   feliz nao ganha chamada de rede (o re-score que era feito na montagem das
        #   fontes agora acontece na sonda).
        # - LEGADO (deepen off, rerank_fallback_enabled): fallback binario original —
        #   contexto VAZIO com reranker -> refaz com enable_rerank=False (ordem do
        #   embedding bge-m3, que casa sinonimos que o cross-encoder perde).
        prefetched_chunks = None
        prefetched_scores = None
        rerank_off = False
        deepen_stage = "off"
        if getattr(self.config, "retrieval_deepen_enabled", False):
            prefetched_chunks, prefetched_scores, rerank_off, deepen_stage = (
                self._deepen_retrieval(payload, headers, query_rewriter))
        elif getattr(self.config, "rerank_fallback_enabled", False):
            prefetched_chunks = self._fetch_context_chunks(payload, headers)
            if not prefetched_chunks:
                rerank_off = True
                payload["enable_rerank"] = False
                prefetched_chunks = self._fetch_context_chunks(payload, headers)

        # Contexto RECUPERADO (texto dos chunks) exposto p/ a verificacao de grounding do
        # endpoint conferir a resposta contra os CHUNKS reais — NAO o texto da pagina, que no
        # graph-RAG e' um subconjunto e gerava falso-positivo (a sintese usa fatos alem da
        # pagina top-scored). Atributo de instancia lido pela skill apos answer_question.
        self.last_retrieved_context = "\n\n".join(
            (c or "") for _, c in (prefetched_chunks or []) if c)[:8000]

        # Timeout (connect, read). O read e o GAP entre bytes do stream: com gpt-oss em
        # raciocinio "high" (via ollama-think-shim) a fase de "pensar" pode passar de 2 min
        # SEM emitir conteudo -> 120s estourava (ReadTimeout) e a resposta vinha
        # "interrompida". 600s casa com o TIMEOUT do servidor LightRAG; connect curto (10s)
        # ainda detecta o LightRAG fora do ar rapido.
        resp = requests.post(f"{self.config.lightrag_api_url}/query/stream", json=payload, stream=True, timeout=(10, 600), headers=headers)
        resp.raise_for_status()

        # Conjunto de manuais reais conhecidos (para so exibir fontes quando a referencia
        # apontar de fato para um documento indexado, evitando "References" em toda resposta).
        known_manuals = set()
        if self.config.docs_dir.exists():
            known_manuals = {f.name.lower() for f in list_pdf_files(self.config.docs_dir)}

        DOC_EXTS = (".pdf", ".docx", ".doc", ".txt", ".md")
        INVALID_PATHS = {"", "unknown_source", "unknown", "none", "null"}

        def _is_real_manual(file_path: str) -> bool:
            if not file_path or file_path.strip().lower() in INVALID_PATHS:
                return False
            name = Path(file_path).name.lower()
            # Aceita se o arquivo esta na lista de manuais conhecidos; caso a lista esteja
            # vazia, aceita qualquer caminho com extensao de documento reconhecida.
            if known_manuals:
                return name in known_manuals
            return name.endswith(DOC_EXTS)

        source_lines = []

        def stream_generator():
            in_thought = False
            seen_refs = set()
            # (file_path, reference_id) na ordem de chegada; a pagina e resolvida
            # ao final, quando ja temos todas as referencias e podemos consultar
            # o contexto recuperado de uma so vez.
            collected_refs = []

            # Estado do filtro da secao "References" no texto da resposta.
            # `answer_buf` segura um pequeno trecho final (HOLDBACK) para nao emitir um
            # titulo "References" parcial antes de detecta-lo; `cut` corta tudo apos a secao.
            answer_buf = ""
            seen_text = ""
            produced_any = False
            cut = False
            HOLDBACK = 50

            def feed_answer(text):
                nonlocal answer_buf, seen_text, produced_any, cut
                if cut or not text:
                    return
                seen_text += text
                # Enquanto nada de util foi emitido, verifica se a resposta inteira e um
                # fallback de "sem contexto" do LightRAG -> substitui por negativa em PT.
                if not produced_any and FALLBACK_RE.search(seen_text):
                    answer_buf = ""
                    cut = True
                    yield ("answer", NO_CONTEXT_MSG)
                    return
                answer_buf += text
                m = REF_SECTION_RE.search(answer_buf)
                if m:
                    head = answer_buf[:m.start()]
                    answer_buf = ""
                    cut = True
                    if head:
                        produced_any = True
                        yield ("answer", head)
                    return
                # Sem secao de References ainda: emite tudo menos um tail de seguranca
                if len(answer_buf) > HOLDBACK:
                    cut_point = len(answer_buf) - HOLDBACK
                    emit, answer_buf = answer_buf[:cut_point], answer_buf[cut_point:]
                    if emit:
                        produced_any = True
                        yield ("answer", emit)

            for line in resp.iter_lines():
                if not line:
                    continue

                data = json.loads(line)

                # Coleta as referencias da busca do grafo (apenas manuais reais, sem duplicar)
                if "references" in data:
                    refs = data["references"]
                    for ref in refs:
                        file_path = ref.get('file_path')
                        if _is_real_manual(file_path) and file_path not in seen_refs:
                            seen_refs.add(file_path)
                            collected_refs.append((file_path, str(ref.get('reference_id', '')).strip()))

                if "response" in data:
                    chunk = data["response"]

                    if "<think>" in chunk:
                        # Thinking legitimo so ABRE o stream (vem antes de qualquer texto de
                        # resposta). Um "<think>" no MEIO da resposta e eco espurio do modelo:
                        # trata-lo como abertura engolia o RESTO da resposta no canal 'thought'
                        # (que o chat.py legado exibia mesmo assim) -> o texto VISIVEL tinha a
                        # linha "> Fonte:" mas o seen_text (parser de citacao) nao -> cited_map
                        # vazio -> painel de fontes vazio (falso-vazio; casos R07/NL1). Aqui
                        # so muda de canal se ainda nao houve resposta; o token e sempre removido.
                        if not seen_text.strip() and not in_thought:
                            in_thought = True
                        chunk = chunk.replace("<think>", "")

                    if "</think>" in chunk:
                        if in_thought:
                            parts = chunk.split("</think>")
                            if parts[0]:
                                yield ("thought", parts[0])
                            in_thought = False
                            if len(parts) > 1 and parts[1]:
                                yield from feed_answer(parts[1])
                            continue
                        # "</think>" sem thinking aberto: token espurio, so remover.
                        chunk = chunk.replace("</think>", "")

                    if in_thought:
                        yield ("thought", chunk)
                    else:
                        yield from feed_answer(chunk)

                if "error" in data:
                    yield ("answer", f"\nErro: {data['error']}")

            # Flush do que sobrou no buffer (resposta sem secao de References)
            if not cut and answer_buf:
                yield ("answer", answer_buf)

            # FONTE CERTEIRA: so listamos fontes quando a resposta esta FUNDAMENTADA.
            # Pelo protocolo do prompt, uma resposta ancorada no manual SEMPRE cita
            # "> Fonte: [arquivo, pag N]"; uma NEGATIVA (tema fora do manual) NUNCA cita.
            # Logo, ausencia de citacao = abstencao/nao-fundamentada -> NAO exibir fontes
            # (evita "fonte fantasma" quando a informacao nao esta no manual, mesmo que o
            # retrieval tenha trazido chunks). Bonus: pula a 2a consulta nesse caso.
            # So exibe fontes quando ha citacao de PAGINA parseavel — em colchetes OU no
            # formato solto da linha "> Fonte:" (italico/markdown), ambos cobertos por
            # _parse_cited_pages. Um "> Fonte:" SEM pagina (tipico de respostas negativas
            # que escorregam do protocolo) NAO conta: a negativa fica sem fontes, em vez de
            # disparar o fallback que listava o conjunto recuperado inteiro.
            cited_map = _parse_cited_pages(seen_text)
            answer_cited = bool(cited_map)
            if answer_cited and collected_refs:
                # Uma unica chamada only_need_context devolve os chunks finais (pos-rerank):
                # deles extraimos a PAGINA (rodape, deterministico) e RE-PONTUAMOS a
                # relevancia no reranker (o LightRAG nao expoe o score). O score do chunk
                # propaga para as paginas que ele contem (max por pagina) -> relevancia %.
                # Reusa os chunks ja buscados pela sonda do fallback (mesmo payload); so
                # busca aqui se a sonda nao rodou (fallback desligado).
                chunks = prefetched_chunks if prefetched_chunks is not None else self._fetch_context_chunks(payload, headers)
                page_map: dict = {}
                for ref_id, content in chunks:
                    page_map.setdefault(ref_id, []).extend(_marker_pages(content))
                # No modo fallback (rerank OFF), NAO exibimos o "· N%": o reranker pontua o
                # conteudo certo perto de zero justamente para a query que disparou o
                # fallback, entao o "1%" enganaria. Sem score -> "(pag. N)" limpo.
                # Com a cascata, os scores da sonda vencedora sao REUSADOS (mesma query,
                # mesmos chunks) em vez de re-pontuar — caminho feliz sem custo extra.
                if rerank_off:
                    scores = []
                elif prefetched_scores is not None and chunks is prefetched_chunks:
                    scores = prefetched_scores
                else:
                    scores = self._rerank_scores(payload.get("query", ""), [c for _, c in chunks])
                page_score: dict = {}
                for (ref_id, content), s in zip(chunks, scores):
                    for p in _marker_pages(content):
                        if p > 0:
                            page_score[p] = max(page_score.get(p, 0.0), s)
                # Uma linha por PAGINA (com o '· N%' quando ha score), SEM REPETIR a mesma
                # pagina: se ela vier de varias refs/chunks, entra uma unica vez.
                seen_pages: set = set()
                files_with_page: set = set()
                no_page: list = []
                for file_path, ref_id in collected_refs:
                    retrieved = {p for p in page_map.get(ref_id, []) if p > 0}
                    cited = _cited_pages_for(file_path, cited_map)
                    pages = _resolve_pages(retrieved, cited)
                    if not pages:
                        no_page.append(file_path)
                        continue
                    for p in pages:
                        if (file_path, p) in seen_pages:
                            continue
                        seen_pages.add((file_path, p))
                        files_with_page.add(file_path)
                        # Marcador [PÁGINA N] -> pagina ja correta (sem offset).
                        source_lines.append(_format_source_line_scored(file_path, p, page_score.get(p)))
                # Arquivo sem nenhuma pagina resolvida: lista so o nome (1x), e apenas se
                # ele ainda nao apareceu com pagina.
                for file_path in dict.fromkeys(no_page):
                    if file_path not in files_with_page:
                        source_lines.append(f"- {file_path}")

            # REDE DE SEGURANCA (reparo deterministico do painel): o modelo SINALIZOU
            # fundamentacao (citacao "> Fonte:" parseavel OU secao "References" nativa do
            # LightRAG), mas o caminho normal nao produziu NENHUMA linha — falso-vazio
            # (ex.: evento 'references' ausente no stream, nome citado com variacao,
            # pagina citada fora do conjunto validado). Reconstroi o painel a partir dos
            # CHUNKS pos-rerank: primeiro as paginas que o MODELO citou (validadas nos
            # chunks); senao as TOP paginas por score, limitadas — NUNCA o conjunto
            # inteiro (mantem a decisao de nao despejar o recuperado). Sem sinal de
            # fundamentacao (negativa/smalltalk), NAO ha reparo: nada de fonte fantasma.
            repair_used = False
            native_refs = _NATIVE_REF_RE.findall(seen_text)
            # Sinais de fundamentacao, do mais ao menos preciso: citacao com pagina
            # (cited_map), secao References nativa, ou linha "> Fonte:" MESMO SEM pagina
            # (_FONTE_LINE_RE) — este ultimo e o caso comum de falso-vazio (o modelo cita
            # o arquivo mas esquece a pagina; sem isto o reparo nao disparava).
            grounding_signal = bool(cited_map or native_refs or _FONTE_LINE_RE.search(_norm(seen_text)))
            if not source_lines and grounding_signal:
                chunks = prefetched_chunks if prefetched_chunks is not None else self._fetch_context_chunks(payload, headers)
                pg_best: dict = {}
                if chunks:
                    if rerank_off:
                        scores = []
                    elif prefetched_scores is not None and chunks is prefetched_chunks:
                        scores = prefetched_scores
                    else:
                        scores = self._rerank_scores(payload.get("query", ""), [c for _, c in chunks])
                    for i, (_ref, content) in enumerate(chunks):
                        s = scores[i] if i < len(scores) else 0.0
                        for p in _marker_pages(content):
                            if p > 0:
                                pg_best[p] = max(pg_best.get(p, 0.0), s)
                # Nome do arquivo: preferir o que o MODELO citou (se e manual real, no case
                # canonico do disco); senao a referencia do stream; senao o unico manual local.
                fname = next((fn for fn in cited_map if _is_real_manual(fn)), None)
                if fname and known_manuals:
                    fname = next((f.name for f in list_pdf_files(self.config.docs_dir)
                                  if f.name.lower() == fname), fname)
                if not fname and collected_refs:
                    fname = Path(collected_refs[0][0]).name
                if not fname and len(known_manuals) == 1:
                    _real = list_pdf_files(self.config.docs_dir)
                    fname = _real[0].name if _real else None
                if fname and pg_best:
                    REPAIR_TOP, REPAIR_MIN = 4, 0.10
                    cited_pages = [p for pp in cited_map.values() for p in pp]
                    pages = [p for p in cited_pages if p in pg_best][:REPAIR_TOP]
                    if not pages:
                        ranked = sorted(pg_best.items(), key=lambda kv: -kv[1])
                        pages = [p for p, s in ranked if s >= REPAIR_MIN][:REPAIR_TOP] or [p for p, _s in ranked[:2]]
                    for p in sorted(set(pages)):
                        sc = None if rerank_off else pg_best.get(p)
                        source_lines.append(_format_source_line_scored(fname, p, sc if sc else None))
                    repair_used = bool(source_lines)

            # INSTRUMENTACAO (diagnostico do falso-vazio): 1 linha por request com o estado
            # de cada portao da montagem do painel. Nao loga conteudo da resposta. Usa print
            # (padrao do codebase p/ logs operacionais) porque o uvicorn nao configura este
            # logger e o INFO nao chegaria ao stdout do container.
            print(
                f"[fontes] cited_map={len(cited_map)} refs_stream={len(collected_refs)} "
                f"native_refs={len(native_refs)} prefetch={prefetched_chunks is not None} "
                f"rerank_off={rerank_off} deepen={deepen_stage} "
                f"max_score={round(max(prefetched_scores or [0.0]), 3)} "
                f"reparo={repair_used} linhas={len(source_lines)} "
                f"in_thought={in_thought} cut={cut} seen_tail={seen_text[-70:]!r}",
                flush=True,
            )

        # O retorno é o gerador em si e uma list de source_lines (sendo popularizada pelo gerador por reflexão)
        return stream_generator(), [], source_lines

    def answer_question(
        self,
        question: str,
        mode: str,
        conversation_history: list | None = None,
        history_turns: int = 5,
        available_docs: list | None = None,
        query_rewriter=None,
    ) -> Tuple[str, list]:
        """Variante NAO-stream para uso como ferramenta de agente (skill
        consultar_base_conhecimento): consome o gerador de answer_question_stream
        e devolve (texto_completo, source_lines).

        Reutiliza todo o parsing (<think>, secao References, fallback de negativa);
        os 'thought' sao descartados (so o texto de resposta importa p/ o agente).
        `source_lines` so fica populada apos consumir o gerador (e preenchida por
        reflexao durante a iteracao)."""
        gen, _, source_lines = self.answer_question_stream(
            question,
            mode,
            conversation_history=conversation_history,
            history_turns=history_turns,
            available_docs=available_docs,
            query_rewriter=query_rewriter,
        )
        parts = [content for kind, content in gen if kind == "answer"]
        return "".join(parts).strip(), source_lines

import json
import re
import requests
from pathlib import Path
from typing import Generator, Tuple, Any

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
NO_CONTEXT_MSG = (
    "Não encontrei informações sobre isso nos manuais disponíveis no momento. "
    "Você pode reformular a pergunta ou verificar se o assunto consta nos documentos indexados."
)

from src.chatbot_fai_docs.config import AppConfig
from src.chatbot_fai_docs.utils import get_current_date_time_pt_br
from src.chatbot_fai_docs.pdfs import list_pdf_files

# Um numero isolado (1 a 3 digitos) em uma linha inteira = rodape de pagina que o
# parser de PDF deixou embutido no texto do chunk. E daqui que extraimos a pagina
# REAL consultada, de forma deterministica (sem depender de o modelo cita-la).
_FOOTER_PAGE_RE = re.compile(r"(?m)^[ \t]*(\d{1,3})[ \t]*$")
# Bloco "Document Chunks" da resposta de contexto do LightRAG (only_need_context):
# um objeto JSON por linha dentro de uma cerca ```json ... ```.
_CHUNKS_BLOCK_RE = re.compile(r"Document Chunks.*?```json(.*?)```", re.S | re.I)


def _footer_pages(content: str) -> list:
    """Numeros de pagina (rodape) embutidos no texto de um chunk, em ordem."""
    return [int(m.group(1)) for m in _FOOTER_PAGE_RE.finditer(content or "")]


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
        by_ref.setdefault(ref, []).extend(_footer_pages(obj.get("content", "")))
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


def _parse_cited_pages(answer_text: str) -> dict:
    """{nome_do_arquivo_lower: [paginas]} a partir das citacoes que o MODELO
    escreveu na resposta ('[arquivo.pdf, pág. N]'). Essa pagina e por-trecho
    (o modelo escolhe a do conteudo que usou), logo mais precisa que o conjunto
    recuperado; por isso ela e validada (anti-alucinacao) contra esse conjunto
    antes de ser usada."""
    out: dict = {}
    for m in _CITED_PAGE_RE.finditer(_norm(answer_text)):
        fname = m.group(1).strip().lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
        if not fname:
            continue
        pages = []
        for tok in re.split(r"[,\s]+", m.group(2)):
            mm = _PAGE_TOKEN_RE.match(tok.strip())
            if not mm:
                continue
            a = int(mm.group(1))
            b = int(mm.group(2)) if mm.group(2) else a
            if 0 < a <= b and b - a < 200:
                pages.extend(range(a, b + 1))
        if pages:
            out.setdefault(fname, []).extend(pages)
    return out


def _cited_pages_for(file_path: str, cited_map: dict) -> list:
    """Paginas que o modelo citou para `file_path` (match frouxo do nome, ja que
    o modelo costuma reproduzir o nome do arquivo como aparece nas fontes)."""
    fn = _norm(Path(file_path).name.lower())
    for cited_fn, pages in cited_map.items():
        if cited_fn == fn or cited_fn in fn or fn in cited_fn:
            return pages
    return []


def _resolve_pages(retrieved: set, cited: list) -> list:
    """Hibrido validado: prioriza a pagina PRECISA citada pelo modelo, desde que
    confirmada no conjunto RECUPERADO (deterministico); senao, cai no conjunto
    recuperado. Se o conjunto recuperado nao veio (falha de rede), confia no
    citado. Garante que sempre haja pagina quando ha qualquer sinal."""
    if cited and retrieved:
        validated = [p for p in cited if p in retrieved]
        if validated:
            return validated
    elif cited and not retrieved:
        return list(cited)
    return sorted(retrieved)


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
        prompt_path = Path("src/IA/Prompt.md")
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

    def answer_question_stream(
        self,
        question: str,
        mode: str,
        conversation_history: list | None = None,
        history_turns: int = 5,
        available_docs: list | None = None,
    ) -> Tuple[Generator[Tuple[str, str], None, None], list, list]:
        """
        Retorna um gerador (para os chunks de resposta e pensamentos), uma lista vazia de search_results
        (para manter a tipagem unificada se necessário), e uma lista formatada das sources_lines originais.

        `conversation_history` é uma lista de dicts {"role", "content"} com os turnos anteriores da
        conversa, repassada ao LightRAG para manter o contexto. `history_turns` limita quantos turnos
        o LightRAG considera. `available_docs` alimenta {{LISTA_MANUAIS}} no prompt (nomes reais do bucket).
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

        # O timeout evita congelamentos indefinidos. 60s em geral é suficiente para a resposta chegar.
        # Caso GraphRAG demore, aumentamos.
        headers = {}
        if self.config.lightrag_api_key:
            headers["X-API-Key"] = self.config.lightrag_api_key
        resp = requests.post(f"{self.config.lightrag_api_url}/query/stream", json=payload, stream=True, timeout=120, headers=headers)
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
                        in_thought = True
                        chunk = chunk.replace("<think>", "")

                    if "</think>" in chunk:
                        parts = chunk.split("</think>")
                        if parts[0] or in_thought:
                            yield ("thought", parts[0])
                        in_thought = False
                        if len(parts) > 1 and parts[1]:
                            yield from feed_answer(parts[1])
                        continue

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
            cited_map = _parse_cited_pages(seen_text)
            # Reconhece o marcador de citacao "> Fonte:" mesmo quando o modelo foge do
            # formato com colchetes (ex.: "> Fonte: *arquivo*, pag N" em italico) — assim
            # uma resposta FUNDAMENTADA nunca fica sem fontes no painel por desvio de formato.
            answer_cited = bool(cited_map) or bool(re.search(r"(?im)>\s*fonte\b", seen_text))
            if answer_cited and collected_refs:
                # Uma unica chamada only_need_context devolve os chunks finais (pos-rerank):
                # deles extraimos a PAGINA (rodape, deterministico) e RE-PONTUAMOS a
                # relevancia no reranker (o LightRAG nao expoe o score). O score do chunk
                # propaga para as paginas que ele contem (max por pagina) -> relevancia %.
                chunks = self._fetch_context_chunks(payload, headers)
                page_map: dict = {}
                for ref_id, content in chunks:
                    page_map.setdefault(ref_id, []).extend(_footer_pages(content))
                scores = self._rerank_scores(payload.get("query", ""), [c for _, c in chunks])
                page_score: dict = {}
                for (ref_id, content), s in zip(chunks, scores):
                    for p in _footer_pages(content):
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
                        source_lines.append(_format_source_line_scored(file_path, p, page_score.get(p)))
                # Arquivo sem nenhuma pagina resolvida: lista so o nome (1x), e apenas se
                # ele ainda nao apareceu com pagina.
                for file_path in dict.fromkeys(no_page):
                    if file_path not in files_with_page:
                        source_lines.append(f"- {file_path}")

        # O retorno é o gerador em si e uma list de source_lines (sendo popularizada pelo gerador por reflexão)
        return stream_generator(), [], source_lines

    def answer_question(
        self,
        question: str,
        mode: str,
        conversation_history: list | None = None,
        history_turns: int = 5,
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
        )
        parts = [content for kind, content in gen if kind == "answer"]
        return "".join(parts).strip(), source_lines

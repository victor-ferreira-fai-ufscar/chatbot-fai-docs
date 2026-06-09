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

class LightRagService:
    def __init__(self, config: AppConfig):
        self.config = config

    def _build_user_prompt(self) -> str:
        prompt_path = Path("src/IA/Prompt.md")
        if prompt_path.exists():
            base_prompt = prompt_path.read_text(encoding="utf-8").strip()
            date_str, time_str = get_current_date_time_pt_br()
            
            if self.config.docs_dir.exists():
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

    def answer_question_stream(
        self,
        question: str,
        mode: str,
        conversation_history: list | None = None,
        history_turns: int = 5,
    ) -> Tuple[Generator[Tuple[str, str], None, None], list, list]:
        """
        Retorna um gerador (para os chunks de resposta e pensamentos), uma lista vazia de search_results
        (para manter a tipagem unificada se necessário), e uma lista formatada das sources_lines originais.

        `conversation_history` é uma lista de dicts {"role", "content"} com os turnos anteriores da
        conversa, repassada ao LightRAG para manter o contexto. `history_turns` limita quantos turnos
        o LightRAG considera.
        """
        user_prompt = self._build_user_prompt()

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
        resp = requests.post(f"{self.config.lightrag_api_url}/query/stream", json=payload, stream=True, timeout=120)
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
                            source_lines.append(f"- {file_path} (Ref ID: {ref.get('reference_id')})")

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

        # O retorno é o gerador em si e uma list de source_lines (sendo popularizada pelo gerador por reflexão)
        return stream_generator(), [], source_lines

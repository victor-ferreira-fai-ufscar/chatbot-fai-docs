import json
import requests
from pathlib import Path
from typing import Generator, Tuple, Any

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

    def answer_question_stream(self, question: str, mode: str) -> Tuple[Generator[Tuple[str, str], None, None], list, list]:
        """
        Retorna um gerador (para os chunks de resposta e pensamentos), uma lista vazia de search_results 
        (para manter a tipagem unificada se necessário), e uma lista formatada das sources_lines originais.
        """
        user_prompt = self._build_user_prompt()
        
        payload = {
            "query": question,
            "mode": mode,
            "stream": True,
            "user_prompt": user_prompt
        }

        # O timeout evita congelamentos indefinidos. 60s em geral é suficiente para a resposta chegar.
        # Caso GraphRAG demore, aumentamos.
        resp = requests.post(f"{self.config.lightrag_api_url}/query/stream", json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        source_lines = []
        
        def stream_generator():
            in_thought = False
            for line in resp.iter_lines():
                if not line:
                    continue
                    
                data = json.loads(line)
                
                # Coleta as referencias da busca do grafo
                if "references" in data:
                    refs = data["references"]
                    for ref in refs:
                        if ref.get('file_path'):
                            source_lines.append(f"- {ref.get('file_path')} (Ref ID: {ref.get('reference_id')})")
                
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
                            yield ("answer", parts[1])
                        continue
                    
                    if in_thought:
                        yield ("thought", chunk)
                    else:
                        yield ("answer", chunk)
                        
                if "error" in data:
                    yield ("answer", f"\nErro: {data['error']}")

        # O retorno é o gerador em si e uma list de source_lines (sendo popularizada pelo gerador por reflexão)
        return stream_generator(), [], source_lines

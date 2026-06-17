import json

from openai import OpenAI


def _delta_reasoning(delta):
    """Extrai o texto de raciocinio de um delta de streaming (varia por modelo)."""
    reasoning = getattr(delta, "reasoning_content", None)
    if not reasoning:
        for alt in ("reasoning", "thought", "thinking"):
            reasoning = getattr(delta, alt, None)
            if reasoning:
                break
    if not reasoning and getattr(delta, "model_extra", None):
        reasoning = (
            delta.model_extra.get("reasoning_content")
            or delta.model_extra.get("reasoning")
            or delta.model_extra.get("thought")
        )
    return reasoning


class OllamaModel:
    def __init__(self, base_url: str = "http://localhost:11434/v1", model_name: str = "llama3.2:3b"):
        self.model_name = model_name
        # Ollama emula a API da OpenAI perfeitamente na rota /v1
        self.client = OpenAI(api_key="ollama", base_url=base_url)

    def generate(self, system_prompt: str, user_prompt: str, history: list[dict]):
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_prompt}]
        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0.2,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True}
        )
        for chunk in response:
            # Capture usage if available (usually in the last chunk)
            if hasattr(chunk, "usage") and chunk.usage is not None:
                yield ("usage", chunk.usage.completion_tokens)
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            
            # Capture Thinking (Chain of Thought)
            # Ollama usually uses 'reasoning_content' for DeepSeek-R1,
            # but we'll check for several variants to be more aggressive.
            reasoning = getattr(delta, "reasoning_content", None)
            
            if not reasoning:
                for alt in ["reasoning", "thought", "thinking"]:
                    reasoning = getattr(delta, alt, None)
                    if reasoning: break
            
            # Fallback for model_extra fields (OpenAI SDK v1.x stores unknown fields here)
            if not reasoning and hasattr(delta, "model_extra") and delta.model_extra:
                reasoning = (
                    delta.model_extra.get("reasoning_content") or 
                    delta.model_extra.get("reasoning") or 
                    delta.model_extra.get("thought")
                )

            if reasoning:
                yield ("thought", reasoning)
                
            # Capture Final Answer
            if delta.content is not None:
                yield ("answer", delta.content)

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        """Um turno do laco de agente. Faz streaming e, ao final, sinaliza se o
        modelo pediu ferramentas. Mantem o protocolo de tuplas do generate():
          ("thought", txt) | ("answer", txt) | ("tool_calls", calls) | ("usage", int)

        Os argumentos das tool_calls chegam FRAGMENTADOS no stream: acumulamos por
        index e so fazemos json.loads no final (erro classico de tool calling)."""
        params = {
            "model": self.model_name,
            "temperature": 0.2,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        response = self.client.chat.completions.create(**params)

        tool_acc: dict[int, dict] = {}   # index -> {id, name, args}
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage is not None:
                yield ("usage", chunk.usage.completion_tokens)
                continue
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            reasoning = _delta_reasoning(delta)
            if reasoning:
                yield ("thought", reasoning)
            if getattr(delta, "content", None):
                yield ("answer", delta.content)

            for tc in (getattr(delta, "tool_calls", None) or []):
                idx = tc.index if getattr(tc, "index", None) is not None else 0
                acc = tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                if getattr(tc, "id", None):
                    acc["id"] += tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        acc["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        acc["args"] += fn.arguments

        if tool_acc:
            calls = []
            for acc in tool_acc.values():
                try:
                    parsed = json.loads(acc["args"] or "{}")
                except json.JSONDecodeError:
                    parsed = {}
                calls.append({"id": acc["id"], "name": acc["name"], "arguments": parsed})
            yield ("tool_calls", calls)

import json

from openai import OpenAI


class OpenAIModel:
    def __init__(self, api_key: str, base_url: str | None = None, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
            # Capture usage if available
            if hasattr(chunk, "usage") and chunk.usage is not None:
                yield ("usage", chunk.usage.completion_tokens)
                continue

            if not chunk.choices:
                continue

            if chunk.choices[0].delta.content is not None:
                yield ("answer", chunk.choices[0].delta.content)

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        """Turno do laco de agente (mesma ideia do OllamaModel.chat). Acumula as
        tool_calls fragmentadas por index e faz json.loads so no final."""
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

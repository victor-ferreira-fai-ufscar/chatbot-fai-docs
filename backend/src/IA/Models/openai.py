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

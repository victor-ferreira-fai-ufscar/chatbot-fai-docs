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
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

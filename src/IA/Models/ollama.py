from openai import OpenAI

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
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

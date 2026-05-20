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

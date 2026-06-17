from google import genai
from google.genai import types

class GeminiModel:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str, history: list[dict]):
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )
            
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])
        )
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        )
        
        response = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config=config,
        )
        for chunk in response:
            if chunk.text:
                yield ("answer", chunk.text)
            
            # Capture usage if available (usually in the last chunk)
            if chunk.usage_metadata:
                yield ("usage", chunk.usage_metadata.candidates_token_count)

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        """O agente (Fase 8) usa o laco de tool calling OpenAI-compatible
        (Ollama/OpenAI). O GeminiModel usa outro SDK e nao participa desse laco."""
        raise NotImplementedError(
            "GeminiModel nao suporta o laco de tool calling do agente; use Ollama/OpenAI."
        )

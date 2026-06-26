# Micro-servico que injeta reasoning "high" no gpt-oss: fica entre o LightRAG e o
# Ollama, adiciona o campo `think:"high"` (que o binding do LightRAG nao envia) na ida
# e remove o `thinking` da resposta na volta. Imagem minima, roda em CPU.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Porta 11435: o LightRAG aponta LLM_BINDING_HOST aqui; o shim encaminha ao Ollama :11434.
EXPOSE 11435
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "11435"]

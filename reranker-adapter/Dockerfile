# Micro-servico que traduz o protocolo de rerank Cohere (que o LightRAG fala) para
# o protocolo do TEI (que roda o modelo na GPU). Imagem minima; roda em CPU.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Porta 7997: a MESMA que o LightRAG ja aponta (RERANK_BINDING_HOST), entao a troca
# do reranker CPU->GPU fica transparente para o LightRAG.
EXPOSE 7997
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7997"]

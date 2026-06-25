# Como trocar o modelo de IA (LLM local)

Guia para trocar o modelo de linguagem usado pelo chatbot. O sistema roda 100%
local via **Ollama** (serviço do host, GPU compartilhada).

## Onde cada modelo é configurado

| Função | Variável | Arquivo |
|---|---|---|
| **Resposta do RAG** (geração principal) | `LLM_MODEL` | `docker-compose.yml` → serviço `lightrag` |
| **Tarefas auxiliares** (título da conversa, resolvedor de download) | `OLLAMA_MODEL` | `.env` |
| **Embeddings** (indexação/busca) | `EMBEDDING_MODEL` + `EMBEDDING_DIM` | `docker-compose.yml` → serviço `lightrag` |
| **Transcrição de áudio** (Whisper) | `WHISPER_MODEL` | `.env` (ver Fase 4 do roadmap) |

> Estado atual de referência: resposta e auxiliares em `gemma4:31b`, embeddings
> em `bge-m3:latest` (dim 1024). Sem OpenAI/Gemini — tudo local.

---

## Trocar o modelo de RESPOSTA (caso comum)

### Passo 1 — Baixar o modelo no Ollama (no host)
O Ollama **não** baixa sozinho; se o modelo não existir, o LightRAG dá erro.
```bash
ollama pull <novo-modelo>     # ex.: ollama pull gemma4:26b
ollama list                   # confirmar que aparece na lista
```

### Passo 2 — Apontar o LightRAG para o novo modelo
No `docker-compose.yml`, serviço `lightrag`:
```yaml
    LLM_MODEL: <novo-modelo>
```
Se o modelo novo tiver janela de contexto/VRAM diferente, revise junto:
`OLLAMA_LLM_NUM_CTX`, `MAX_TOTAL_TOKENS`, `MAX_ENTITY_TOKENS`, `MAX_RELATION_TOKENS`.

### Passo 3 (recomendado) — Alinhar as tarefas auxiliares
No `.env`, para usar o mesmo modelo nas tarefas auxiliares:
```
OLLAMA_MODEL=<novo-modelo>
```

### Passo 4 — Recriar os containers afetados
Só muda variável de ambiente → **não precisa rebuild**, só recriar:
```bash
docker compose up -d lightrag    # pega o novo LLM_MODEL
docker compose up -d backend     # somente se mexeu no .env (OLLAMA_MODEL)
```

### Passo 5 — Validar
```bash
docker logs -f fai_lightrag      # acompanhar a inicialização/uso
nvidia-smi                       # conferir VRAM ocupada
```
Depois, mande uma pergunta no chat e confira a resposta.

---

## Avisos importantes

1. **VRAM compartilhada (32 GB):** o LLM de resposta, o Whisper (medium, ~5 GB) e
   os embeddings dividem a mesma GPU. Um LLM muito maior pode não caber junto com
   o Whisper carregado — acompanhe com `nvidia-smi`. Modelos menores (ex.: 14B,
   `gemma4:26b`) deixam mais folga.
2. **Trocar embeddings é disruptivo:** mudar `EMBEDDING_MODEL`/`EMBEDDING_DIM`
   **invalida o índice atual** e exige **re-indexar todos os documentos**. Trocar
   apenas o `LLM_MODEL` (resposta) é barato e reversível; trocar embeddings, não.
3. **Pull antes de apontar:** sempre baixe o modelo no Ollama **antes** de mudar a
   config e recriar os containers, para evitar erro de "model not found".

---

## Reverter

Basta voltar o valor anterior (`LLM_MODEL` / `OLLAMA_MODEL`) e recriar os
containers. Como é só variável de ambiente, a reversão é imediata e sem rebuild.

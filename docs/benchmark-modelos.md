# Benchmark de modelos LLM (chatbot FAI)

Comparativo de modelos locais (Ollama) rodando a **mesma bateria de 9 perguntas**
pela rota real do chatbot (`POST /api/v1/chat/stream` → LightRAG → Ollama).

- **Data:** 15/06/2026
- **Hardware:** NVIDIA RTX 5090 (32 GB), via container com `gpus: all`.
- **Pipeline:** LightRAG (modo híbrido) + embeddings `bge-m3`. Cada pergunta como
  conversa nova (sem histórico).
- **Raciocínio (thinking):** **desligado** nos modelos Qwen3 (variante `-nothink`
  via Modelfile). `deepseek-r1` não permite desligar (sempre raciocina).

## Metodologia

Para cada modelo: aponta `LLM_MODEL`/`OLLAMA_MODEL` → recria `lightrag`+`backend`
→ *warmup* (carrega na VRAM) → roda as 9 perguntas medindo no cliente e amostrando
`nvidia-smi` (a cada 250 ms) durante a janela de geração.

**Limitações conhecidas das métricas (via RAG):**
- **TTFT** inclui a etapa de extração de palavras-chave do LightRAG (uma chamada
  extra ao LLM) + a busca no grafo — ou seja, é o TTFT **real do chatbot**, não a
  latência crua do modelo.
- **Tokens/tok-s** são **estimados** (caracteres ÷ 4) — o contador exato do Ollama
  não é exposto pela via RAG (múltiplas chamadas internas por pergunta).
- **Ctx (tokens de entrada)** não é extraível pela via RAG.
- **VRAM** é o total da GPU durante a geração (modelo + embeddings + KV cache).

## Resultado (ordenado por velocidade de geração)

| Modelo | OK | TTFT (s) | Resp (s) | Tok~ | Geração (tok/s) | VRAM (GB) | GPU % | Pot (W) | Temp (°C) | Efic (tok/s/W) |
|---|---|---|---|---|---|---|---|---|---|---|
| **qwen3:8b** | 9/9 | 5,5 | 8,3 | 350 | **38,9** | 11,6 | 78 | 482 | 65 | **0,080** |
| qwen3:14b | 9/9 | 9,2 | 12,6 | 285 | 21,7 | 15,7 | 87 | 515 | 76 | 0,042 |
| gemma4:26b | 7/9 | 26,1 | 28,4 | 283 | 10,3 | 20,2 | 78 | 389 | 70 | 0,026 |
| qwen2.5-coder:32b | 9/9 | 18,1 | 23,4 | 237 | 9,9 | 28,7 | 91 | 534 | 78 | 0,019 |
| qwen3:32b | 9/9 | 18,4 | 25,0 | 240 | 8,9 | 29,1 | 91 | 535 | 79 | 0,016 |
| gemma4:12b | 8/9 | 30,0 | 32,5 | 264 | 8,3 | 11,1 | 79 | 434 | 69 | 0,019 |
| deepseek-r1:32b | 7/9 | 28,9 | 34,4 | 240 | 7,0 | 28,7 | 93 | 551 | 80 | 0,013 |
| gemma4:31b | 9/9 | 30,9 | 35,8 | 247 | 6,9 | 24,9 | 89 | 524 | 78 | 0,013 |

> ⏸ **Pendentes (para rodar depois):** `llama3.3:70b` e `llama4` — não cabem nos
> 32 GB de VRAM (offload para CPU → bem mais lentos). Serão medidos à parte.

## Falhas observadas

| Modelo | Perguntas com erro | Causa |
|---|---|---|
| gemma4:26b | Q1, Q5 | Timeout de 120s — **loop de repetição degenerada** do modelo |
| gemma4:12b | Q4 | Resposta vazia |
| deepseek-r1:32b | Q4, Q6 | Pensou, mas não emitiu resposta final (vazia) |

## Leituras

1. **`qwen3:8b` lidera** em velocidade **e** eficiência (≈5× mais eficiente que os
   32b), com a menor VRAM e 9/9 respostas — forte candidato a modelo padrão.
   `qwen3:14b` é o segundo melhor equilíbrio.
2. **Família `gemma4` decepcionou:** lenta **e** instável (o `12b` ficou mais lento
   que os 32b da Qwen; o `26b` deu timeout por repetição). Indício de
   build/quantização problemática nesta instalação.
3. **`deepseek-r1:32b`** é o mais lento (raciocínio sempre ligado) e teve respostas
   vazias — pouco prático para este uso.
4. **Grounding:** quase todos citaram 1 fonte por resposta. A **qualidade textual**
   das respostas deve ser avaliada manualmente (não medida aqui).

> Nota: estes números refletem **velocidade/custo**, não **qualidade da resposta**.
> A escolha final do modelo deve pesar também a precisão/completude das respostas.

# Chatbot FAI Docs

Sistema de RAG Avançado (Retrieval-Augmented Generation) operando localmente e integrando base de conhecimento de PDFs com PostgreSQL (Supabase) via arquitetura *Two-Stage* (Busca Vetorial + Re-ranking).

## 🧩 Visão simples da arquitetura

Em termos práticos, o fluxo otimizado é:
`PDFs -> Markdown (PyMuPDF) -> Chunking Geométrico -> HuggingFace Embeddings -> pgvector (Busca Primária) -> Cross-Encoder (Juiz Re-ranker) -> LLM Rápido (Streaming) -> Usuário`

1. Ler os PDFs extraindo sua formatação inteligente em **Markdown** (`pymupdf4llm`).
2. Quebrar o texto respeitando fluxogramas e listas.
3. Gerar embeddings pela CPU nativa sem gastar VRAM.
4. Recuperar os 20 resultados mais relevantes no Postgres.
5. Recalcular a relevância lógica (0 a 10) dos 20 por meio do **Re-ranking**.
6. Enviar apenas os 5 textos perfeitos no *Contexto Limpo* para a IA formatar a resposta na tela letra a letra.

## 📦 Funcionalidade das Dependências Principais

- **`pymupdf4llm`**: Transforma os PDFs brutos em strings de Markdown perfeitamente delimitadas (preserva Tabelas, Listas e intersecções). Acabita com textos colados.
- **`sentence-transformers`**: Motor duplo. Cria os Embeddings (transforma texto em matemática) e, na segunda fase, instancia o `CrossEncoder` que opera a nossa mágica chamada Re-ranking cruzado na recuperação final.
- **`pgvector` (PostgreSQL)**: Recebe os vetores. Permite buscarmos instantaneamente por Semântica Lógica (Distância de Cosseno) diretamente por linguagem SQL.
- **`openai` & `google-genai`**: Bibliotecas responsáveis que atuam como clientes de conversa. Suportam localmente o `Ollama` ou na nuvem o Gemini/GPT-4.
- **`streamlit`**: Empacota o backend como um Chat Dinâmico bonito Web para uso do colaborador.

## O que cada parte faz

- `app.py`: Interface Streamlit, lida com UI e Streaming (`st.write_stream`).
- `config.py`: Gestão limpa das variáveis de ambiente (`CHUNK_SIZE`, Modelos Rerankers).
- `pdfs.py`: Leitura rica de PDFs para Markdown e conversão pro banco.
- `embeddings.py`: Gera os cálculos vetoriais e carrega o Juiz Local Reranker (`CrossEncoder`).
- `vector_store.py`: Gravação e busca de SQL Rápido no Supabase.
- `service.py`: Maestro! Orquestra o tempo da pesquisa e filtra (Rerank) os achados.

## Como rodar

### 1. Configurar ambiente (`.env`)

Preencha a chave dos bancos e os parâmetros da Engine:

```env
DATABASE_URL=postgresql://postgres:<SUA-SENHA>@db.<PROJECT-REF>.supabase.co:5432/postgres

# Otimizado para performance e busca profunda:
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# Motores Locais Open Source:
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

### 2. Instalar dependências

```bash
uv sync
```

### 3. Rodar a interface

```bash
uv run streamlit run app.py
```

Na primeira execução, o app processará os blocos demoradamente e baixará pequenos pedaços do HuggingFace. A partir da segunda inicialização o cache assume, a ferramenta voa em fração de segundos.

## Modelos Open Source Recomendados (Ollama)

O APP não requer internet para conversar, utilize uma destas engrenagens:
```env
# Exemplo 1: Lama (Facebook)
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2:3b

# Exemplo 2: Gemma (Google Local)
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=gemma3:1b
```

## Próximos passos e Integrações Futuras

1. **OCR Avançado (Fallback Híbrido)**: Adaptar a estrutura Google Cloud Vision para resgatar informações presas em *Scans* onde a extração da CPU resulta vaza ou corrompida.
2. Adicionar filtros rígidos de busca baseados em Data/Versão ou Títulos Específicos do Tópico do PDF dentro da Query Postgres.
3. Expandir Chatbot RAG em Omnichannel (FastAPI), separando do Streamlit para deploy em aplicativos mobile, Whatsapp e sistemas acadêmicos corporativos.

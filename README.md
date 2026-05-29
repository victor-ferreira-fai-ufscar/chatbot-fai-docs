# Chatbot FAI Docs

Sistema de RAG Avançado (Retrieval-Augmented Generation) operando localmente e integrando base de conhecimento de PDFs com PostgreSQL (Supabase) via arquitetura *Two-Stage* (Busca Vetorial + Re-ranking). O projeto evoluiu para uma arquitetura Full-Stack moderna.

## 🏗️ Arquitetura do Sistema

O projeto adota uma arquitetura cliente-servidor robusta:

- **Frontend (Next.js):** Interface de chat moderna, responsiva e com suporte completo a Markdown, gerenciamento de estado de sessões e histórico de conversas.
- **Backend (FastAPI):** API REST em Python focada em alta performance, gerenciamento do RAG, streaming de respostas de LLMs (Google GenAI / OpenAI / Ollama) e persistência de dados.
- **Banco de Dados (PostgreSQL + Supabase):** Armazenamento seguro de embeddings (via `pgvector`) e relacionamento estruturado de histórico de chats usando chaves estrangeiras lógicas (`SERIAL`).

## 🧩 Modos de Operação RAG (Dual-Mode)

O backend possui suporte a dois motores de recuperação de informação, que podem ser alternados:

**1. Supabase RAG (Padrão - Busca Vetorial Clássica)**
Fluxo prático: `PDFs -> Markdown (PyMuPDF) -> Chunking Geométrico -> Embeddings -> pgvector -> Cross-Encoder -> Streaming LLM`

**2. LightRAG (Grafo de Conhecimento)**
Utiliza um motor baseado em grafos focados em relacionamentos complexos, conectando-se a um servidor `LightRAG` operando paralelamente.

1. Ler os PDFs extraindo sua formatação inteligente em **Markdown** (`pymupdf4llm`).
2. Quebrar o texto respeitando fluxogramas e listas.
3. Gerar embeddings pela CPU nativa sem gastar VRAM.
4. Recuperar os resultados mais relevantes no Postgres.
5. Recalcular a relevância lógica (0 a 10) por meio do **Re-ranking**.
6. Enviar o *Contexto Limpo* via streaming para o Frontend renderizar.

## 📦 Tecnologias e Dependências Principais

### Backend (`/backend`)

- **FastAPI:** Framework web principal.
- **`pymupdf4llm`**: Transforma PDFs brutos em Markdown perfeitamente delimitado.
- **`sentence-transformers`**: Cria Embeddings e instancia o `CrossEncoder` para Re-ranking.
- **`pgvector` (PostgreSQL)**: Recebe vetores para busca instantânea por similaridade de cosseno.
- **`LightRAG`**: Integração com servidor dedicado de Grafos de Conhecimento para suporte a Dual-Mode RAG.
- **`google-genai` / `openai`**: Clientes de LLM (suportando Gemini, GPT-4 ou Ollama local).

### Frontend (`/frontend`)

- **Next.js & React:** Componentização e renderização do Chat.
- **TailwindCSS:** Estilização utilitária e temas escuros fluidos.
- **Markdown Parsers:** Renderização profissional de respostas da IA, incluindo tabelas e blocos de código.

## 🚀 Como Rodar o Projeto Localmente

O projeto exige que tanto o Backend quanto o Frontend estejam em execução.

### 1. Configuração do Backend (`/backend`)

Crie o arquivo `backend/.env` (baseado no `.env.example`):

```env
DATABASE_URL=postgresql://postgres:<SUA-SENHA>@db.<PROJECT-REF>.supabase.co:5432/postgres

# Otimizado para performance e busca profunda:
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# Motores Locais Open Source:
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# Conexão com o motor LightRAG (opcional se não usar a funcionalidade de Grafo)
LIGHTRAG_API_URL=http://localhost:9621

# API Key do LLM (se usar nuvem)
GEMINI_API_KEY=sua_chave_aqui
```

Instale as dependências e inicie a API:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

> *Nota:* O serviço estará rodando em `http://localhost:8000`. A documentação da API fica disponível em `/docs`.

### 2. Configuração do Frontend (`/frontend`)

Crie o arquivo `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Instale as dependências e inicie o servidor Next.js:

```bash
cd frontend
npm install
npm run dev
```

> *Nota:* A interface web estará disponível em `http://localhost:3000`.

## 🤖 Modelos Open Source (Ollama)

O backend é projetado para operar 100% offline via Ollama. Exemplo de uso:

```env
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2:3b
```

## 🛤️ Próximos Passos e Integrações Futuras

1. **OCR Avançado (Fallback Híbrido)**: Adaptar a estrutura Google Cloud Vision para resgatar informações em *Scans* onde a extração direta da CPU falha.
2. **Autenticação de Usuários**: Expandir o schema SERIAL para atrelar conversas a usuários logados de forma segura.
3. **Dockerização Completa**: Atualizar o `docker-compose.yml` para englobar frontend, backend e um possível banco de dados vetorial local de forma unificada.

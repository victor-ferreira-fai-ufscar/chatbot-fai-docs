# Supabase

Guia simples para conectar este projeto ao Supabase.

## Projeto

- Project ref: `weicrmqpvrnqngnhecwm`
- URL do projeto: `https://weicrmqpvrnqngnhecwm.supabase.co`

## O que este projeto usa do Supabase

Neste momento, usamos o Supabase principalmente como:

- Postgres
- `pgvector`

Ou seja, a aplicação conversa com o banco Postgres do Supabase para salvar e buscar embeddings.

A chave publishable do Supabase não é necessária para o fluxo atual do backend do RAG.

## String de conexão

Use a connection string Postgres do projeto neste formato:

```env
DATABASE_URL=postgresql://postgres:<SUA-SENHA>@db.weicrmqpvrnqngnhecwm.supabase.co:5432/postgres
```

## Preparação inicial

### 1. Login no CLI

```bash
supabase login
```

### 2. Inicializar o projeto localmente

```bash
supabase init
```

### 3. Vincular ao projeto remoto

```bash
supabase link --project-ref weicrmqpvrnqngnhecwm
```

## Verificações importantes no painel do Supabase

Antes de rodar o app, confirme:

1. o Postgres do projeto está ativo
2. a extensão `vector` está habilitada
3. você tem a senha correta do banco para montar a `DATABASE_URL`

## O que o app faz automaticamente

Na primeira execução, o app tenta:

1. conectar ao Postgres
2. garantir a extensão `vector`
3. criar a tabela `document_chunks` se ela não existir
4. gerar embeddings dos PDFs
5. salvar os chunks e embeddings no banco

## Variáveis de ambiente mínimas

Exemplo:

```env
DATABASE_URL=postgresql://postgres:<SUA-SENHA>@db.weicrmqpvrnqngnhecwm.supabase.co:5432/postgres
OPENAI_API_KEY=<SUA_CHAVE>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
```

## Execução

```bash
uv sync
uv run streamlit run app.py
```

## Resumo para o time

Se alguém do time perguntar "como isso funciona?", a resposta curta é:

1. os PDFs são lidos localmente
2. os textos viram embeddings
3. os embeddings ficam no Postgres do Supabase
4. a busca semântica acontece no `pgvector`
5. os trechos encontrados são enviados ao modelo para gerar a resposta

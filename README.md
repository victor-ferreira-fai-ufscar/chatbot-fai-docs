# Chatbot FAI Docs

Protótipo simples de chatbot para consultar os PDFs do projeto usando embeddings e Supabase.

## Visão simples da arquitetura

A ideia do projeto agora é esta:

1. ler os PDFs da pasta `docs/sil`
2. quebrar o texto em trechos menores
3. gerar embeddings desses trechos
4. salvar os embeddings no Postgres do Supabase com `pgvector`
5. quando o usuário perguntar algo, buscar os trechos mais próximos
6. enviar a pergunta e o contexto para o modelo de resposta

Em termos práticos, o fluxo é:

`PDFs -> embeddings -> Supabase pgvector -> contexto -> LLM -> resposta`

## Por que Supabase

Escolhemos Supabase porque ele simplifica bastante o entendimento do time:

- o banco vetorial fica em Postgres, que é familiar
- `pgvector` resolve a busca semântica sem adicionar outra ferramenta separada
- a migração futura continua simples, porque a aplicação fala com Postgres
- o projeto continua com uma arquitetura pequena e legível

## Estrutura do código

```text
.
├── app.py
├── docs/
│   ├── SUPABASE.md
│   └── sil/
├── pyproject.toml
└── src/
    └── chatbot_fai_docs/
        ├── config.py
        ├── embeddings.py
        ├── llm.py
        ├── models.py
        ├── pdfs.py
        ├── service.py
        └── vector_store.py
```

## O que cada parte faz

- `app.py`: interface Streamlit
- `config.py`: leitura das variáveis de ambiente
- `pdfs.py`: leitura dos PDFs e criação dos chunks
- `embeddings.py`: geração dos embeddings
- `vector_store.py`: gravação e busca vetorial no Postgres/Supabase
- `service.py`: orquestra o fluxo do RAG
- `llm.py`: monta a chamada para o modelo de resposta

## Como rodar

### 1. Configurar ambiente

```bash
cp .env.example .env
```

Preencha pelo menos:

```env
DATABASE_URL=postgresql://postgres:<SUA-SENHA>@db.<PROJECT-REF>.supabase.co:5432/postgres
OPENAI_API_KEY=<SUA_CHAVE>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
```

### 2. Instalar dependências

```bash
uv sync
```

### 3. Rodar a interface

```bash
uv run streamlit run app.py
```

Na primeira execução, o app:

- lê os PDFs
- gera os embeddings
- cria a tabela se necessário
- sincroniza os chunks no banco

## Supabase

O guia objetivo de configuração do projeto Supabase está em [docs/SUPABASE.md](./docs/SUPABASE.md).

## Modelos de resposta

Hoje o app já funciona com provedores compatíveis com a API da OpenAI.

Exemplos:

### OpenAI

```env
OPENAI_API_KEY=<SUA_CHAVE>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

### Ollama

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2:3b
```

## Estado atual do protótipo

- os 2 PDFs atuais já foram processados localmente durante a validação
- a arquitetura foi reduzida para um único caminho principal com Supabase/Postgres
- o objetivo agora é facilitar entendimento e continuidade pelo time

## Próximos passos naturais

1. Adicionar um comando separado de ingestão para não reprocessar tudo a cada reload do Streamlit.
2. Criar filtros por documento e página.
3. Adicionar OCR caso apareçam PDFs escaneados.
4. Evoluir a interface depois que o comportamento do RAG estiver estável.

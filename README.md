# Chatbot FAI Docs

Protótipo simples para testar localmente um chatbot que consulta os PDFs do projeto.

Nesta primeira versão, a solução faz o seguinte:

- lê os PDFs da pasta `docs/sil`
- extrai o texto e divide em trechos
- recupera os trechos mais parecidos com a pergunta usando TF-IDF
- envia a pergunta com esse contexto para um modelo compatível com a API da OpenAI
- exibe a resposta em uma interface local com Streamlit

Isso permite começar com algo pequeno e funcional, sem depender de uma arquitetura mais pesada agora.

## Documentos atuais

1. [2026-02-23 - EMBRAPII MANUAL DE PROCEDIMENTOS INTERNOS.pdf](./docs/sil/2026-02-23%20-%20EMBRAPII%20MANUAL%20DE%20PROCEDIMENTOS%20INTERNOS.pdf)
2. [Manual do Coordenador esboço 6.pdf](./docs/sil/Manual%20do%20Coordenador%20esboço%206.pdf)

## Stack

- Python
- [uv](https://github.com/astral-sh/uv)
- Streamlit
- pypdf
- scikit-learn
- OpenAI SDK

## Como rodar localmente

### 1. Instalar o `uv`

Consulte a documentação oficial: [astral-sh/uv](https://github.com/astral-sh/uv)

### 2. Criar o ambiente e instalar dependências

```bash
uv sync
```

### 3. Configurar variáveis de ambiente

Crie um arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

### 4. Executar o app

```bash
uv run streamlit run app.py
```

O app abrirá localmente no navegador.

## Modelos suportados neste MVP

### OpenAI API

Exemplo de `.env`:

```env
OPENAI_API_KEY=<SUA_CHAVE>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
```

### Ollama local

Se quiser rodar com modelo local usando Ollama, a interface já aceita base URL compatível com OpenAI.

Exemplo de `.env`:

```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2:3b
```

Depois, na barra lateral do app, você também pode ajustar o modelo manualmente.

## Estrutura atual

```text
.
├── app.py
├── docs/
│   └── sil/
├── pyproject.toml
└── src/
    └── chatbot_fai_docs/
        └── rag.py
```

## Limitações desta versão

- a recuperação é simples, usando TF-IDF, então ainda não é um RAG mais robusto com embeddings
- a extração depende do texto disponível no PDF; PDFs com texto ruim ou imagem escaneada podem exigir OCR depois
- ainda não há persistência de conversa, autenticação ou publicação na web

## Próximos passos naturais

1. Trocar a busca TF-IDF por embeddings.
2. Adicionar OCR para PDFs escaneados.
3. Permitir upload de novos documentos pela interface.
4. Evoluir depois para integração com a área de coordenadores.

## Contexto inicial do projeto

Links de referência:

- Área de Coordenadores: https://sistemas.fai.ufscar.br/Coordenadores/Projeto/Listar
- Repositório GitHub: https://github.com/victor-ferreira-fai-ufscar/chatbot-fai-docs
- Manuais/DOCS de exemplo (Sil): https://teams.microsoft.com/l/message/19:9fae0f1d72a74dca9d0a24fce056a7bd@thread.v2/1775481371366?context=%7B%22contextType%22%3A%22chat%22%7D

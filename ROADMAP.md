# 🚀 FAI Chatbot: Roadmap de Evolução

Este documento serve como o registro central de ideias, planos e futuras melhorias para o sistema de chatbot. Novas ideias devem ser adicionadas aqui para manter o alinhamento tecnológico e a visão de longo prazo.

## 🏆 Visão Geral

Transformar o chatbot atual em uma ferramenta institucional de alta performance, capaz de lidar com documentos complexos e oferecer uma experiência de usuário personalizada e persistente.

## 📅 Fases de Implementação

### 🔹 Fase 1: Autoconsciência e Contexto (Concluída ✅)

* Injeção dinâmica de data e hora no prompt.
* Reconhecimento automático da lista de manuais disponíveis no sistema.
* Suavização da ancoragem RAG para permitir respostas sobre o estado do sistema.

### 🔹 Fase 2: Visão e OCR Avançado (Google Vision API)

**Objetivo:** Superar as limitações do processamento de PDF convencional.

* **Fallback Híbrido:** Usar OCR gratuito (`pypdf`) por padrão e disparar a Google Vision apenas em páginas "cegas" (scans antigos ou imagens).
* **Leitura de Prints:** Indexar ilustrações e telas de sistemas que hoje são ignoradas.
* **Referência Detalhada:** [Ver plano técnico](docs/future_vision_api_plan.md)

### 🔹 Fase 3: Persistência e Histórico (Supabase) (Concluída ✅)

**Objetivo:** Permitir que o usuário retome conversas e gerencie múltiplos contextos.

* ✅ **Banco de Dados (Supabase self-hosted):** Persistência de mensagens e threads no Postgres do Supabase (conexão via pooler/Supavisor). Tabelas `chat_conversations` e `chat_messages` criadas automaticamente no startup.
* ✅ **Gestão de Threads:** Identificadores únicos por conversa (`conversation_id`).
* ✅ **Interface Lateral:** Barra lateral com histórico de chats (padrão ChatGPT).
* ✅ **Títulos Automáticos:** Geração de título curto pela LLM a partir da primeira pergunta.
* ✅ **Integração de Contexto RAG:** Histórico persistido enviado ao parâmetro `conversation_history` do LightRAG (últimos `HISTORY_TURNS` turnos) para manter o contexto entre mensagens.
* ✅ **Isolamento por Sessão (`user_id`):** Sem login ainda — cada sessão gera um `user_id` (guardado no `localStorage`) e vê apenas as próprias conversas.
* ✅ **Limpar Histórico:** Ação que apaga todas as conversas do usuário no backend (rota `DELETE /history/`).
* ✅ **Observabilidade:** Log no startup do backend indicando sucesso/falha da conexão com o Supabase (sem expor a senha).

### 🔹 Fase 4: Transcrição de Áudio (Speech-to-Text) - [ADIADA]

**Objetivo:** Permitir que usuários enviem perguntas por voz, facilitando o uso em dispositivos móveis.

* **Integração Local Whisper**: Implementado motor 100% local (`faster-whisper`), mas desativado temporariamente para priorizar a estabilidade do campo de texto original e UX minimalista.
* **Interface de Gravador**: Possibilidade de reativar o botão de microfone no futuro conforme demanda dos usuários.

### 🔹 Fase 5: Arquitetura RAG Dual (Supabase vs LightRAG)

**Objetivo:** Permitir a escolha dinâmica entre a abordagem atual via Supabase e a nova abordagem via Grafos do LightRAG para fins de comparação de performance e qualidade de resposta.

* **Integração LightRAG Backend**: Criação de um cliente/serviço para consumir a API local do LightRAG (que opera na porta `9621`).
* **Seletor na Interface**: Inserir um botão Toggle ou Select no painel lateral/header da interface do chatbot permitindo alternar facilmente entre o "RAG Tradicional (Supabase)" e o "GraphRAG (LightRAG)".
* **Roteamento e Comparativo**: Quando o usuário envia a mensagem, o sistema decide qual pipeline de RAG chamar baseado na opção selecionada, mantendo a experiência fluida.

### 🔹 Fase 6: Repositório de Documentos e Entrega ao Usuário (Supabase Storage) (Concluída ✅)

**Objetivo:** Armazenar no **Supabase Storage** (bucket privado) os documentos que a IA consulta e permitir que o usuário **receba o arquivo** sob demanda — tanto clicando na fonte citada quanto pedindo em linguagem natural — por meio de **URLs assinadas temporárias**.

**Princípios de Arquitetura:**
* **Gatilho = upload no LightRAG (não a pasta `docs/sil`):** o fluxo de ingestão passa a ser roteado pelo backend, que sobe o arquivo **simultaneamente** para o LightRAG (indexação) e para o bucket do Supabase (entrega). Assim, todo documento indexado fica disponível para download e os dois lados permanecem sincronizados.
* **Bucket privado + signed URL:** nenhum arquivo é público; o backend gera links assinados com validade curta no momento do pedido.

**Plano de Implementação:**

1. **Configuração do Bucket e `.env`**
   * Criar bucket privado (ex.: `manuais`) no Supabase Storage.
   * Novas variáveis: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (acesso admin ao Storage), `SUPABASE_BUCKET=manuais`, `SIGNED_URL_TTL=3600` (segundos).

2. **Serviço de Storage (backend)** — `storage_service.py`
   * Wrapper sobre a API REST do Storage do Supabase self-hosted (`/storage/v1/...`) usando a service role key: `upload(file)`, `create_signed_url(path, ttl)`, `list_objects()`, `exists(path)`.

3. **Endpoint de Upload Unificado** — `POST /documents/upload`
   * Recebe o arquivo, encaminha para o `POST /documents/upload` do LightRAG (indexação) **e** sobe os mesmos bytes para o bucket (chave = nome do arquivo sanitizado).
   * Retorna `track_id` (LightRAG) + confirmação de armazenamento. Idempotente: se o objeto já existe, atualiza/ignora.

4. **Mapeamento documento ↔ objeto**
   * Tabela `document_files` (filename, storage_path, uploaded_at, track_id) para resolver rapidamente a fonte citada → objeto no bucket. Alternativamente, listar o bucket sob demanda.

5. **Entrega via Signed URL** — `GET /documents/{filename}/download-url`
   * Valida que o arquivo existe no bucket, gera e retorna a URL assinada (TTL de `SIGNED_URL_TTL`).

6. **Frontend — Chips de fonte clicáveis**
   * Em `ChatWindow.tsx`, transformar os chips de "Fontes Pesquisadas" em botões que chamam o endpoint de signed URL e abrem/baixam o arquivo.

7. **Pedido em Linguagem Natural com Resolução por IA** — `document_resolver.py`
   * ✅ Pré-filtro leve em `chat.py` (verbo de envio + substantivo de documento **ou** pronome referencial como "esse/ele/anterior") evita chamadas desnecessárias de LLM em perguntas informativas.
   * ✅ Quando o pré-filtro dispara, um **resolvedor por IA** recebe o histórico da conversa + os documentos citados na última resposta + a lista de objetos do bucket e decide, em JSON estruturado: se é de fato um pedido de download, **qual** documento (resolvendo referências de contexto como "me envia esse documento") e, quando ambíguo, sinaliza para **perguntar ao usuário** qual arquivo enviar.
   * ✅ Substitui o casamento por palavra-chave anterior, que falhava com pronomes e referências contextuais.

8. **Backfill (opcional)**
   * Documentos já indexados antes do fluxo unificado (ex.: Manual do Coordenador) não estão no bucket. Subir manualmente uma vez via Studio ou um script de carga inicial.

### 🔹 Fase 7: Experiência de Conversa (UX) (Concluída ✅)

**Objetivo:** Aproximar a interação do chat de aplicativos de mensagens modernos, dando ao usuário mais controle sobre o contexto e a navegação.

* ✅ **Citação / Menção de Mensagem (estilo WhatsApp):** botão "Responder" em cada mensagem (usuário ou assistente) que cita a mensagem anterior. A citação aparece fixada acima da mensagem, é **persistida no histórico** (`metadata.quoted`) — reaparecendo ao recarregar a conversa — e é **enviada como contexto explícito** à IA, permitindo perguntas do tipo "explique melhor o primeiro item dessa resposta".
* ✅ **Ir para a Última Mensagem:** setinha flutuante (↓) que aparece logo acima do input quando o usuário rola para cima, com rolagem suave até o fim. Inclui auto-seguir inteligente durante o streaming (acompanha o fim apenas quando o usuário já está perto dele).

## 💡 Banco de Ideias (Backlog)

* [ ] **Interface Web Moderna**: Migrar do Streamlit para um frontend em Next.js + Tailwind para maior controle de UX/UI.
* [ ] **Integração com Área do Coordenador**: API para buscar dados em tempo real de outros sistemas institucionais da FAI.
* [ ] **Sugestões de Perguntas**: Chips clicáveis com perguntas frequentes baseadas nos documentos mais acessados.
* [ ] **Feedback de Qualidade**: Botões de "Joinha" (Polegar para cima/baixo) para treinar ou ajustar o RAG futuramente.
* [ ] **Exportação de Conversas**: Opção para baixar o histórico formatado em PDF ou Markdown.

Última atualização: 11 de Junho de 2026

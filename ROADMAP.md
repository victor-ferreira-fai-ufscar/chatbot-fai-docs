# 🚀 FAI Chatbot: Roadmap de Evolução

Este documento serve como o registro central de ideias, planos e futuras melhorias para o sistema de chatbot. Novas ideias devem ser adicionadas aqui para manter o alinhamento tecnológico e a visão de longo prazo.

---

## 🏆 Visão Geral
Transformar o chatbot atual em uma ferramenta institucional de alta performance, capaz de lidar com documentos complexos e oferecer uma experiência de usuário personalizada e persistente.

---

## 📅 Fases de Implementação

### 🔹 Fase 1: Autoconsciência e Contexto (Concluída ✅)
*   Injeção dinâmica de data e hora no prompt.
*   Reconhecimento automático da lista de manuais disponíveis no sistema.
*   Suavização da ancoragem RAG para permitir respostas sobre o estado do sistema.

### 🔹 Fase 2: Visão e OCR Avançado (Google Vision API)
**Objetivo:** Superar as limitações do processamento de PDF convencional.
*   **Fallback Híbrido:** Usar OCR gratuito (`pypdf`) por padrão e disparar a Google Vision apenas em páginas "cegas" (scans antigos ou imagens).
*   **Leitura de Prints:** Indexar ilustrações e telas de sistemas que hoje são ignoradas.
*   **Referência Detalhada:** [Ver plano técnico](docs/future_vision_api_plan.md)

### 🔹 Fase 3: Persistência e Histórico (SQLite)
**Objetivo:** Permitir que o usuário retome conversas e gerencie múltiplos contextos.
*   **Banco de Dados Local:** Implementação do `sqlite3` para persistir mensagens e threads.
*   **Gestão de Threads:** Identificadores únicos para cada conversa.
*   **Interface Lateral:** Barra lateral com histórico de chats (padrão ChatGPT).
*   **Títulos Automáticos:** Usar a LLM para gerar títulos curtos para cada nova conversa baseando-se na primeira pergunta.

### 🔹 Fase 4: Transcrição de Áudio (Speech-to-Text) - [ADIADA]
**Objetivo:** Permitir que usuários enviem perguntas por voz, facilitando o uso em dispositivos móveis.
*   **Integração Local Whisper**: Implementado motor 100% local (`faster-whisper`), mas desativado temporariamente para priorizar a estabilidade do campo de texto original e UX minimalista.
*   **Interface de Gravador**: Possibilidade de reativar o botão de microfone no futuro conforme demanda dos usuários.

### 🔹 Fase 5: Arquitetura RAG Dual (Supabase vs LightRAG)
**Objetivo:** Permitir a escolha dinâmica entre a abordagem atual via Supabase e a nova abordagem via Grafos do LightRAG para fins de comparação de performance e qualidade de resposta.
*   **Integração LightRAG Backend**: Criação de um cliente/serviço para consumir a API local do LightRAG (que opera na porta `9621`).
*   **Seletor na Interface**: Inserir um botão Toggle ou Select no painel lateral/header da interface do chatbot permitindo alternar facilmente entre o "RAG Tradicional (Supabase)" e o "GraphRAG (LightRAG)".
*   **Roteamento e Comparativo**: Quando o usuário envia a mensagem, o sistema decide qual pipeline de RAG chamar baseado na opção selecionada, mantendo a experiência fluida.

---

## 💡 Banco de Ideias (Backlog)

*   [ ] **Interface Web Moderna**: Migrar do Streamlit para um frontend em Next.js + Tailwind para maior controle de UX/UI.
*   [ ] **Integração com Área do Coordenador**: API para buscar dados em tempo real de outros sistemas institucionais da FAI.
*   [ ] **Sugestões de Perguntas**: Chips clicáveis com perguntas frequentes baseadas nos documentos mais acessados.
*   [ ] **Feedback de Qualidade**: Botões de "Joinha" (Polegar para cima/baixo) para treinar ou ajustar o RAG futuramente.
*   [ ] **Exportação de Conversas**: Opção para baixar o histórico formatado em PDF ou Markdown.

---
*Última atualização: 15 de Abril de 2026*

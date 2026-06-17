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

### 🔹 Fase 4: Transcrição de Áudio (Speech-to-Text) (Concluída ✅)

**Objetivo:** Permitir que usuários enviem perguntas por voz, facilitando o uso em dispositivos móveis.

* ✅ **Integração Local Whisper (OpenAI)**: Motor 100% local com o [`openai-whisper`](https://github.com/openai/whisper), modelo **`medium`** (configurável via `WHISPER_MODEL`). O modelo é baixado no build da imagem do backend e carregado sob demanda na primeira transcrição (singleton mantido quente em VRAM entre requisições).
* ✅ **Endpoint de Transcrição**: `POST /api/v1/audio/transcribe` recebe o áudio (`UploadFile`), transcreve em threadpool e retorna o texto. Idioma fixado em `pt` por padrão (`WHISPER_LANGUAGE`).
* ✅ **Interface de Gravador**: Botão de microfone funcional em `ChatWindow.tsx` (MediaRecorder → endpoint de transcrição → texto injetado no campo de input), com estados de gravando/transcrevendo.
* ✅ **Aceleração por GPU (RTX 5090)**: rodando em CUDA (`torch 2.11.0+cu128`, suporte a Blackwell/sm_120). O host recebeu o `nvidia-container-toolkit` + runtime nvidia no Docker e o backend usa `gpus: all`. Validado em produção: `device='cuda'`, 1ª transcrição ~4s (inclui carregar o modelo na VRAM), chamadas seguintes <0,1s. Fallback automático para CPU via `WHISPER_DEVICE=auto` caso a GPU não esteja disponível.
* ✅ **HTTPS (pré-requisito do microfone)**: o `getUserMedia` exige contexto seguro. Resolvido com o **Caddy central** (`/opt/stacks/caddy`) terminando TLS e servindo frontend + API sob o mesmo origin (`https://200.136.209.229` e `https://lina.fai.ufscar.br`). Hoje com cert self-signed (CA interna) — migra para Let's Encrypt quando houver DNS público.
* 💡 *Transcrição "ao vivo" (streaming) foi avaliada e adiada:* o Whisper não é streaming nativo; o comportamento atual transcreve ao parar a gravação. Ver Backlog.

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

### 🔹 Fase 8: De Chatbot para Agente com Skills (Tool Calling) 🚧

**Objetivo:** Transformar a Lina de um pipeline RAG fixo em um **agente** que decide, a cada turno, **quais Skills** usar — com o **LightRAG virando uma Skill** (consultado só quando há necessidade documental, não mais em todo turno). O agente deve "fazer praticamente tudo" dentro do ambiente da FAI: consultar a base de conhecimento, **gerar planilhas, gerar PDFs/documentos** e entregar arquivos — tudo **100% on‑premises**.

**Decisões de arquitetura (fixadas):**
* **Laço de tool calling nativo**, sobre a camada `src/IA/Models` (API OpenAI‑compatible do Ollama). Sem framework externo (LangGraph/Pydantic‑AI) — controle total e zero dependências novas. Funciona com qualquer modelo local que suporte function calling (gpt-oss, Qwen3, Mistral, Llama, etc.), não só o gpt-oss.
* **Capacidades empacotadas como Skills:** uma pasta por skill em `backend/skills/` com um `SKILL.md` (convenção inspirada nas [Anthropic Agent Skills](https://github.com/anthropics/skills)), descobertas por um *loader* e expostas ao laço como **ferramentas tipadas**. Skill nova = pasta nova, sem tocar no laço.
* **Execução model-agnostic e segura:** cada skill roda por um *handler* Python determinístico que nós entregamos (`kind: native`) — o modelo **não** escreve nem roda código. Mesmo comportamento trocando o cérebro (gpt-oss, Qwen3, Mistral, Llama, multimodal). Skills `kind: script` (modelo escreve código), incl. as oficiais `pdf`/`xlsx`/`docx` da Anthropic, ficam para a **Fase 10** (sandbox); o loader as rejeita até lá.
* **`anthropics/skills` = referência**, não dependência: skills próprias, em PT, afinadas para modelos locais; pega-se estrutura + know-how do upstream, sem vendorizar/submodular.
* **Primeira entrega = 4 skills:** `consultar_base_conhecimento` (LightRAG), `gerar_planilha` (xlsx/csv via openpyxl), `gerar_documento_pdf` (WeasyPrint/fpdf2) e `entregar_documento` (Storage + signed URL, reusando o resolver da Fase 6).
* **Compatibilidade:** o agente devolve o mesmo gerador de tuplas `("answer"|"thought"|"usage", …)` que o `chat_stream` já consome; persona (Lina), histórico, citações e chips de download são preservados. Flag `AGENT_ENABLED` permite rollback para o fluxo atual.

* 📋 **Plano técnico detalhado:** [docs/plano-agente-tool-calling.md](docs/plano-agente-tool-calling.md) (anatomia de uma Skill, loader, laço, disclosure progressivo, passos 8.0–8.9, riscos).

### 🔹 Fase 9: Multimodalidade (Visão) e OCR Agêntico

**Objetivo:** Dar olhos à Lina — ler **prints de tela, fotos, diagramas e PDFs escaneados** que hoje são ignorados. Como o `gpt-oss` (cérebro atual) é **texto‑puro**, esta fase decide entre **(a)** adicionar uma **skill** `analisar_imagem` apoiada por um modelo de visão carregado sob demanda, ou **(b)** trocar o cérebro do agente por um **modelo multimodal agêntico** único (faz tools + visão). Conecta‑se ao plano de OCR híbrido da Fase 2.

* Skill `analisar_imagem` / `ler_documento_escaneado` (entrada: upload do usuário ou página "cega" de PDF).
* Decisão de modelo conforme a tabela em **"Sugestões de Modelos"** (abaixo), respeitando o orçamento de **32 GB de VRAM** da RTX 5090.
* Ingestão multimodal no LightRAG (indexar texto extraído de imagens/scans).

### 🔹 Fase 10: Governança, Segurança e Auditoria do Agente

**Objetivo:** Como o agente passa a **gerar arquivos e tomar ações**, blindar o sistema para uso institucional.

* **Limites de execução:** `MAX_TOOL_STEPS`, timeout por skill, teto de tamanho de arquivos gerados.
* **Auditoria:** persistir no `metadata` da mensagem quais skills foram chamadas, com quais argumentos e resultados (rastreabilidade para dados sensíveis da FAI).
* **Sandbox (habilita Skills `kind: script`):** quando o agente puder **escrever/rodar código** — incl. rodar/adaptar as skills oficiais `pdf`/`xlsx`/`docx` da Anthropic, ou uma tool de cálculos — isolá‑la (container efêmero / sem rede).
* **Controle de acesso:** quando houver login (hoje há isolamento por `user_id`), restringir skills sensíveis por perfil.
* **MCP (Model Context Protocol):** expor as skills via MCP para reuso por outros clientes internos da FAI — e, no inverso, consumir tools MCP externas como skills (backlog).

## 🧠 Sugestões de Modelos Multimodais Agênticos Locais

Levantamento (jun/2026) de modelos **open‑weight, locais (Ollama/vLLM)** para um agente que faz **tool calling** e, idealmente, **visão**, cabendo no orçamento de **uma RTX 5090 (32 GB)**. Hoje a VRAM já abriga ~23 GB (gpt‑oss 13 GB + auxiliar + `bge-m3` 0,7 GB), então as escolhas consideram a folga restante.

> ⚠️ **Verificar antes de produção:** tags do Ollama, VRAM por quantização e números de benchmark mudam rápido. Confirmar no `ollama.com/library` e nas fontes antes de fixar.

| Modelo | Tool calling | Visão | VRAM (~Q4) | Ollama | Observações |
|--------|:---:|:---:|---|---|---|
| **gpt-oss:20b** (atual) | ✅ nativo, forte | ❌ texto‑puro | ~13 GB | `gpt-oss:20b` | Cérebro atual; ótimo raciocínio + function calling. Mantém‑se na Fase 8. |
| **Qwen3‑VL:8b** | ✅ (Hermes‑style) | ✅ | ~12 GB | `qwen3-vl:8b` | Coabita com o gpt‑oss; bom custo/benefício para a skill de visão. |
| **Qwen3‑VL:32b** | ✅ | ✅ forte | ~16–24 GB | `qwen3-vl:32b` | Melhor visão; **tight** se mantiver gpt‑oss carregado — exige swap de modelo. |
| **Mistral Small 3.2 (24B)** | ✅ nativo + JSON | ✅ | ~15 GB | `mistral-small3.2` | **Candidato a cérebro único** (tools + visão), 128k contexto, baixa latência. Simplifica a VRAM (um modelo no lugar de dois). |
| **Gemma 3/4 (vision)** | ✅ (variantes recentes) | ✅ | E4B ~6 GB | `gemma3`/aux | Família já usada como auxiliar; variante pequena boa para tarefas baratas. |

**Recomendações:**
* **(a) Cérebro do agente (tools + visão num só):** **Mistral Small 3.2** — visão + function calling nativo + 128k contexto em ~15 GB libera a VRAM e simplifica a operação. **Alternativa:** **Qwen3‑VL:32b** se a qualidade de visão for prioritária (família Qwen lidera os rankings de function calling tipo BFCL).
* **(b) Manter gpt‑oss + visão como ferramenta:** gpt‑oss:20b (cérebro, texto) **+** `qwen3-vl:8b` carregado sob demanda para a skill `analisar_imagem`. Cabe nos 32 GB, mas com folga apertada (preferir swap de modelo pelo Ollama a manter ambos residentes).
* **(c) Modelo auxiliar rápido** (roteamento, títulos, smalltalk): variante pequena do **Gemma** ou **Qwen3** (~4–8B) — barato e rápido, libera o cérebro para o laço de agente.

**Estratégia de VRAM (32 GB):** manter `bge-m3` (0,7 GB) residente para o LightRAG; **um** cérebro de agente (gpt‑oss 13 GB *ou* Mistral Small 3.2 15 GB); modelos de visão/auxiliares **carregados sob demanda** (o Ollama faz swap) em vez de todos residentes. Medir empiricamente após cada troca, como já feito com o gpt‑oss.

**Fontes:** [Qwen3‑VL (GitHub)](https://github.com/qwenlm/qwen3-vl) · [Qwen3‑VL no Ollama / VRAM por quant](https://localllm.in/blog/ollama-vram-requirements-for-local-llms) · [gpt-oss no Ollama](https://ollama.com/library/gpt-oss) · [gpt-oss (OpenAI)](https://openai.com/index/introducing-gpt-oss/) · [Mistral Small 3.2 (Ollama)](https://ollama.com/library/mistral-small3.2) · [Mistral Small 3.1 (model card)](https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503) · [Berkeley Function Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html)

## 💡 Banco de Ideias (Backlog)

* [x] **Interface Web Moderna**: ~~Migrar do Streamlit para um frontend em Next.js + Tailwind~~ — concluído (frontend atual em Next.js + Tailwind).
* [ ] **Transcrição de Voz "ao vivo" (streaming)**: texto aparecendo enquanto o usuário fala. Como o Whisper não é streaming nativo, exigiria pseudo-streaming por chunks (re-transcrever o áudio acumulado a cada ~2-3s) ou um servidor de streaming dedicado (ex.: WhisperLive/whisper_streaming + VAD via websocket). Hoje a transcrição ocorre ao parar a gravação.
* [ ] **Integração com Área do Coordenador**: API para buscar dados em tempo real de outros sistemas institucionais da FAI — naturalmente exposta como a skill `consultar_sistema_fai` (Fase 8+).
* [ ] **Sugestões de Perguntas**: Chips clicáveis com perguntas frequentes baseadas nos documentos mais acessados.
* [ ] **Feedback de Qualidade**: Botões de "Joinha" (Polegar para cima/baixo) para treinar ou ajustar o RAG futuramente.
* [ ] **Exportação de Conversas**: Opção para baixar o histórico formatado em PDF ou Markdown — reaproveita a skill `gerar_documento_pdf` (Fase 8).

### 🧩 Skills futuras candidatas (catálogo do agente)

> O modelo de Skills (Fase 8) é feito para crescer: **nova capacidade = nova pasta em `backend/skills/`**, sem tocar no laço. Candidatas para depois da primeira entrega (4 skills):

* [ ] **`gerar_documento_docx` / `gerar_apresentacao_pptx`**: gerar Word/PowerPoint **editáveis** (não só PDF). Bons candidatos a adaptar das skills oficiais `docx`/`pptx` da Anthropic quando houver sandbox (`kind: script`, Fase 10).
* [ ] **`gerar_grafico`**: gráficos/visualizações (matplotlib) a partir de dados extraídos via `consultar_base_conhecimento`, entregues como imagem/PDF.
* [ ] **`enviar_email`**: enviar a resposta ou o arquivo gerado por e-mail institucional (SMTP da FAI). Ação com efeito externo → exige a governança da Fase 10 (confirmação + auditoria).
* [ ] **`consultar_sistema_fai`**: integração com sistemas institucionais (Área do Coordenador) exposta como skill — ver item acima.
* [ ] **`resumir_documento` / `comparar_documentos`**: resumo executivo de um manual inteiro, ou comparação entre versões/normas, sob demanda.
* [ ] **`analisar_imagem`**: skill de visão — já planejada na Fase 9 (multimodalidade).

### ⚙️ Infraestrutura do agente / Skills

* [ ] **Roteador de skills (disclosure em escala):** quando o catálogo crescer a ponto de poluir o `tools=`, uma skill `descobrir_skills(intencao)` seleciona as candidatas antes de expor os schemas (ver plano §4.3).
* [ ] **Fallback de tool calling:** modo JSON/ReAct por prompt para modelos locais **sem** function calling nativo, mantendo o agente model-agnostic.
* [ ] **Hot-reload de skills:** recarregar `backend/skills/` sem reiniciar o backend (dropar a pasta → skill disponível na hora).
* [ ] **Catálogo administrável:** listar skills disponíveis e habilitar/desabilitar por ambiente (dev/produção) ou por perfil de usuário (liga com Controle de Acesso, Fase 10).
* [ ] **Suíte de avaliação de skills:** transformar a matriz model-agnostic (passo 8.9) numa bateria de regressão por modelo (qualidade de tool calling + artefatos idênticos).

Última atualização: 17 de Junho de 2026

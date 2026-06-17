# Plano de Implementação: De Chatbot RAG para Agente com Skills (Tool Calling)

> **Status:** proposta de implementação (Fase 8 do [ROADMAP](../ROADMAP.md)).
> **Decisões fixadas:**
> - Laço de tool calling **nativo** sobre a camada `src/IA/Models` (OpenAI‑compatible / Ollama), **sem framework externo**.
> - As capacidades do agente são empacotadas como **Skills** — uma pasta por skill com um `SKILL.md` (convenção inspirada nas [Anthropic Agent Skills](https://github.com/anthropics/skills)), descobertas por um *loader* e expostas ao laço como **ferramentas tipadas**.
> - **Execução model‑agnostic e segura:** cada skill é executada por um *handler* Python determinístico que **nós** entregamos — o modelo **não** escreve nem roda código. O sistema mantém o mesmo comportamento trocando o cérebro (gpt‑oss, Qwen3, Mistral Small, Llama, um modelo multimodal…).
> - **Sem sandbox / code‑exec nesta fase.** Skills do tipo *script* (em que o modelo escreve código), incluindo as oficiais `pdf`/`xlsx`/`docx` da Anthropic, ficam para a **Fase 10** (sandbox/governança). O contrato de skill já é desenhado para acomodá‑las **sem mexer no laço**.
> - `anthropics/skills` é **referência**, não dependência: nossas skills são próprias, em PT, afinadas para modelos locais. Tudo **100% on‑premises** (FAI), sem nuvem.

---

## 1. Objetivo e mudança de paradigma

Hoje a orquestração é **fixa** e vive no endpoint `backend/app/api/endpoints/chat.py` (`chat_stream`): um `if/else` decide entre (a) *smalltalk gate* → resposta conversacional, (b) intenção de download → resolvedor de documento, (c) caso padrão → **sempre** consultar o LightRAG. O modelo nunca decide o que fazer; ele só redige a resposta final.

O alvo é inverter isso: o modelo passa a ser um **agente** que recebe um conjunto de **Skills** (ferramentas autodescritas) e decide, a cada turno, **se** e **qual** skill usar — inclusive consultar o LightRAG apenas quando precisa de conhecimento documental. A persona (Lina) e as regras de ancoragem permanecem, mas o LightRAG vira **uma skill entre outras**, não o trilho obrigatório.

```
Hoje:   pergunta ──> [if/else fixo] ──> LightRAG (sempre) ──> resposta
Alvo:   pergunta ──> [AGENTE] ──┬──> consultar_base_conhecimento (LightRAG)   ← só quando precisa
                                ├──> gerar_planilha (xlsx/csv)
                                ├──> gerar_documento_pdf
                                ├──> entregar_documento (arquivo já indexado)
                                ├──> … (novas skills = nova pasta, sem tocar no laço)
                                └──> (responde direto, sem skill, em conversa social)
                 (laço: usa skills até ter o suficiente, então redige a resposta final)
```

---

## 2. Por que Skills *tipadas* (e não o runtime de code‑exec)

As Anthropic Agent Skills empacotam **duas coisas distintas**, e a escolha entre elas define toda a arquitetura:

1. **O formato** — uma pasta por capacidade, com `SKILL.md` (frontmatter `name` + `description` curtos e um corpo de instruções em Markdown) e, opcionalmente, arquivos de apoio. Combinado com **disclosure progressivo**: só os metadados (name/description) ficam sempre no contexto; as instruções completas são carregadas **sob demanda**.
2. **O runtime** — o modelo lê as instruções e **escreve e executa código** num sandbox para cumprir a tarefa (é assim que as skills oficiais `pdf`/`xlsx`/`docx` funcionam: o modelo gera um script Python que manipula o arquivo).

**Adotamos o formato; não adotamos o runtime de code‑exec nesta fase.** Motivos:

- **Model‑agnostic é requisito.** Vamos testar vários modelos locais (gpt‑oss, Qwen3, Mistral Small, Llama, multimodais) e o sistema precisa funcionar bem **independente** do escolhido. O runtime de code‑exec faz a qualidade depender de o modelo **escrever código correto de primeira** — exatamente onde modelos locais variam mais e os menores falham. Com **tool tipada**, o modelo só faz a parte fácil e uniforme entre modelos: **escolher a skill e preencher um JSON Schema** (function calling). O trabalho pesado (montar o `.xlsx`, renderizar o PDF, consultar o LightRAG) roda no **nosso handler determinístico** → **o artefato sai igual** trocando o cérebro; só a *decisão* de qual skill chamar depende do modelo.
- **Segurança / governança.** Execução de código arbitrário por um LLM num ambiente institucional exige sandbox, limites e auditoria — é a **Fase 10** do ROADMAP, que decidimos não antecipar.
- **A extensibilidade vem do formato, não do runtime.** "Dropar uma pasta = nova capacidade", catálogo escalável via disclosure e um lugar único no projeto — tudo isso o formato entrega sem code‑exec.

**O que NÃO perdemos:** o contrato de skill (§3) prevê desde já um segundo *kind* — `script` — para skills que precisarão de sandbox. Quando a Fase 10 entregar o sandbox, essas skills (inclusive vendorizar/adaptar as oficiais da Anthropic) entram **sem alterar o laço** — só o despachante passa a saber executar `kind: script`.

> **Relação com `anthropics/skills` (decisão "Referência"):** as skills oficiais são *skills que escrevem código*, afinadas para o Claude. Não rodam como estão num cenário sem code‑exec e com cérebro local. Então criamos skills **próprias, em PT, afinadas para modelos locais**, tomando do upstream a **estrutura** (frontmatter, disclosure, exemplos) e o **know‑how de domínio** (quais libs, pegadinhas de cada formato). Útil clonar o repo localmente como consulta durante o dev; **não** vendorizamos nem submodulamos no produto (evita acoplamento a um runtime diferente e a instruções afinadas p/ outro modelo).

---

## 3. Anatomia de uma Skill

Cada skill é uma **pasta** sob `backend/skills/` — o lugar único do projeto onde as ferramentas ficam "disponibilizadas para o agente". Uma skill nova = uma pasta nova; o laço não muda.

```
backend/skills/
├── consultar_base_conhecimento/
│   ├── SKILL.md          # frontmatter (name/description/params) + instruções (corpo)
│   └── handler.py        # callable Python determinístico (kind=native)
├── gerar_planilha/
│   ├── SKILL.md
│   └── handler.py
├── gerar_documento_pdf/
│   ├── SKILL.md
│   └── handler.py
└── entregar_documento/
    ├── SKILL.md
    └── handler.py
```

### 3.1 `SKILL.md` — contrato declarativo

```markdown
---
name: gerar_planilha
description: "Gera uma planilha (.xlsx) a partir de dados estruturados e devolve link de download. Use quando pedirem tabela/planilha/exportação de dados."
kind: native                       # native (handler Python, esta fase) | script (sandbox, Fase 10)
handler: handler.py:executar       # módulo:função do callable (apenas kind=native)
parameters:                        # JSON Schema dos argumentos (vai no `tools=`)
  type: object
  properties:
    titulo:  { type: string }
    colunas: { type: array, items: { type: string } }
    linhas:  { type: array, items: { type: array, items: { type: string } } }
  required: [titulo, colunas, linhas]
---

# Instruções (carregadas SOB DEMANDA — disclosure progressivo)

Como montar a planilha, exemplos de bom uso, formatação, casos de borda…
(este corpo NÃO vai no system prompt; ver §4.3)
```

- **`description` é curta** (uma linha): é o que sempre fica no `tools=`. As instruções ricas vivem no **corpo**, carregado só quando a skill é relevante.
- **`parameters`** é o JSON Schema que vira o schema da função no tool calling.
- **`kind`**: `native` agora (handler Python que nós entregamos); `script` reservado p/ Fase 10 (sandbox).

### 3.2 Contrato do handler (`kind: native`)

```python
# backend/skills/gerar_planilha/handler.py
from src.chatbot_fai_docs.agent.types import AgentContext, SkillResult

def executar(args: dict, ctx: AgentContext) -> SkillResult:
    """args: validado contra o JSON Schema do SKILL.md.
       ctx:  config, StorageService, histórico, coletor de efeitos colaterais."""
    ...
    return SkillResult(
        for_model="Planilha gerada com 12 linhas.",   # texto que volta ao modelo (mensagem `tool`)
        sources=[],                                     # fontes citadas (LightRAG) → evento `done`
        downloads=[("planilha.xlsx", signed_url)],      # chips de download → evento `done`
    )
```

- **`for_model`**: vira o `content` da mensagem `role:"tool"` no próximo turno do laço.
- **Efeitos colaterais** (`sources`, `downloads`) são coletados no `ctx` e emitidos pelo endpoint no evento `done`, preservando "Fontes Pesquisadas" e os chips de download das Fases 6/7.
- Handlers importam serviços do projeto normalmente (`from src.chatbot_fai_docs.lightrag_service import LightRagService`) — o `src` já está no `sys.path` do backend.

---

## 4. Arquitetura: loader + laço nativo

### 4.1 Componentes novos (backend)

```
backend/skills/                      # as skills (pastas) — ver §3
backend/src/chatbot_fai_docs/agent/
├── __init__.py
├── types.py            # AgentContext, SkillResult
├── skill_loader.py     # varre backend/skills/*/SKILL.md -> schemas + registry de handlers
├── tool_registry.py    # nome -> (schema, handler, instruções); dispatch com validação/timeout
└── agent_service.py    # o laço (orquestrador): run_stream(...)
```

### 4.2 O *loader* de skills (`skill_loader.py`)

No startup (ou no 1º uso), o loader:
1. varre `backend/skills/*/SKILL.md` e faz parse do frontmatter (`name`, `description`, `kind`, `parameters`, `handler`) e separa o corpo (instruções);
2. para `kind: native`, importa o callable via `importlib` (`handler.py:executar`);
3. monta `TOOL_SCHEMAS = [{"type":"function","function":{"name","description","parameters"}}, …]` (só a `description` **curta**);
4. registra no `tool_registry`: `name -> {schema, handler, instrucoes}`.

Resultado: **adicionar uma skill = criar uma pasta**. Sem editar o laço, o endpoint ou o registry.

### 4.3 Disclosure progressivo no tool calling

Em function calling, o schema precisa estar no `tools=` para o modelo poder chamar. Então o disclosure se traduz assim:

- **Sempre no `tools=`:** apenas `name` + `description` curta + `parameters` de cada skill → prompt enxuto mesmo com muitas skills.
- **Sob demanda:** o **corpo** do `SKILL.md` (instruções detalhadas, exemplos, formatação) **não** entra no system prompt. É injetado só quando a skill entra em jogo, por uma destas vias (configurável):
  - **(a) preâmbulo no resultado** — na 1ª vez que a skill é chamada no laço, prefixamos as instruções ao `for_model` retornado; ou
  - **(b) skill utilitária** `consultar_instrucoes(nome_skill)` que o modelo chama antes de usar a skill.
- **Escala p/ catálogo grande (futuro):** quando o nº de skills crescer a ponto de poluir o `tools=`, adiciona‑se uma skill de **roteamento** (`descobrir_skills(intencao)`) que devolve as candidatas; só então o laço expõe os schemas relevantes. Para a 1ª entrega (4 skills), o `tools=` completo é barato e dispensa o roteador.

### 4.4 Extensão da camada de modelos (`src/IA/Models`)

Hoje `OllamaModel.generate()` / `OpenAIModel.generate()` **só** fazem streaming de texto e emitem tuplas `("answer"|"thought"|"usage", conteúdo)`. Vamos adicionar **um método novo** que aceita `tools` e devolve também `("tool_calls", [...])`, sem quebrar o `generate()` existente (que o título e o smalltalk continuam usando).

```python
# src/IA/Models/ollama.py  (mesma ideia em openai.py)
import json

def chat(self, messages: list[dict], tools: list[dict] | None = None):
    """Um turno do laço de agente. Faz streaming e, ao final, sinaliza
    se o modelo pediu skills (tools). Mantém o protocolo de tuplas existente:
      ("thought", txt)      -> raciocínio (emitido ao vivo, UX)
      ("answer", txt)       -> texto da resposta final (bufferizado, ver laço)
      ("tool_calls", calls) -> [{id, name, arguments(dict)}, ...]
      ("usage", int)
    """
    stream = self.client.chat.completions.create(
        model=self.model_name, messages=messages, tools=tools or None,
        tool_choice="auto", temperature=0.2, stream=True,
        stream_options={"include_usage": True},
    )
    tool_acc = {}   # index -> {id, name, args(str)}
    for chunk in stream:
        ... # reasoning -> ("thought", ...)  | content -> ("answer", ...)  (igual ao generate())
        for tc in (delta.tool_calls or []):
            acc = tool_acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
            acc["id"]   += tc.id or ""
            acc["name"] += (tc.function.name or "")
            acc["args"] += (tc.function.arguments or "")   # JSON chega em pedaços
    if tool_acc:
        yield ("tool_calls", [{"id": a["id"], "name": a["name"],
                               "arguments": json.loads(a["args"] or "{}")}
                              for a in tool_acc.values()])
```

> **Nota técnica:** os argumentos das `tool_calls` chegam **fragmentados** no streaming; é obrigatório **acumular as strings por `index`** e só fazer `json.loads` no final. Esse é o erro nº 1 de quem implementa tool calling com a API OpenAI/Ollama.

### 4.5 O laço (`agent_service.py`)

```python
def run_stream(question, conversation_history, ctx) -> Generator[tuple, None, None]:
    schemas, registry = load_skills()             # do skill_loader (§4.2)
    messages = [{"role": "system", "content": build_agent_system_prompt(ctx)}]
    messages += history_to_messages(conversation_history)
    messages += [{"role": "user", "content": question}]

    for step in range(MAX_TOOL_STEPS):             # guarda contra laço infinito (ex.: 5)
        answer_buf, tool_calls = "", None
        for kind, payload in model.chat(messages, tools=schemas):
            if kind == "thought":   yield ("thought", payload)         # streama ao vivo
            elif kind == "answer":  answer_buf += payload              # buffer
            elif kind == "tool_calls": tool_calls = payload
            elif kind == "usage":   yield ("usage", payload)

        if not tool_calls:                          # modelo redigiu a resposta final
            yield ("answer", answer_buf); return

        # registra a intenção do assistente + executa cada skill
        messages.append({"role": "assistant", "content": answer_buf or None,
                         "tool_calls": to_openai_tool_calls(tool_calls)})
        for call in tool_calls:
            yield ("tool_status", f"🔧 {call['name']}…")               # UX opcional (evento SSE)
            result = registry.dispatch(call["name"], call["arguments"], ctx)  # valida args + timeout
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result.for_model})             # texto p/ o modelo
            ctx.collect(result)                     # fontes citadas, links de download, etc.

    yield ("answer", "Não consegui concluir a tarefa em tempo hábil. Pode reformular?")
```

**Pontos de projeto:**
- **`thought` ao vivo, `answer` bufferizada.** Modelos de raciocínio (gpt‑oss) emitem `thought` antes de decidir. O texto de `answer` só vai ao usuário no turno **sem** `tool_calls` (a resposta final), evitando vazar rascunhos.
- **Guarda de passos (`MAX_TOOL_STEPS`)** + **timeout por skill** para nunca travar a requisição.
- **`ctx` (contexto da requisição)** carrega `config`, `StorageService`, histórico e um **coletor** de efeitos colaterais (fontes do LightRAG, links assinados) que o endpoint emite no evento `done`.

### 4.6 Model‑agnostic e multimodalidade (requisito central)

- **Interface única:** o laço só conhece `tools=`/`tool_calls` da API OpenAI‑compatible que o Ollama expõe **igual** para qualquer modelo com function calling. O laço **não** conhece o modelo.
- **Qualidade não cai ao trocar de modelo:** o artefato é produzido pelo handler determinístico; só a *decisão* de qual skill chamar depende do cérebro — a parte mais fácil e uniforme entre modelos.
- **Variância de function calling entre locais:** Qwen3 (líder em FC), gpt‑oss, Mistral, Llama 3.1+, Hermes suportam bem; alguns mal. Mitigações: poucas skills + descrições afiadas; `tool_choice="auto"`; disclosure reduz ruído; **fallback opcional** (JSON‑mode / prompt estilo ReAct) para modelos sem FC nativo. Há um passo de validação por matriz de modelos no plano incremental (§6).
- **Multimodalidade (Fase 9):** o contrato de skill **independe** da modalidade do cérebro. Um modelo multimodal "vê" imagens nas mensagens; uma skill de visão (`analisar_imagem`) também pode delegar a um modelo de visão sob demanda. Vision como **input** é Fase 9 e **não muda o laço**.

---

## 5. As quatro skills da primeira entrega

Cada uma é uma pasta `SKILL.md` + `handler.py` (`kind: native`).

### 5.1 `consultar_base_conhecimento` — LightRAG como skill  ⭐ núcleo

`SKILL.md` (frontmatter resumido):
```yaml
name: consultar_base_conhecimento
description: "Consulta os manuais e documentos institucionais da FAI (base de conhecimento). Use SEMPRE que a pergunta exigir informação factual sobre processos, normas, prazos, valores ou conteúdo de manuais. NÃO use para conversa social."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    consulta: { type: string, description: "A pergunta/termo a buscar, reescrita para maximizar recuperação." }
    modo:     { type: string, enum: [mix, hybrid, local, global], description: "Modo de busca do grafo. Padrão: mix." }
  required: [consulta]
```

- **Handler:** envolve o `LightRagService` já existente. Hoje ele faz *streaming para o usuário*; para uso como skill precisamos de uma **variante não‑stream** que **colete o texto completo + `source_lines`** e os devolva ao agente. Reusar o parsing de `<think>`/References/fallback de `lightrag_service.py`.
- **Fontes:** as `source_lines` entram no `ctx` e seguem para o evento `done` (mantém os chips de fonte clicáveis das Fases 6/7).
- **Ancoragem:** a regra estrita do `Prompt.md` continua valendo para o **conteúdo factual** — o agente só afirma o que esta skill retornou.

### 5.2 `gerar_planilha` — Excel/CSV

`parameters`: `titulo` (string), `colunas` (array de string), `linhas` (array de array de string).

- **Lib:** `openpyxl` (puro Python, offline) para `.xlsx`; `csv` da stdlib para `.csv`. Sem rede.
- **Fluxo:** monta o arquivo em memória (`BytesIO`) → `StorageService.upload(nome_sanitizado, bytes, content_type)` → `create_signed_url(...)` → `SkillResult` com `downloads=[(nome, url)]` e um `for_model` curto.
- **Dado:** o agente normalmente preenche `linhas` com o que extraiu via `consultar_base_conhecimento` num passo anterior — daí a importância do laço multi‑etapa.

### 5.3 `gerar_documento_pdf` — relatórios/declarações em PDF

`parameters`: `titulo` (string), `conteudo_markdown` (string), `rodape` (string, opcional).

- **Lib recomendada:** `WeasyPrint` (Markdown → HTML → PDF com CSS, ótima tipografia). Alternativa leve: `fpdf2`/`reportlab`.
- **Atenção Docker:** o WeasyPrint exige libs de sistema (`libpango`, `libcairo`, `libgdk-pixbuf`) no `backend/Dockerfile`. Para evitar, usar `fpdf2`.
- **Fluxo:** idêntico ao da planilha (gera bytes → Storage → signed URL).
- **Template institucional (opcional):** cabeçalho com logo da FAI + CSS padrão. *(Quando, na Fase 10, houver sandbox, este é o candidato natural a virar uma `kind: script` mais flexível — adaptada da skill `pdf` oficial.)*

### 5.4 `entregar_documento` — arquivo já indexado

`parameters`: `referencia` (string) — "manual do coordenador", "esse documento" etc.

- **Reuso:** `StorageService.list_objects()` + a lógica de `document_resolver.py` (`resolve_document_request`) para casar a referência (incl. pronomes/contexto) com um objeto do bucket; gera signed URL. Se ambíguo, devolve ao modelo a lista de candidatos para ele perguntar ao usuário (mesma UX da Fase 6).
- **Substitui** o bloco de download pós‑resposta hoje hardcoded no `chat_stream` (passa a ser decisão do agente).

---

## 6. Integração no endpoint, persona e plano incremental

### 6.1 `chat_stream` (chat.py)
- Substituir o bloco `if use_smalltalk_gate / else LightRAG` por **uma** chamada a `AgentService.run_stream(...)`, que devolve o **mesmo gerador de tuplas** já consumido pela seção "2. Processar Resposta". Mínima mudança no resto do endpoint.
- **Smalltalk gate continua como fast‑path** (antes do agente): turnos 100% sociais não pagam o round‑trip de decisão de skills. `is_smalltalk()` e seus testes permanecem válidos.
- O bloco de download pós‑resposta (hoje em `chat.py`) é **removido** — vira a skill `entregar_documento`.
- Emitir `tool_status` como evento SSE opcional (ex.: "🔧 Consultando os manuais…") melhora a percepção de latência durante o laço.

### 6.2 `Prompt.md` — novo "Protocolo de Skills"
Adicionar uma seção ao `Prompt.md` (lido a cada requisição, sem rebuild):
- Quando consultar a base de conhecimento (toda pergunta factual sobre manuais) e quando **não** (conversa social, perguntas sobre a própria Lina).
- A ancoragem estrita passa a se aplicar ao **resultado da skill** `consultar_base_conhecimento`: nada de afirmar o que ela não retornou.
- Geração de planilha/PDF é permitida e **não** dispara o protocolo de negativa.
- Manter a blindagem (não falar de arquitetura/LLM) e a regra de nunca inventar URLs (os links vêm das skills).

### 6.3 Plano incremental (ordem de execução)

| Passo | Entrega | Arquivos | Verificação |
|------|---------|----------|-------------|
| 8.0 | Convenção de Skill + loader + tipos | `backend/skills/`, `agent/types.py`, `agent/skill_loader.py`, `agent/tool_registry.py` | loader descobre 1 skill dummy → monta schema + dispatch |
| 8.1 | Método `chat(messages, tools)` na camada de modelos | `src/IA/Models/ollama.py`, `openai.py` | teste unit com mock acumulando `tool_calls` fragmentadas |
| 8.2 | Laço `AgentService.run_stream` (+ disclosure sob demanda) | `agent/agent_service.py` | modelo *fake* que pede 1 skill e depois responde |
| 8.3 | Skill `consultar_base_conhecimento` (+ variante não‑stream do LightRAG) | `backend/skills/consultar_base_conhecimento/`, `lightrag_service.py` | pergunta factual → fonte citada no `done` |
| 8.4 | Skill `gerar_planilha` | `backend/skills/gerar_planilha/` | "monte uma planilha com X" → `.xlsx` baixável |
| 8.5 | Skill `gerar_documento_pdf` (+ deps no Dockerfile) | `backend/skills/gerar_documento_pdf/`, `backend/Dockerfile` | "gere um PDF de Y" → PDF baixável |
| 8.6 | Skill `entregar_documento` (reuso do resolver) | `backend/skills/entregar_documento/` | "me envia o manual do coordenador" → signed URL |
| 8.7 | Integração no endpoint + Prompt.md (Protocolo de Skills) | `chat.py`, `src/IA/Prompt.md` | regressão: factual, social, download, geração |
| 8.8 | Observabilidade: persistir skills chamadas no `metadata` | `chat.py`/repo | histórico mostra quais skills rodaram (auditoria) |
| 8.9 | **Matriz model‑agnostic:** rodar a bateria com 2–3 modelos locais | (harness de teste) | gpt‑oss vs qwen3 vs mistral: qualidade de tool calling + artefatos idênticos |

**Config nova** (`app/core/config.py`): `AGENT_ENABLED: bool = False`, `MAX_TOOL_STEPS: int = 5`, `TOOL_TIMEOUT_S: int = 60`, `SKILLS_DIR: Path` (default `backend/skills`), `SKILL_INSTRUCTIONS_MODE: str = "preamble"` (`preamble` | `on_demand`). Manter `AGENT_ENABLED=false` permite rollback instantâneo para o fluxo atual durante a transição.

---

## 7. Riscos e mitigações

- **Modelo "esquece" de chamar a base e responde de cabeça** → ancoragem forte no Prompt + few‑shot de quando chamar a skill; `temperature=0.2`.
- **Laço infinito / custo** → `MAX_TOOL_STEPS` + timeout por skill + log de passos.
- **`tool_calls` fragmentadas no stream** → acumular por `index` antes do `json.loads` (ver §4.4).
- **Variância de function calling entre modelos locais** → matriz de modelos (passo 8.9); poucas skills com descrições afiadas; disclosure; fallback JSON‑mode/ReAct p/ modelos sem FC nativo.
- **Qualidade de tool calling do gpt‑oss em PT** → validar BFCL‑style local; se fraco, Qwen3 (líder em FC — ver §7 do ROADMAP).
- **Latência percebida** maior (laço multi‑etapa) → emitir `tool_status`; manter smalltalk fast‑path.
- **WeasyPrint pesado no Docker** → fallback `fpdf2`.
- **Segurança do loader** → só carregar skills do próprio repo (confiáveis); `kind: script` é **rejeitado** enquanto não houver sandbox (Fase 10).

---

## 8. Fora do escopo desta fase (crescimento futuro)
- **Skills `kind: script` + sandbox de execução de código** (o modelo escreve/roda código; permite rodar/adaptar as skills oficiais `pdf`/`xlsx`/`docx` da Anthropic): **Fase 10** (governança/segurança/auditoria). O contrato de skill já acomoda — entram **sem mexer no laço**.
- **Visão/multimodalidade** (ler prints, PDFs escaneados): **Fase 9** — modelo multimodal co‑hospedado (ex.: Mistral Small 3.2) ou gpt‑oss + `qwen3-vl` sob demanda (ver tabela de modelos no ROADMAP).
- **MCP (Model Context Protocol)**: expor as skills como servidor MCP a outros clientes — e, no inverso, consumir tools MCP externas como skills — backlog.
- **Vendorizar/submodular `anthropics/skills`**: só se um dia formos rodar as oficiais (exige code‑exec); hoje é **referência** de estrutura e know‑how.

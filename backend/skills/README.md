# Skills do agente (Fase 8)

Cada **skill** é uma capacidade do agente, empacotada como **uma pasta** aqui em
`backend/skills/`. O agente as descobre por um *loader* e as expõe ao laço de
tool calling como ferramentas tipadas. **Skill nova = pasta nova** — sem tocar no
laço, no endpoint nem no registry.

Convenção inspirada nas [Anthropic Agent Skills](https://github.com/anthropics/skills).
Plano completo: [`docs/plano-agente-tool-calling.md`](../../docs/plano-agente-tool-calling.md).

## Estrutura de uma skill

```
backend/skills/<nome_da_skill>/
├── SKILL.md      # frontmatter (contrato) + corpo (instruções, sob demanda)
└── handler.py    # callable Python determinístico (kind: native)
```

## `SKILL.md`

```markdown
---
name: gerar_planilha
description: "Gera uma planilha .xlsx a partir de dados e devolve link de download. Use quando pedirem tabela/planilha/exportação."
kind: native                     # native (handler Python) | script (sandbox -> Fase 10)
handler: handler.py:executar     # 'arquivo.py:funcao' (apenas kind=native)
parameters:                      # JSON Schema dos argumentos (vai no tools=)
  type: object
  properties:
    titulo:  { type: string }
    colunas: { type: array, items: { type: string } }
    linhas:  { type: array, items: { type: array, items: { type: string } } }
  required: [titulo, colunas, linhas]
---

# Instruções (carregadas SOB DEMANDA — disclosure progressivo)

Como usar, exemplos, formatação, casos de borda… Este corpo **não** vai no
system prompt; é injetado quando a skill entra em jogo.
```

- **`description` é curta** (uma linha): é o que sempre fica no `tools=`. As
  instruções ricas ficam no corpo.
- **`parameters`** é o JSON Schema que vira o schema da função.
- **`kind: script`** (modelo escreve/roda código) exige sandbox e é **rejeitado**
  pelo loader até a Fase 10.

## `handler.py` (kind: native)

```python
from src.chatbot_fai_docs.agent.types import AgentContext, SkillResult

def executar(args: dict, ctx: AgentContext) -> SkillResult:
    """args: validado contra o JSON Schema do SKILL.md.
       ctx:  config, StorageService, histórico e coletor de efeitos colaterais."""
    ...
    return SkillResult(
        for_model="Planilha gerada com 12 linhas.",   # texto que volta ao modelo
        sources=[],                                     # citações -> evento `done`
        downloads=[("planilha.xlsx", signed_url)],      # chips de download -> `done`
    )
```

- O retorno canônico é `SkillResult`; por conveniência, o registry também aceita
  um `dict` (`{"for_model", "sources", "downloads", "error"}`) ou uma `str`.
- Erros e timeout **não** derrubam o laço: viram um `SkillResult(error=True)` cujo
  texto volta ao modelo.

## Como o agente usa

`AgentService` (em `src/chatbot_fai_docs/agent/`) recebe o modelo (Ollama/OpenAI)
e um `ToolRegistry` montado a partir desta pasta, e roda o laço até o modelo
redigir a resposta final. Tudo atrás da flag `AGENT_ENABLED` (padrão `False`).

Teste de fundação (roda no host, sem Docker):

```bash
python3 backend/src/chatbot_fai_docs/agent/test_agent.py
```

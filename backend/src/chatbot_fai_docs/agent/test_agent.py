"""Teste de fundacao do agente (Fase 8): loader -> registry -> laco, com um
modelo FAKE (sem depender de openai/pydantic). Roda no host:

    python3 backend/src/chatbot_fai_docs/agent/test_agent.py

Importa o pacote `agent` como TOP-LEVEL (adicionando .../chatbot_fai_docs ao
path) para nao disparar o __init__ pesado de `chatbot_fai_docs` (que puxa
RagService e, com ele, openai/sentence-transformers).
"""
import sys
import tempfile
from pathlib import Path

# .../src/chatbot_fai_docs  -> permite `import agent...` como top-level
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.agent_service import AgentService, to_openai_tool_calls  # noqa: E402
from agent.skill_loader import _parse_skill_md, load_skills  # noqa: E402
from agent.tool_registry import ToolRegistry  # noqa: E402
from agent.types import AgentContext, SkillResult  # noqa: E402

ECHO_SKILL_MD = """---
name: echo
description: "Repete o texto recebido (skill de teste)."
kind: native
handler: handler.py:executar
parameters:
  type: object
  properties:
    texto: { type: string, description: "Texto a repetir." }
  required: [texto]
---

# Instrucoes
Skill de teste. Devolve o texto recebido prefixado por "echo:".
"""

ECHO_HANDLER_PY = '''def executar(args, ctx):
    return {
        "for_model": "echo: " + str(args.get("texto", "")),
        "sources": ["Fonte: teste.pdf"],
    }
'''


class FakeModel:
    """1a chamada: pede a skill `echo`. 2a chamada (com resultado de tool ja
    presente nas mensagens): redige a resposta final."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if not has_tool_result:
            yield ("thought", "preciso chamar echo")
            yield ("usage", 5)
            yield ("tool_calls", [{"id": "call_1", "name": "echo", "arguments": {"texto": "oi"}}])
        else:
            yield ("answer", "Resultado final: ")
            yield ("answer", "feito.")
            yield ("usage", 7)


def _make_skill_dir(base: Path) -> Path:
    d = base / "echo"
    d.mkdir()
    (d / "SKILL.md").write_text(ECHO_SKILL_MD, encoding="utf-8")
    (d / "handler.py").write_text(ECHO_HANDLER_PY, encoding="utf-8")
    return base


def main():
    failures = []

    def check(cond, msg):
        print(("OK   " if cond else "FALHA ") + msg)
        if not cond:
            failures.append(msg)

    # --- parsing do frontmatter ---
    meta, body = _parse_skill_md(ECHO_SKILL_MD)
    check(meta.get("name") == "echo", "frontmatter: name lido")
    check(meta["parameters"]["required"] == ["texto"], "frontmatter: parameters aninhado preservado")
    check("Instrucoes" in body, "frontmatter: corpo separado do frontmatter")

    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = _make_skill_dir(Path(tmp))

        # --- loader ---
        skills = load_skills(skills_dir)
        check("echo" in skills, "loader: skill 'echo' descoberta")
        check(callable(skills["echo"].handler), "loader: handler importado (callable)")

        # --- registry / schema ---
        reg = ToolRegistry(skills, tool_timeout_s=5)
        schemas = reg.schemas
        check(
            len(schemas) == 1 and schemas[0]["function"]["name"] == "echo",
            "registry: schema OpenAI montado",
        )

        # --- dispatch direto ---
        ctx = AgentContext()
        res = reg.dispatch("echo", {"texto": "abc"}, ctx)
        check(
            isinstance(res, SkillResult) and res.for_model == "echo: abc",
            "registry: dispatch executa o handler",
        )
        check(reg.dispatch("naoexiste", {}, ctx).error, "registry: skill desconhecida -> erro")

        # --- laco completo com modelo fake ---
        fake = FakeModel()
        svc = AgentService(fake, reg, max_steps=5)
        ctx2 = AgentContext()
        events = list(svc.run_stream("diga oi", [], ctx2))
        answers = [p for k, p in events if k == "answer"]
        check(fake.calls == 2, "laco: modelo chamado 2x (tool -> resposta)")
        check(("tool_status", "echo") in events, "laco: emitiu tool_status da skill")
        check(
            bool(answers) and answers[-1] == "Resultado final: feito.",
            "laco: resposta final bufferizada corretamente",
        )
        check("Fonte: teste.pdf" in ctx2.sources, "laco: sources coletadas no ctx")

    # --- conversao p/ formato OpenAI ---
    oc = to_openai_tool_calls([{"id": "x", "name": "echo", "arguments": {"a": 1}}])
    check(
        oc[0]["type"] == "function" and oc[0]["function"]["arguments"] == '{"a": 1}',
        "to_openai_tool_calls: argumentos serializados em JSON",
    )

    print()
    if failures:
        print(f"=== {len(failures)} FALHA(S) ===")
        sys.exit(1)
    print("=== TODOS OS CHECKS PASSARAM ===")


if __name__ == "__main__":
    main()

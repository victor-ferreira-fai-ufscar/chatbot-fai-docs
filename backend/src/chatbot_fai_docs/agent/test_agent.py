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

from agent.agent_service import (  # noqa: E402
    AgentService,
    sanitize_harmony,
    to_openai_tool_calls,
    _HARMONY_FALLBACK,
)
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


class LeakyHarmonyModel:
    """Simula um modelo que VAZA o raciocinio (formato 'harmony') no `content` do
    turno final — reproduzindo o fluxo que disparava o bug: 1a chamada pede uma
    skill ('me envia o documento'), 2a chamada redige a resposta final, mas o
    raciocinio escapa fragmentado via content (como o Ollama as vezes faz)."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if not has_tool_result:
            yield ("tool_calls", [{"id": "c1", "name": "echo", "arguments": {"texto": "manual"}}])
        else:
            # vazamento degradado (a): thought\n{raciocinio}<channel|>{final}
            yield ("answer", "thought\n")
            yield ("answer", "The user wants the document. Plan: send the link.")
            yield ("answer", "<channel|>")
            yield ("answer", "Aqui esta o seu documento: http://x/manual.pdf")


class GreetingThenSkillModel:
    """Reproduz o bug Alberto Q2: 1a chamada responde SAUDACAO sem tools a uma
    pergunta factual (viola o guard de grounding); recebida a corretiva, chama a
    skill; com o resultado, redige a resposta final fundamentada."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        has_corrective = any(
            m.get("role") == "user" and "verificacao automatica" in str(m.get("content", ""))
            for m in messages
        )
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if has_tool_result:
            yield ("answer", "O prazo e 30 dias. > Fonte: [teste.pdf, pag. 1]")
        elif has_corrective:
            yield ("tool_calls", [{"id": "c1", "name": "echo", "arguments": {"texto": "prazo"}}])
        else:
            yield ("answer", "Ola! Sou a Lina. Como posso ajudar?")


class StubbornModel:
    """SEMPRE responde sem tools e sem fonte (nunca se corrige) — exercita o
    esgotamento dos retries e o exhausted_fallback."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        yield ("answer", "Resposta teimosa sem fonte nenhuma.")


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

        # --- integracao: vazamento harmony NO turno final e sanitizado no run_stream ---
        leaky = LeakyHarmonyModel()
        svc2 = AgentService(leaky, reg, max_steps=5)
        ctx3 = AgentContext()
        ev = list(svc2.run_stream("me envia esse documento", [], ctx3))
        final = next((p for k, p in reversed(ev) if k == "answer"), None)
        check(leaky.calls == 2, "run_stream: tool -> resposta final (fluxo do bug)")
        check(
            final == "Aqui esta o seu documento: http://x/manual.pdf",
            "run_stream: resposta final sanitizada (integracao)",
        )
        check(
            final is not None
            and "thought" not in final
            and "channel" not in final
            and "The user wants" not in final,
            "run_stream: nenhum artefato harmony chega ao usuario",
        )

        # --- guard de grounding: corretiva -> consulta -> resposta fundamentada ---
        def _checker(final_text, actx):
            # Simula o guard nao-social do endpoint: sem fontes/downloads no turno
            # -> corretiva, independente do tamanho (pega a saudacao de 69 chars).
            if actx.sources or actx.downloads:
                return None
            return "ATENCAO (verificacao automatica): consulte a base antes de responder."

        gm = GreetingThenSkillModel()
        svc3 = AgentService(gm, reg, max_steps=5, grounding_checker=_checker,
                            max_grounding_retries=2)
        ctx4 = AgentContext()
        ev3 = list(svc3.run_stream("qual o prazo de matricula?", [], ctx4))
        final3 = next((p for k, p in reversed(ev3) if k == "answer"), None)
        check(gm.calls == 3, "guard: saudacao -> corretiva -> skill -> resposta (3 chamadas)")
        check(("tool_status", "verificando_fontes") in ev3, "guard: emitiu tool_status do retry")
        check(final3 is not None and "Fonte" in final3, "guard: resposta final fundamentada")
        check(ctx4.extras.get("skills_called") == ["echo"], "guard: skills_called rastreado no ctx")

        # --- guard: retries esgotados SEM fallback -> aceita a ultima resposta ---
        sm = StubbornModel()
        svc4 = AgentService(sm, reg, max_steps=5, grounding_checker=_checker,
                            max_grounding_retries=2)
        ev4 = list(svc4.run_stream("pergunta factual", [], AgentContext()))
        final4 = next((p for k, p in reversed(ev4) if k == "answer"), None)
        check(sm.calls == 3, "guard: 1 chamada + 2 retries = 3 (contador respeitado)")
        check(final4 == "Resposta teimosa sem fonte nenhuma.",
              "guard: sem strict-fail, ultima resposta e aceita")

        # --- guard: retries esgotados COM exhausted_fallback -> substitui a resposta ---
        sm2 = StubbornModel()
        svc5 = AgentService(sm2, reg, max_steps=5, grounding_checker=_checker,
                            max_grounding_retries=2,
                            exhausted_fallback=lambda t, c: "TOKEN_NEGATIVA_TESTE")
        ev5 = list(svc5.run_stream("pergunta factual", [], AgentContext()))
        final5 = next((p for k, p in reversed(ev5) if k == "answer"), None)
        check(final5 == "TOKEN_NEGATIVA_TESTE", "guard: strict-fail substitui pela negativa")

        # --- guard: checker liberando (ex.: pergunta social) -> zero retry ---
        gm2 = GreetingThenSkillModel()
        svc6 = AgentService(gm2, reg, max_steps=5, grounding_checker=lambda t, c: None,
                            max_grounding_retries=2)
        ev6 = list(svc6.run_stream("bom dia", [], AgentContext()))
        final6 = next((p for k, p in reversed(ev6) if k == "answer"), None)
        check(gm2.calls == 1 and final6 == "Ola! Sou a Lina. Como posso ajudar?",
              "guard: social passa direto (sem retry)")

        # --- regressao: skill de geracao sem consulta NAO dispara o guard ---
        # (o checker real libera por actx.downloads; simulamos coletando um download)
        fake2 = FakeModel()
        svc7 = AgentService(fake2, reg, max_steps=5, grounding_checker=_checker,
                            max_grounding_retries=2)
        ctx7 = AgentContext()
        ev7 = list(svc7.run_stream("gera um pdf disso", [], ctx7))
        final7 = next((p for k, p in reversed(ev7) if k == "answer"), None)
        check(fake2.calls == 2 and final7 == "Resultado final: feito.",
              "guard: skill com fontes no turno passa sem retry")

        # --- guard: corretiva no ULTIMO passo do laco NAO descarta a resposta ---
        # (finding da revisao adversarial: o `continue` na ultima iteracao caia no
        # fallback generico "Nao consegui concluir..." jogando fora o buffer)
        sm3 = StubbornModel()
        svc8 = AgentService(sm3, reg, max_steps=2, grounding_checker=_checker,
                            max_grounding_retries=2)
        ev8 = list(svc8.run_stream("pergunta factual", [], AgentContext()))
        final8 = next((p for k, p in reversed(ev8) if k == "answer"), None)
        check(sm3.calls == 2 and final8 == "Resposta teimosa sem fonte nenhuma.",
              "guard: sem passo restante, entrega a resposta em vez do generico")

        # --- guard: skill que FALHOU registra skill_errors no ctx ---
        class FailingSkillModel:
            def __init__(self):
                self.calls = 0
            def chat(self, messages, tools=None):
                self.calls += 1
                if not any(m.get("role") == "tool" for m in messages):
                    yield ("tool_calls", [{"id": "c9", "name": "naoexiste", "arguments": {}}])
                else:
                    yield ("answer", "Houve um erro ao executar a ferramenta.")

        fsm = FailingSkillModel()
        # checker que reproduz a liberacao real por skill_errors
        def _checker_err(final_text, actx):
            if actx.extras.get("skill_errors"):
                return None
            return _checker(final_text, actx)
        svc9 = AgentService(fsm, reg, max_steps=5, grounding_checker=_checker_err,
                            max_grounding_retries=2)
        ctx9 = AgentContext()
        ev9 = list(svc9.run_stream("gera a planilha", [], ctx9))
        final9 = next((p for k, p in reversed(ev9) if k == "answer"), None)
        check(ctx9.extras.get("skill_errors") == ["naoexiste"],
              "guard: skill com erro registrada em skill_errors")
        check(fsm.calls == 2 and final9 == "Houve um erro ao executar a ferramenta.",
              "guard: falha de skill libera o relato honesto (sem retry)")

    # --- sanitizacao do formato "harmony" (anti-vazamento de raciocinio) ---
    s = sanitize_harmony
    normal = "Ola! O prazo de matricula vai ate 10/07. Posso ajudar em algo mais?"
    check(s(normal) == normal, "harmony: resposta normal passa intacta")
    check(s("") == "", "harmony: string vazia inalterada")
    check(
        s("Final: o resultado e X.") == "Final: o resultado e X.",
        "harmony: 'Final:' sem marcadores nao e tocado",
    )
    proper = (
        "<|channel|>analysis<|message|>The user wants the deadline. Plan: reply.<|end|>"
        "<|start|>assistant<|channel|>final<|message|>O prazo e 10/07. 📎"
    )
    check(s(proper) == "O prazo e 10/07. 📎", "harmony: proper analysis+final -> so o final")
    check(
        s("<|channel|>analysis<|message|>The user wants...<|end|>") == _HARMONY_FALLBACK,
        "harmony: so analysis -> fallback (nao vaza raciocinio)",
    )
    check(
        s("<|channel|>commentary<|message|>vou checar<|end|><|channel|>final<|message|>Pronto.")
        == "Pronto.",
        "harmony: commentary+final -> so o final",
    )
    check(
        s("<|channel|>final<|message|>Pronto.<|return|>") == "Pronto.",
        "harmony: token de fim (<|return|>) removido",
    )
    deg_a = "thought\nThe user wants the manual. Plan: send link.<channel|>Aqui esta o manual: 📎 http://x"
    check(s(deg_a) == "Aqui esta o manual: 📎 http://x", "harmony: degradado (a) -> so o final")
    deg_b = "thought\n<channel|>The user wants the doc. Actually, looking at the instructions: I should..."
    check(s(deg_b) == _HARMONY_FALLBACK, "harmony: degradado (b) so raciocinio -> fallback")
    deg_multi = "thought\nr1 reasoning<channel|>r2 reasoning<channel|>Resposta final em PT"
    check(s(deg_multi) == "Resposta final em PT", "harmony: degradado multi-canal -> apos ultimo canal")

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

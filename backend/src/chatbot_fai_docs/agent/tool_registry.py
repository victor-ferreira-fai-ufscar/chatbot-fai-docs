"""Registry de Skills: monta os schemas para `tools=` e despacha chamadas para
os handlers, com validacao basica e timeout por execucao.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

from .skill_loader import Skill, load_skills
from .types import AgentContext, SkillResult


class ToolRegistry:
    def __init__(self, skills: dict[str, Skill], *, tool_timeout_s: int = 60):
        self._skills = skills
        self._timeout = tool_timeout_s

    @classmethod
    def from_dir(cls, skills_dir: str | Path, *, tool_timeout_s: int = 60) -> "ToolRegistry":
        return cls(load_skills(skills_dir), tool_timeout_s=tool_timeout_s)

    @property
    def schemas(self) -> list[dict]:
        """Lista de schemas (so name + description curta + parameters) p/ `tools=`."""
        return [s.tool_schema() for s in self._skills.values()]

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def instructions_for(self, name: str) -> str:
        """Corpo do SKILL.md (instrucoes carregadas sob demanda)."""
        skill = self._skills.get(name)
        return skill.instructions if skill else ""

    def dispatch(self, name: str, arguments: dict, ctx: AgentContext) -> SkillResult:
        """Executa a skill `name`. Erros e timeout viram um SkillResult de erro
        (texto que volta ao modelo), nunca uma excecao que derruba o laco."""
        skill = self._skills.get(name)
        if skill is None:
            return SkillResult(for_model=f"Erro: skill desconhecida '{name}'.", error=True)

        args = arguments if isinstance(arguments, dict) else {}
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(skill.handler, args, ctx)
            result = future.result(timeout=self._timeout)
        except FuturesTimeout:
            executor.shutdown(wait=False, cancel_futures=True)
            return SkillResult(
                for_model=f"Erro: a skill '{name}' excedeu o tempo limite ({self._timeout}s).",
                error=True,
            )
        except Exception as e:  # noqa: BLE001 - qualquer falha do handler vira msg p/ o modelo
            executor.shutdown(wait=False, cancel_futures=True)
            return SkillResult(for_model=f"Erro ao executar a skill '{name}': {e}", error=True)
        executor.shutdown(wait=False)
        return self._normalize(result)

    @staticmethod
    def _normalize(result) -> SkillResult:
        """Aceita SkillResult (canonico), dict ou str -> SkillResult."""
        if isinstance(result, SkillResult):
            return result
        if isinstance(result, dict):
            return SkillResult(
                for_model=str(result.get("for_model", "")),
                sources=list(result.get("sources", []) or []),
                downloads=list(result.get("downloads", []) or []),
                error=bool(result.get("error", False)),
            )
        return SkillResult(for_model=str(result))

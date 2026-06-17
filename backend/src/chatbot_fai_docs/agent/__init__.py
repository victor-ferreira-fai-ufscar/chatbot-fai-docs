"""Pacote do agente (Fase 8): laco de tool calling nativo + Skills.

Depende apenas de stdlib + PyYAML; o modelo (Ollama/OpenAI) e INJETADO no
AgentService, mantendo o laco model-agnostic e testavel isoladamente (sem
importar openai/pydantic). Ver docs/plano-agente-tool-calling.md.
"""
from .types import AgentContext, SkillResult
from .skill_loader import Skill, load_skills, load_skill_dir
from .tool_registry import ToolRegistry
from .agent_service import AgentService, to_openai_tool_calls, history_to_messages

__all__ = [
    "AgentContext",
    "SkillResult",
    "Skill",
    "load_skills",
    "load_skill_dir",
    "ToolRegistry",
    "AgentService",
    "to_openai_tool_calls",
    "history_to_messages",
]

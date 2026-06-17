"""Loader de Skills: varre `backend/skills/*/SKILL.md`, faz parse do frontmatter
YAML (convencao das Anthropic Agent Skills) e importa o handler de cada skill.

Cada skill = uma pasta com:
  - SKILL.md  -> frontmatter (name, description, kind, handler, parameters) + corpo
                 (instrucoes carregadas sob demanda; ver disclosure progressivo).
  - handler.py (kind=native) -> callable executar(args: dict, ctx) -> SkillResult.

Skills `kind: script` (modelo escreve/roda codigo) exigem sandbox -> Fase 10:
o loader as REJEITA por enquanto.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

FRONTMATTER_DELIM = "---"


@dataclass
class Skill:
    name: str
    description: str
    kind: str
    parameters: dict
    instructions: str
    handler: Callable | None  # callable para kind=native
    path: Path

    def tool_schema(self) -> dict:
        """Schema no formato `tools=` da API OpenAI/Ollama."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


def _parse_skill_md(text: str) -> tuple[dict, str]:
    """Separa o frontmatter YAML (entre linhas '---') do corpo (instrucoes)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError("SKILL.md sem frontmatter YAML (esperado '---' na 1a linha)")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            end = i
            break
    if end is None:
        raise ValueError("SKILL.md com frontmatter nao fechado (faltou '---')")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter do SKILL.md nao e um mapa YAML")
    body = "\n".join(lines[end + 1:]).strip()
    return meta, body


def _load_handler(skill_dir: Path, handler_spec: str) -> Callable:
    """handler_spec = 'arquivo.py:funcao'. Importa por caminho (importlib)."""
    if ":" not in handler_spec:
        raise ValueError(f"handler invalido '{handler_spec}' (use 'arquivo.py:funcao')")
    file_part, func_name = handler_spec.split(":", 1)
    handler_path = skill_dir / file_part
    if not handler_path.exists():
        raise FileNotFoundError(f"handler nao encontrado: {handler_path}")
    mod_name = f"_skill_{skill_dir.name}_{handler_path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, handler_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"nao foi possivel preparar o import de {handler_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    fn = getattr(module, func_name, None)
    if not callable(fn):
        raise AttributeError(f"funcao '{func_name}' nao encontrada em {handler_path}")
    return fn


def load_skill_dir(skill_dir: Path) -> Skill:
    """Carrega uma unica pasta de skill. Levanta excecao se invalida/kind=script."""
    meta, body = _parse_skill_md((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    name = meta.get("name") or skill_dir.name
    kind = (meta.get("kind") or "native").strip()
    description = (meta.get("description") or "").strip()
    parameters = meta.get("parameters") or {"type": "object", "properties": {}}

    if kind == "script":
        raise NotImplementedError(
            f"skill '{name}' e kind=script; execucao em sandbox so na Fase 10"
        )
    if kind != "native":
        raise ValueError(f"skill '{name}' com kind desconhecido: {kind!r}")

    handler_spec = meta.get("handler")
    if not handler_spec:
        raise ValueError(f"skill '{name}' (kind=native) sem 'handler' no frontmatter")
    handler = _load_handler(skill_dir, handler_spec)

    return Skill(
        name=name,
        description=description,
        kind=kind,
        parameters=parameters,
        instructions=body,
        handler=handler,
        path=skill_dir,
    )


def load_skills(skills_dir: str | Path) -> dict[str, Skill]:
    """Varre <skills_dir>/*/SKILL.md e devolve {name: Skill}.

    Skills invalidas (ou kind=script) sao PULADAS com aviso, sem derrubar o resto.
    """
    base = Path(skills_dir)
    skills: dict[str, Skill] = {}
    if not base.exists():
        return skills
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").exists():
            continue
        try:
            skill = load_skill_dir(child)
        except NotImplementedError as e:
            print(f"[skill_loader] pulando '{child.name}': {e}")
            continue
        except Exception as e:  # noqa: BLE001 - uma skill ruim nao pode derrubar as demais
            print(f"[skill_loader] ERRO ao carregar '{child.name}': {e}")
            continue
        skills[skill.name] = skill
    return skills

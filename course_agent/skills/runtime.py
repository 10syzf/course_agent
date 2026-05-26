"""Local Skill Runtime（Task 013）."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from course_agent.capabilities.base import CapabilityCallResult, CapabilityKind, CapabilitySpec
from course_agent.logger import get_logger
from course_agent.observability.metrics import track_capability_call

_log = get_logger("SkillRuntime")


class SkillContext(BaseModel):
    """Skill 执行上下文."""

    meta: dict[str, Any] = Field(default_factory=dict)


@dataclass
class Skill:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]
    tags: list[str]

    def to_capability_spec(self) -> CapabilitySpec:
        return CapabilitySpec(
            name=self.name,
            kind=CapabilityKind.SKILL,
            description=self.description,
            parameters=self.parameters,
            source="skills",
            tags=self.tags,
        )


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill 已存在: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Skill 未注册: {name}")
        return self._skills[name]

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def list_names(self) -> list[str]:
        return list(self._skills.keys())


_global_skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    return _global_skill_registry


def skill(
    *,
    name: str,
    description: str,
    parameters: dict[str, Any],
    tags: list[str] | None = None,
    registry: SkillRegistry | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        (registry or _global_skill_registry).register(
            Skill(
                name=name,
                description=description,
                parameters=parameters,
                func=func,
                tags=tags or [],
            )
        )
        return func

    return decorator


class LocalSkillProvider:
    provider_name = "skills"

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or get_skill_registry()

    def list_capabilities(self) -> list[CapabilitySpec]:
        return [s.to_capability_spec() for s in self.registry.all()]

    async def call(
        self, name: str, arguments: dict[str, Any]
    ) -> CapabilityCallResult:
        sk = self.registry.get(name)
        ctx = SkillContext(meta={})
        with track_capability_call(
            capability_name=name,
            capability_kind=CapabilityKind.SKILL.value,
            provider_name=self.provider_name,
        ) as rec:
            t0 = time.perf_counter()
            try:
                result = sk.func(ctx=ctx, **arguments)
                if isinstance(result, Awaitable):
                    result = await result
            except Exception as e:  # noqa: BLE001
                rec.status = "error"
                rec.error = f"{type(e).__name__}: {str(e)[:300]}"
                raise
            latency = int((time.perf_counter() - t0) * 1000)
            return CapabilityCallResult(
                capability_name=name,
                kind=CapabilityKind.SKILL,
                ok=True,
                output=str(result),
                latency_ms=latency,
            )


__all__ = [
    "LocalSkillProvider",
    "Skill",
    "SkillContext",
    "SkillRegistry",
    "get_skill_registry",
    "skill",
]

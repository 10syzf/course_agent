"""Capability 注册中心（Task 013）."""

from __future__ import annotations

from typing import Any

from course_agent.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCallResult,
    CapabilityKind,
    CapabilitySpec,
)


class CapabilityRegistry:
    """统一管理 internal_tool / skill / mcp 三类能力."""

    def __init__(self) -> None:
        self._providers: list[BaseCapabilityProvider] = []

    def register_provider(self, provider: BaseCapabilityProvider) -> None:
        names = {p.provider_name for p in self._providers}
        if provider.provider_name in names:
            raise ValueError(f"Capability provider 已存在: {provider.provider_name}")
        self._providers.append(provider)

    def providers(self) -> list[BaseCapabilityProvider]:
        return list(self._providers)

    def list_all(self) -> list[CapabilitySpec]:
        out: list[CapabilitySpec] = []
        seen: set[tuple[CapabilityKind, str]] = set()
        for p in self._providers:
            for spec in p.list_capabilities():
                key = (spec.kind, spec.name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(spec)
        out.sort(key=lambda x: (x.kind.value, x.name))
        return out

    def list_by_kind(self, kind: CapabilityKind) -> list[CapabilitySpec]:
        return [s for s in self.list_all() if s.kind == kind]

    def list_enabled(self) -> list[CapabilitySpec]:
        return [s for s in self.list_all() if s.enabled]

    def get(self, name: str) -> CapabilitySpec | None:
        for spec in self.list_all():
            if spec.name == name:
                return spec
        return None

    def call_provider_for(self, name: str) -> BaseCapabilityProvider | None:
        for provider in self._providers:
            if any(spec.name == name for spec in provider.list_capabilities()):
                return provider
        return None

    async def call(
        self, name: str, arguments: dict[str, Any]
    ) -> CapabilityCallResult:
        provider = self.call_provider_for(name)
        if provider is None:
            raise KeyError(f"Capability 未注册: {name}")
        return await provider.call(name, arguments)


_global_cap_registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    return _global_cap_registry


__all__ = ["CapabilityRegistry", "get_capability_registry"]

"""Capability Registry 单测（Task 013）."""

from __future__ import annotations

import pytest

from course_agent.capabilities import CapabilityKind, CapabilityRegistry, CapabilitySpec


class _P1:
    provider_name = "p1"

    def list_capabilities(self):
        return [
            CapabilitySpec(name="a", kind=CapabilityKind.INTERNAL_TOOL),
            CapabilitySpec(name="b", kind=CapabilityKind.SKILL),
        ]

    async def call(self, name, arguments):
        raise NotImplementedError


class _P2:
    provider_name = "p2"

    def list_capabilities(self):
        return [
            CapabilitySpec(name="c", kind=CapabilityKind.MCP, enabled=False),
            CapabilitySpec(name="b", kind=CapabilityKind.SKILL),  # duplicate
        ]

    async def call(self, name, arguments):
        raise NotImplementedError


def test_registry_register_provider_and_list_all():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    rows = reg.list_all()
    assert [r.name for r in rows] == ["a", "b"]


def test_registry_rejects_duplicate_provider_name():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    with pytest.raises(ValueError, match="provider"):
        reg.register_provider(_P1())


def test_registry_deduplicates_same_kind_same_name():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    reg.register_provider(_P2())
    rows = reg.list_all()
    assert [r.name for r in rows].count("b") == 1


def test_registry_list_by_kind():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    reg.register_provider(_P2())
    skills = reg.list_by_kind(CapabilityKind.SKILL)
    assert len(skills) == 1
    assert skills[0].name == "b"


def test_registry_list_enabled_filters_disabled():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    reg.register_provider(_P2())
    enabled = reg.list_enabled()
    assert "c" not in [r.name for r in enabled]


def test_registry_get_and_missing():
    reg = CapabilityRegistry()
    reg.register_provider(_P1())
    assert reg.get("a") is not None
    assert reg.get("missing") is None

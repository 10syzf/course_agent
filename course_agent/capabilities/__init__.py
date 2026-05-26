"""统一能力层（Task 013）."""

from course_agent.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCallResult,
    CapabilityKind,
    CapabilitySpec,
)
from course_agent.capabilities.registry import (
    CapabilityRegistry,
    get_capability_registry,
)
from course_agent.capabilities.router import CapabilityRouter

__all__ = [
    "BaseCapabilityProvider",
    "CapabilityCallResult",
    "CapabilityKind",
    "CapabilityRegistry",
    "CapabilityRouter",
    "CapabilitySpec",
    "get_capability_registry",
]

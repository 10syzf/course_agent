"""Task 014：Chainlit orchestrator runtime 切换测试."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from course_agent.config import AgentConfig, AppConfig, LLMConfig, LoggingConfig, RuntimeConfig
from course_agent.mcp.config import MCPConfig
from course_agent.ui import chainlit_app


class _DummySession:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value


class _DummyMessage:
    sent: list[tuple[str, str]] = []

    def __init__(self, content: str = "", author: str = "", actions=None) -> None:
        self.content = content
        self.author = author
        self.actions = actions or []

    async def send(self):
        _DummyMessage.sent.append((self.author, self.content))
        return self


class _DummyMemory:
    def __init__(self) -> None:
        self.long = None
        self.short = SimpleNamespace(max_turns=20, compress_trigger=16, llm=None)

    async def clear_short(self) -> None:
        return None


def _cfg() -> AppConfig:
    return AppConfig(
        llm=LLMConfig(provider="mock", model="mock-llm"),
        agent=AgentConfig(max_steps=6),
        runtime=RuntimeConfig(backend="langgraph", checkpoint="memory", draw_graph=True),
        mcp=MCPConfig(),
        logging=LoggingConfig(),
    )


@pytest.mark.asyncio
async def test_scene_action_orchestrator_switches_runtime(monkeypatch):
    session = _DummySession()
    session.set("cfg", _cfg())
    session.set("memory", None)
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app, "create_llm", lambda cfg: object())
    runtime_obj = SimpleNamespace(backend="langgraph")
    monkeypatch.setattr(chainlit_app, "create_runtime", lambda *a, **k: runtime_obj)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    _DummyMessage.sent.clear()

    await chainlit_app.on_scene_action(SimpleNamespace(payload={"scene": "orchestrator"}))

    assert session.get("agent_mode") == "orchestrator"
    assert session.get("agent") is runtime_obj
    assert session.get("history") == []


@pytest.mark.asyncio
async def test_scene_action_orchestrator_message_contains_backend(monkeypatch):
    session = _DummySession()
    session.set("cfg", _cfg())
    session.set("memory", None)
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app, "create_llm", lambda cfg: object())
    monkeypatch.setattr(chainlit_app, "create_runtime", lambda *a, **k: SimpleNamespace(backend="langgraph"))
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    _DummyMessage.sent.clear()

    await chainlit_app.on_scene_action(SimpleNamespace(payload={"scene": "orchestrator"}))

    assert _DummyMessage.sent
    assert "langgraph" in _DummyMessage.sent[-1][1]


@pytest.mark.asyncio
async def test_settings_update_rebuilds_orchestrator_runtime(monkeypatch):
    session = _DummySession()
    session.set("cfg", _cfg())
    session.set("scene", "orchestrator")
    session.set("memory", _DummyMemory())
    session.set("memory_enabled", False)
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app, "create_llm", lambda cfg: object())
    runtime_obj = SimpleNamespace(llm=object(), backend="langgraph")
    monkeypatch.setattr(chainlit_app, "create_runtime", lambda *a, **k: runtime_obj)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    _DummyMessage.sent.clear()

    await chainlit_app.on_settings_update(
        {"model": "mock-llm", "temperature": 0.3, "max_steps": 9, "memory_enabled": False}
    )

    assert session.get("agent") is runtime_obj
    assert session.get("cfg").agent.max_steps == 9


@pytest.mark.asyncio
async def test_settings_update_orchestrator_keeps_memory_object_when_flag_unchanged(monkeypatch):
    session = _DummySession()
    memory = _DummyMemory()
    session.set("cfg", _cfg())
    session.set("scene", "orchestrator")
    session.set("memory", memory)
    session.set("memory_enabled", False)
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app, "create_llm", lambda cfg: object())
    monkeypatch.setattr(
        chainlit_app,
        "create_runtime",
        lambda *a, **k: SimpleNamespace(llm=object(), backend="langgraph"),
    )
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)

    await chainlit_app.on_settings_update(
        {"model": "mock-llm", "temperature": 0.2, "max_steps": 6, "memory_enabled": False}
    )

    assert session.get("memory") is memory

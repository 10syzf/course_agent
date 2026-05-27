"""Task 015：Chainlit graph event / replay 摘要展示测试."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from course_agent.ui import chainlit_app


class _DummySession:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value


class _DummyMessage:
    sent: list[str] = []

    def __init__(self, content: str = "", author: str = "", actions=None) -> None:
        self.content = content
        self.author = author
        self.actions = actions or []

    async def send(self):
        _DummyMessage.sent.append(self.content)
        return self

    async def stream_token(self, token: str):
        self.content += token

    async def update(self):
        return self


class _DummyStep:
    outputs: list[str] = []

    def __init__(self, name: str = "", type: str = "") -> None:
        self.name = name
        self.type = type
        self.input = ""
        self.output = ""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _DummyStep.outputs.append(self.output)


class _GraphAgent:
    runtime_kind = "react_graph"
    backend = "langgraph"

    async def astream_run(self, user_input, history=None, callbacks=None):
        from course_agent.llm.base import StreamChunk

        self._last_replay = {
            "backend": "langgraph",
            "runtime_kind": "react_graph",
            "node_sequence": ["prepare_context", "llm", "finalize"],
            "steps": 2,
            "path": "/tmp/demo.json",
        }
        yield StreamChunk(delta_text="hello")
        yield StreamChunk(finish_reason="stop")

    async def arun(self, user_input, history=None, callbacks=None):
        return SimpleNamespace(answer="hello", steps=1, trace=[])

    def get_last_replay(self):
        return getattr(self, "_last_replay", None)


@pytest.mark.asyncio
async def test_on_message_react_graph_renders_graph_runtime_step(monkeypatch):
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))
    _DummyStep.outputs.clear()

    await chainlit_app.on_message(SimpleNamespace(content="你好", elements=[]))

    assert _DummyStep.outputs
    assert "react_graph" in _DummyStep.outputs[-1]
    assert "prepare_context -> llm -> finalize" in _DummyStep.outputs[-1]


@pytest.mark.asyncio
async def test_on_message_react_graph_step_contains_replay_path(monkeypatch):
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))
    _DummyStep.outputs.clear()

    await chainlit_app.on_message(SimpleNamespace(content="你好", elements=[]))

    assert "/tmp/demo.json" in _DummyStep.outputs[-1]


@pytest.mark.asyncio
async def test_on_message_non_graph_agent_does_not_render_graph_step(monkeypatch):
    class _LegacyAgent:
        async def astream_run(self, user_input, history=None, callbacks=None):
            from course_agent.llm.base import StreamChunk

            yield StreamChunk(delta_text="legacy")
            yield StreamChunk(finish_reason="stop")

        async def arun(self, user_input, history=None, callbacks=None):
            return SimpleNamespace(answer="legacy", steps=1, trace=[])

    session = _DummySession()
    session.set("agent", _LegacyAgent())
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))
    _DummyStep.outputs.clear()

    await chainlit_app.on_message(SimpleNamespace(content="你好", elements=[]))

    assert _DummyStep.outputs == []

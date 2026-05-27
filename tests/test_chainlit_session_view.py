"""Task 016：Chainlit session 任务态展示测试."""

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

    def get_last_replay(self):
        return {
            "backend": "langgraph",
            "runtime_kind": "react_graph",
            "node_sequence": ["start", "wait_human_input"],
            "steps": 1,
            "path": "/tmp/session-replay.json",
        }


class _SessionRuntime:
    def __init__(self, status: str = "waiting_human_input") -> None:
        self._status = status
        self.calls: list[tuple[str, str]] = []

    def get_session(self, session_id):
        if not session_id:
            return None
        return SimpleNamespace(session_id=session_id, status=SimpleNamespace(value=self._status))

    async def start(self, user_text, history=None, callbacks=None):
        self.calls.append(("start", user_text))
        return _result("s-1", self._status)

    async def continue_session(self, session_id, user_text, callbacks=None):
        self.calls.append(("continue", user_text))
        return _result(session_id, "completed")

    async def resume(self, session_id, callbacks=None):
        self.calls.append(("resume", session_id))
        return _result(session_id, "completed")


def _result(session_id: str, status: str):
    return SimpleNamespace(
        session=SimpleNamespace(
            session_id=session_id,
            status=status,
            waiting_reason="need input" if "waiting" in status else None,
            latest_replay_path="/tmp/session-replay.json",
        ),
        runtime_result=SimpleNamespace(answer="done" if status == "completed" else "waiting"),
    )


@pytest.mark.asyncio
async def test_on_message_react_graph_session_start_renders_task_step(monkeypatch):
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("session_runtime", _SessionRuntime("waiting_human_input"))
    session.set("task_session_id", None)
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))
    _DummyStep.outputs.clear()

    await chainlit_app.on_message(SimpleNamespace(content="这题我稍后补充资料", elements=[]))

    assert any("session_id=`s-1`" in item for item in _DummyStep.outputs)
    assert any("waiting_human_input" in item for item in _DummyStep.outputs)


@pytest.mark.asyncio
async def test_on_message_waiting_human_input_continues_existing_session(monkeypatch):
    runtime = _SessionRuntime("waiting_human_input")
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("session_runtime", runtime)
    session.set("task_session_id", "s-1")
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))

    await chainlit_app.on_message(SimpleNamespace(content="补充信息", elements=[]))

    assert runtime.calls[0][0] == "continue"


@pytest.mark.asyncio
async def test_on_message_waiting_approval_resumes_existing_session(monkeypatch):
    runtime = _SessionRuntime("waiting_approval")
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("session_runtime", runtime)
    session.set("task_session_id", "s-2")
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))

    await chainlit_app.on_message(SimpleNamespace(content="确认，继续", elements=[]))

    assert runtime.calls[0][0] == "resume"


@pytest.mark.asyncio
async def test_on_message_session_step_contains_replay_path(monkeypatch):
    session = _DummySession()
    session.set("agent", _GraphAgent())
    session.set("session_runtime", _SessionRuntime("waiting_human_input"))
    session.set("task_session_id", None)
    session.set("history", [])
    session.set("memory", None)
    session.set("agent_mode", "react")
    monkeypatch.setattr(chainlit_app.cl, "user_session", session)
    monkeypatch.setattr(chainlit_app.cl, "Message", _DummyMessage)
    monkeypatch.setattr(chainlit_app.cl, "Step", _DummyStep)
    monkeypatch.setattr(chainlit_app, "set_active_manager", lambda memory: None)
    monkeypatch.setattr(chainlit_app, "build_default_capability_registry", lambda **kwargs: SimpleNamespace(list_all=lambda: []))
    _DummyStep.outputs.clear()

    await chainlit_app.on_message(SimpleNamespace(content="这题我稍后补充资料", elements=[]))

    assert any("/tmp/session-replay.json" in item for item in _DummyStep.outputs)

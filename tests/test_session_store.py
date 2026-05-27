"""Task 016：session store 测试."""

from __future__ import annotations

from course_agent.session.models import SessionStatus, TaskSession
from course_agent.session.store import SessionStore


def test_session_store_creates_file_on_init(tmp_path):
    store = SessionStore(tmp_path)
    assert store.file_path.exists()
    assert store.list_sessions() == []


def test_session_store_save_and_get_session(tmp_path):
    store = SessionStore(tmp_path)
    session = TaskSession(title="demo", input="hello")
    store.save_session(session)
    got = store.get_session(session.session_id)
    assert got is not None
    assert got.title == "demo"


def test_session_store_overwrites_existing_session(tmp_path):
    store = SessionStore(tmp_path)
    session = TaskSession(title="demo", input="hello")
    store.save_session(session)
    session.set_status(SessionStatus.COMPLETED)
    store.save_session(session)
    got = store.get_session(session.session_id)
    assert got is not None
    assert got.status == SessionStatus.COMPLETED


def test_session_store_list_sessions_sorted_by_updated_at(tmp_path):
    store = SessionStore(tmp_path)
    a = TaskSession(title="a", input="a")
    b = TaskSession(title="b", input="b")
    store.save_session(a)
    b.touch()
    store.save_session(b)
    rows = store.list_sessions()
    assert rows[0].session_id == b.session_id


def test_session_store_delete_session(tmp_path):
    store = SessionStore(tmp_path)
    session = TaskSession(title="demo", input="hello")
    store.save_session(session)
    assert store.delete_session(session.session_id) is True
    assert store.get_session(session.session_id) is None

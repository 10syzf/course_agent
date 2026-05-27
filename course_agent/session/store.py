"""Task 016：Session 持久化存储."""

from __future__ import annotations

import json
from pathlib import Path

from course_agent.session.models import TaskSession


class SessionStore:
    """基于 JSON 文件的最小 SessionStore."""

    def __init__(self, session_dir: str | Path = "data/sessions") -> None:
        self.base_dir = Path(session_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.base_dir / "sessions.json"
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _load_rows(self) -> list[dict]:
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def _save_rows(self, rows: list[dict]) -> None:
        self.file_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_sessions(self) -> list[TaskSession]:
        """列出所有 session，按更新时间倒序."""
        items = [TaskSession.model_validate(row) for row in self._load_rows()]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get_session(self, session_id: str) -> TaskSession | None:
        """按 ID 获取 session."""
        for item in self.list_sessions():
            if item.session_id == session_id:
                return item
        return None

    def save_session(self, session: TaskSession) -> TaskSession:
        """创建或覆盖保存 session."""
        rows = self._load_rows()
        data = session.model_dump(mode="json")
        for idx, row in enumerate(rows):
            if row.get("session_id") == session.session_id:
                rows[idx] = data
                self._save_rows(rows)
                return session
        rows.append(data)
        self._save_rows(rows)
        return session

    def delete_session(self, session_id: str) -> bool:
        """删除一个 session."""
        rows = self._load_rows()
        new_rows = [row for row in rows if row.get("session_id") != session_id]
        changed = len(new_rows) != len(rows)
        if changed:
            self._save_rows(new_rows)
        return changed


__all__ = ["SessionStore"]

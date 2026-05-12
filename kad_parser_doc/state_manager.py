from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any, Optional


def _default_state_path() -> str:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(project_root, "script_state.json")


class StateManager:
    def __init__(self, state_path: Optional[str] = None) -> None:
        self._path = state_path or _default_state_path()
        self._lock = threading.Lock()
        with self._lock:
            self._ensure_file()

    def _read_unlocked(self) -> dict[str, Any]:
        if not os.path.isfile(self._path):
            return {"is_running": False, "current_task_id": None}
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"is_running": False, "current_task_id": None}
        is_running = bool(data.get("is_running", False))
        task_id = data.get("current_task_id")
        if task_id is not None and not isinstance(task_id, str):
            task_id = str(task_id)
        return {"is_running": is_running, "current_task_id": task_id}

    def _write_unlocked(self, state: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".",
            prefix=".script_state_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _ensure_file(self) -> None:
        if os.path.isfile(self._path):
            return
        initial = {"is_running": False, "current_task_id": None}
        self._write_unlocked(initial)

    def set_running(self, message_id: str) -> None:
        with self._lock:
            self._ensure_file()
            self._write_unlocked({"is_running": True, "current_task_id": message_id})

    def set_stopped(self) -> None:
        with self._lock:
            self._ensure_file()
            self._write_unlocked({"is_running": False, "current_task_id": None})

    def is_running(self) -> bool:
        with self._lock:
            self._ensure_file()
            return bool(self._read_unlocked()["is_running"])

    def get_current_task_id(self) -> Optional[str]:
        with self._lock:
            self._ensure_file()
            return self._read_unlocked()["current_task_id"]

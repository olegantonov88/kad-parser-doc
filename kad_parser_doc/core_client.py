from __future__ import annotations

from typing import Any, Optional

import requests

from .config import get_config
from .logging_utils import log_event


class CoreClient:
    def __init__(self) -> None:
        self.cfg = get_config()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.core_api_token:
            headers["Authorization"] = f"Bearer {self.cfg.core_api_token}"
        return headers

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        timeout_seconds: float = 60.0,
    ) -> tuple[bool, Optional[dict[str, Any]]]:
        url = self.cfg.core_api_url.rstrip("/") + path
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=timeout_seconds,
            )
            data: Optional[dict[str, Any]]
            try:
                raw_data = response.json()
                data = raw_data if isinstance(raw_data, dict) else None
            except Exception:
                data = None
            ok = bool(response.ok)
            event_payload: dict[str, Any] = {
                "path": path,
                "status": response.status_code,
                "ok": ok,
            }
            if not ok:
                event_payload["error_detail"] = data if data is not None else response.text
            log_event("core_post", event_payload)
            return ok, data
        except Exception as exc:
            log_event(
                "core_post_error",
                {"path": path, "message": str(exc), "exception_type": type(exc).__name__},
            )
            return False, None

    def notify_document_text(
        self,
        payload: dict[str, Any],
        require_success: bool,
    ) -> bool:
        path = "/api/parse-result/document-text/"
        ok, data = self.post(path, payload, timeout_seconds=60.0)
        success_val = data.get("success") if isinstance(data, dict) else None
        log_event("notify_document_text_result", {"ok": ok, "success": success_val})
        if not ok:
            return False
        if require_success:
            return bool(isinstance(data, dict) and data.get("success") is True)
        return True


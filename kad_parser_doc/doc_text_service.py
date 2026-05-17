from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from .config import get_config
from .logging_utils import log_event
from .models import DocFetchResult, QueueDocTask
from .selenium_utils import (
    apply_stealth,
    create_persistent_context,
    fetch_document_html_via_browser,
    get_or_create_page,
    wait_for_page_ready,
)


class BrowserManager:
    """Manages a Playwright browser in a dedicated single thread.

    Playwright sync API uses greenlets and must run in the thread where it was
    created. All browser operations are submitted to a ThreadPoolExecutor with
    max_workers=1, which guarantees they always run in the same thread.
    """

    def __init__(self) -> None:
        self.cfg = get_config()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pw = None
        self._context = None

    def _profile_dir(self) -> str:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        path = os.path.join(project_root, ".profiles", "pw-default")
        os.makedirs(path, exist_ok=True)
        return path

    def _ensure_context_in_thread(self) -> None:
        if self._context is not None:
            try:
                _ = self._context.pages
                return
            except Exception:
                self._context = None
                if self._pw is not None:
                    try:
                        self._pw.stop()
                    except Exception:
                        pass
                    self._pw = None

        self._pw, self._context = create_persistent_context(
            headless=self.cfg.headless,
            profile_dir=self._profile_dir(),
        )
        page = get_or_create_page(self._context)
        page.set_default_timeout(60_000)
        apply_stealth(page)
        page.goto(self.cfg.ras_base_url)
        wait_for_page_ready(page, timeout_ms=20_000)
        log_event("browser_started", {"status": "ok"})

    def _fetch_in_thread(self, doc_uuid: str) -> dict:
        self._ensure_context_in_thread()
        page = get_or_create_page(self._context)
        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""
        if "ras.arbitr.ru" not in current_url:
            page.goto(self.cfg.ras_base_url)
            wait_for_page_ready(page, timeout_ms=20_000)
        return fetch_document_html_via_browser(page, doc_uuid)

    def _close_in_thread(self) -> None:
        context, pw = self._context, self._pw
        self._context = None
        self._pw = None
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass
        log_event("browser_closed", {"status": "ok"})

    def fetch_document(self, doc_uuid: str) -> dict:
        return self._executor.submit(self._fetch_in_thread, doc_uuid).result()

    def close_browser(self) -> None:
        # Fire-and-forget: called from async event loop, must not block it.
        # The executor serialises this with any concurrent fetch, so state is safe.
        self._executor.submit(self._close_in_thread)


class DocTextService:
    def __init__(self, browser: BrowserManager) -> None:
        self.browser = browser
        self.cfg = get_config()

    def _check_ip(self) -> Optional[str]:
        if not self.cfg.check_ip_enabled or not self.cfg.check_ip_url:
            return None
        headers: dict[str, str] = {}
        if self.cfg.check_ip_bearer:
            headers["Authorization"] = f"Bearer {self.cfg.check_ip_bearer}"
        try:
            response = requests.get(self.cfg.check_ip_url, headers=headers, timeout=10)
            data = response.json() if response.ok else None
            if isinstance(data, dict):
                for key in ("ip", "client_ip", "remote_addr"):
                    if data.get(key):
                        return str(data[key])
        except Exception:
            pass
        return None

    def fetch_document_text(self, task: QueueDocTask) -> DocFetchResult:
        start_ip = self._check_ip()
        result = DocFetchResult(ok=False, message="unknown_error", start_ip=start_ip)
        try:
            raw = self.browser.fetch_document(task.doc_uuid)
            is_ok = bool(raw.get("ok"))
            status_code = int(raw.get("status") or 0)
            text = str(raw.get("text") or "")
            if is_ok and status_code == 200:
                result = DocFetchResult(
                    ok=True,
                    html=text,
                    start_ip=start_ip,
                )
            else:
                if status_code == 451:
                    message = "Ошибка 451"
                elif status_code == 429:
                    message = "Ошибка 429"
                elif status_code >= 500:
                    message = f"Ошибка загрузки документа: HTTP {status_code}"
                elif raw.get("error"):
                    message = str(raw.get("error"))
                else:
                    message = f"Ошибка получения текста: status={status_code}"
                result = DocFetchResult(ok=False, message=message, start_ip=start_ip)
        except Exception as exc:
            result = DocFetchResult(ok=False, message=str(exc), start_ip=start_ip)
        finally:
            log_event(
                "doc_fetch_completed",
                {
                    "job_uuid": task.job_uuid,
                    "doc_id": task.doc_id,
                    "doc_uuid": task.doc_uuid,
                    "start_ip": start_ip,
                },
            )
        return result

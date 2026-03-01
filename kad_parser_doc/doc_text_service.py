from __future__ import annotations

import base64
import os
import threading
from typing import Optional

import requests

from .config import get_config
from .logging_utils import log_event
from .models import DocFetchResult, QueueDocTask
from .selenium_utils import (
    apply_stealth,
    create_chrome_driver,
    fetch_document_html_via_browser,
    wait_for_document_ready,
)


class BrowserManager:
    def __init__(self) -> None:
        self.cfg = get_config()
        self._driver = None
        self._lock = threading.Lock()

    @property
    def driver(self):
        return self._driver

    def ensure_driver(self):
        with self._lock:
            if self._driver is not None:
                try:
                    _ = self._driver.window_handles
                    return self._driver
                except Exception:
                    self._driver = None
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
            profile_dir = os.path.join(project_root, ".profiles", "default")
            os.makedirs(profile_dir, exist_ok=True)
            driver = create_chrome_driver(headless=self.cfg.headless, profile_dir=profile_dir)
            driver.get(self.cfg.ras_base_url)
            wait_for_document_ready(driver, timeout_seconds=20.0)
            apply_stealth(driver)
            self._driver = driver
            log_event("browser_started", {"status": "ok"})
            return driver

    def ensure_ras_home(self) -> None:
        driver = self.ensure_driver()
        try:
            current_url = str(driver.current_url or "")
        except Exception:
            current_url = ""
        if "ras.arbitr.ru" not in current_url:
            driver.get(self.cfg.ras_base_url)
            wait_for_document_ready(driver, timeout_seconds=20.0)

    def close_browser(self) -> None:
        with self._lock:
            driver = self._driver
            self._driver = None
        if driver is not None:
            try:
                driver.quit()
                log_event("browser_closed", {"status": "ok"})
            except Exception as exc:
                log_event("browser_closed", {"status": "error", "message": str(exc)})


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
            self.browser.ensure_ras_home()
            driver = self.browser.ensure_driver()
            raw = fetch_document_html_via_browser(driver, task.doc_uuid)
            is_ok = bool(raw.get("ok"))
            status_code = int(raw.get("status") or 0)
            text = str(raw.get("text") or "")
            if is_ok and status_code == 200 and text:
                text_base64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
                result = DocFetchResult(
                    ok=True,
                    text_base64=text_base64,
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


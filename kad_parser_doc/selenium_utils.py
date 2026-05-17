from __future__ import annotations

from typing import Any

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from playwright_stealth import Stealth


def create_persistent_context(headless: bool, profile_dir: str) -> tuple[Playwright, BrowserContext]:
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )
    return pw, context


def get_or_create_page(context: BrowserContext) -> Page:
    pages = context.pages
    return pages[0] if pages else context.new_page()


def wait_for_page_ready(page: Page, timeout_ms: float = 20_000) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)


def apply_stealth(page: Page) -> None:
    try:
        # navigator_plugins=False — Pravocaptcha calls Plugin.item() which the JS stub lacks
        Stealth(navigator_plugins=False).apply_stealth_sync(page)
    except Exception:
        pass


def fetch_document_html_via_browser(page: Page, doc_uuid: str) -> dict[str, Any]:
    js = """
    async (uuid) => {
        return new Promise((resolve) => {
            function postWithToken(token) {
                try {
                    fetch('/Ras/HtmlDocument/' + uuid, {
                        method: 'POST',
                        headers: {
                            'RecaptchaToken': token === undefined ? 'undefined' : String(token),
                            'X-Requested-With': 'XMLHttpRequest',
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: 'hilightText='
                    }).then(async function(resp) {
                        var txt = '';
                        try { txt = await resp.text(); } catch(e) {}
                        resolve({ ok: resp.status === 200, status: resp.status, text: txt });
                    }).catch(function(e) {
                        resolve({ ok: false, status: 0, error: String(e), text: '' });
                    });
                } catch(e) {
                    resolve({ ok: false, status: 0, error: String(e), text: '' });
                }
            }
            try {
                if (window.Common && typeof Common.executePravocaptcha === 'function') {
                    Common.executePravocaptcha(postWithToken);
                } else {
                    postWithToken('undefined');
                }
            } catch(e) {
                resolve({ ok: false, status: 0, error: String(e), text: '' });
            }
        });
    }
    """
    result = page.evaluate(js, str(doc_uuid))
    if isinstance(result, dict):
        return result
    return {"ok": False, "status": 0, "error": "unexpected_browser_result", "text": ""}

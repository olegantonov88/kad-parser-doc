from __future__ import annotations

import hashlib
import random
from typing import Any, Optional

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
        # navigator_plugins=False  — Pravocaptcha вызывает Plugin.item() через WebIDL, заглушка его не реализует
        # navigator_languages=False — stealth менял язык на en-US, что меняло pr_fp и выглядело нетипично
        Stealth(navigator_plugins=False, navigator_languages=False).apply_stealth_sync(page)
    except Exception:
        pass


def ip_to_noise(ip: str, salt: str = "") -> float:
    """Детерминированный шум из IP + соль. Один IP = один fingerprint всегда."""
    if not ip:
        return (random.random() - 0.5) * 1e-6
    key = f"{ip}:{salt}" if salt else ip
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return ((h % 10000) / 10000 - 0.5) * 1e-6


def inject_fp_noise(context: BrowserContext, noise: float) -> None:
    """Инжектирует Canvas + Audio шум в каждую страницу контекста через add_init_script."""
    script = f"""
    (() => {{
        const audioNoise = {noise:.20e};
        const pixelShift = (Math.round(Math.abs(audioNoise) * 1e9) % 127) + 1;

        // Audio: добавляем константный сдвиг к каждому семплу
        const origGetChannelData = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = function(channel) {{
            const data = origGetChannelData.call(this, channel);
            for (let i = 0; i < data.length; i++) {{
                data[i] = Math.max(-1, Math.min(1, data[i] + audioNoise));
            }}
            return data;
        }};

        // Canvas getImageData: возвращаем изменённые данные, не трогая оригинал
        const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function() {{
            const imgData = origGetImageData.apply(this, arguments);
            if (imgData.data.length >= 4) {{
                imgData.data[0] = (imgData.data[0] + pixelShift) & 0xff;
            }}
            return imgData;
        }};

        // Canvas toDataURL: копируем в offscreen canvas, меняем пиксель, возвращаем data URL
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {{
            const w = this.width || 1;
            const h = this.height || 1;
            const canvas2 = document.createElement('canvas');
            canvas2.width = w;
            canvas2.height = h;
            const ctx2 = canvas2.getContext('2d');
            if (ctx2) {{
                ctx2.drawImage(this, 0, 0);
                const imgData = ctx2.getImageData(0, 0, w, h);
                if (imgData.data.length >= 4) {{
                    imgData.data[0] = (imgData.data[0] + pixelShift) & 0xff;
                }}
                ctx2.putImageData(imgData, 0, 0);
                return origToDataURL.call(canvas2, type);
            }}
            return origToDataURL.apply(this, arguments);
        }};
    }})();
    """
    context.add_init_script(script)


def read_pr_fp(page: Page) -> Optional[str]:
    """Читает cookie pr_fp, вычисленный WASM-ом KAD после загрузки страницы."""
    try:
        for cookie in page.context.cookies():
            if cookie.get("name") == "pr_fp":
                return cookie.get("value")
    except Exception:
        pass
    return None


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

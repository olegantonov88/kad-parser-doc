from __future__ import annotations

from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth


def create_chrome_driver(headless: bool, profile_dir: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--lang=ru-RU")
    if headless:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    driver.set_script_timeout(60)
    return driver


def wait_for_document_ready(driver: webdriver.Chrome, timeout_seconds: float = 20.0) -> None:
    WebDriverWait(driver, timeout_seconds).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def apply_stealth(driver: webdriver.Chrome) -> None:
    try:
        stealth(
            driver,
            languages=["ru-RU", "ru", "en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
    except Exception:
        pass


def fetch_document_html_via_browser(driver: webdriver.Chrome, doc_uuid: str) -> dict[str, Any]:
    js = r"""
    var uuid = arguments[0];
    var done = arguments[arguments.length - 1];
    function postWithToken(token){
      try{
        fetch('/Ras/HtmlDocument/' + uuid, {
          method: 'POST',
          headers: {
            'RecaptchaToken': token === undefined ? 'undefined' : String(token),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          body: 'hilightText='
        }).then(async function(resp){
          var txt = '';
          try { txt = await resp.text(); } catch(e) {}
          done({ ok: resp.status === 200, status: resp.status, text: txt });
        }).catch(function(e){
          done({ ok: false, status: 0, error: String(e), text: '' });
        });
      } catch(e){
        done({ ok: false, status: 0, error: String(e), text: '' });
      }
    }
    try{
      if (window.Common && typeof Common.executePravocaptcha === 'function'){
        Common.executePravocaptcha(postWithToken);
      } else {
        postWithToken('undefined');
      }
    } catch(e){
      done({ ok: false, status: 0, error: String(e), text: '' });
    }
    """
    result = driver.execute_async_script(js, str(doc_uuid))
    if isinstance(result, dict):
        return result
    return {"ok": False, "status": 0, "error": "unexpected_browser_result", "text": ""}


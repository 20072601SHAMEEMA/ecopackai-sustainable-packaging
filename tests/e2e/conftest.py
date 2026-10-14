"""
End-to-end UI test setup (Playwright).

- Starts the real EcoPackAI app (API + website) on a free local port, using the
  test database from tests/conftest.py and a client API key.
- Runs every test in Chromium and Firefox (choose with E2E_BROWSERS=chromium,firefox).
- On a failed test, saves to tests/e2e/artifacts/<test>/: a screenshot, the page
  HTML, the browser console log and a Playwright trace. Replay the trace with:
      python -m playwright show-trace tests/e2e/artifacts/<test>/trace.zip

Needs: pip install playwright && python -m playwright install chromium firefox
(skipped automatically when Playwright or its browsers are missing).
"""

import os
import re
import threading
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
E2E_KEY = "e2e-client-key-0001"
BROWSERS = [b.strip() for b in os.environ.get("E2E_BROWSERS", "chromium,firefox").split(",") if b.strip()]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Remember each phase's result on the test item, so fixtures can see whether the test failed."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def live_server(make_app):
    from werkzeug.serving import make_server

    app = make_app(API_KEYS=(E2E_KEY,), ADMIN_API_KEYS=())
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="session")
def playwright_instance():
    with playwright_api.sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session", params=BROWSERS)
def browser(request, playwright_instance):
    try:
        launched = getattr(playwright_instance, request.param).launch()
    except Exception as error:                                     # browser not installed
        pytest.skip(f"{request.param} is not available: {error}")
    yield launched
    launched.close()


@pytest.fixture
def page(request, browser, live_server):
    context = browser.new_context(base_url=live_server, viewport={"width": 1280, "height": 900},
                                  accept_downloads=True)
    context.tracing.start(screenshots=True, snapshots=True, sources=False)
    new_page = context.new_page()
    new_page.set_default_timeout(15000)
    console = []
    new_page.on("console", lambda msg: console.append(f"[{msg.type}] {msg.text}"))
    new_page.on("pageerror", lambda exc: console.append(f"[pageerror] {exc}"))
    new_page.console_log = console
    new_page.e2e_key = E2E_KEY
    yield new_page

    failed = getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed
    if failed:
        folder = ARTIFACTS / re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            new_page.screenshot(path=str(folder / "screenshot.png"), full_page=True)
            (folder / "page.html").write_text(new_page.content(), encoding="utf-8")
        except Exception:
            pass
        (folder / "console.log").write_text("\n".join(console) + "\n", encoding="utf-8")
        context.tracing.stop(path=str(folder / "trace.zip"))
        print(f"\nE2E failure artifacts saved in {folder}")
    else:
        context.tracing.stop()
    context.close()

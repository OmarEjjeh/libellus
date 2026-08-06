"""The round-trip holds in a real browser, through a real host (#91, ADR-0047).

`app/src/feast/document.test.ts` proves the same thing under `node`, which is
where a stringifier bug would first show up. This proves the rest of the path:
that the built bundle is what gets served, that `/feasts/*.yaml` reaches the
page over `fetch` on a host that also serves the application, and that the text
survives being decoded and put back together by the shipped code rather than by
the source next to it.

That distinction is the whole of #91 slice 1's integration risk. A build step
that emits a bundle nobody serves fails silently: the browser is handed an
`index.html` whose `<script src="/src/main.tsx">` it cannot run, and shows a
blank page.

The Toolchain is deliberately blocked here. The editor does not wait for the
pipeline — the feast panel renders while the Worker is still fetching ~80 MB —
so aborting those requests keeps this test about the editor, and keeps it
runnable in CI, which has no Toolchain at all.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("playwright.sync_api", reason="needs playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SHIPPED_FEASTS = ["2026-07-10-benedictus", "2026-09-18-lambertus"]

pytestmark = pytest.mark.skipif(
    not (PROJECT_ROOT / "app" / "dist" / "index.html").is_file(),
    reason="needs the application — run `npm install && npm run build`",
)


@pytest.fixture(scope="module")
def served(serve: ModuleType) -> Iterator[str]:
    """`serve.py`'s own handler, without `main()`'s wheel and Toolchain guards.

    Neither is needed to read a feast spec, and requiring them would make this
    skip exactly where it is most wanted — on a machine, or a CI runner, that
    has never built a booklet.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(serve.Handler, generated=serve.manifests("none.whl"))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def page(served: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        opened = browser.new_page()
        opened.route("**/toolchain/**", lambda route: route.abort())
        opened.goto(f"{served}/app/", wait_until="domcontentloaded")
        yield opened
        browser.close()


@pytest.mark.parametrize("feast", SHIPPED_FEASTS)
def test_a_shipped_feast_would_be_written_back_unchanged(page, feast: str) -> None:
    page.select_option("#feast", feast)

    verdict = page.locator(".feast p")
    verdict.wait_for(timeout=30_000)
    assert "bestanden" in verdict.inner_text(), verdict.inner_text()
    assert verdict.get_attribute("class") == "faithful"


def test_the_feast_is_read_into_a_typed_model_and_not_just_fetched(page) -> None:
    """The counts come from the composed document, so they prove it composed."""
    page.select_option("#feast", "2026-09-18-lambertus")
    page.locator(".feast p").wait_for(timeout=30_000)

    shown = dict(
        zip(
            page.locator(".feast dt").all_inner_texts(),
            page.locator(".feast dd").all_inner_texts(),
        )
    )
    assert shown["title"] == "Sancti Lamberti"
    assert shown["rite"] == "romanum-cum-precibus"
    assert shown["antiphonae"] == "5"

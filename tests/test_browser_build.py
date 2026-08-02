"""The booklet the browser builds is the booklet the toolchain builds (#57).

This is the acceptance test for the all-in-one's first vertical slice: a page
served over plain HTTP, no cross-origin isolation, no `SharedArrayBuffer`, and
a PDF at the end that is pixel-identical to a native build of the same feast.

Pixels, not text: the chant is drawn from font glyphs positioned by
GregorioTeX, so a placement bug leaves the extracted text identical. #56 is the
standing proof — ten pages differed by a vertical offset of otherwise identical
content, and no text comparison would have seen it.

Against a native build made *here*, never against the shipped PDF. That
distinction is what let spike #43 attribute a discrepancy to a pre-existing
native bug instead of to WebAssembly, and it is why #56 was found at all.

Skipped unless the Toolchain has been assembled (`scripts/toolchain/build.sh`)
and a native TeX Live is present, so an ordinary `pytest` run — and CI, which
has neither — is unaffected.
"""

from __future__ import annotations

import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="needs playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from conftest import requires_toolchain  # noqa: E402

#: How long the whole first visit may take: ~80 MB of Toolchain, a Pyodide
#: install, a format build, then two LuaTeX passes over a 36-page booklet.
BUILD_TIMEOUT_MS = 900_000

pytestmark = [
    requires_toolchain,
    pytest.mark.skipif(
        not (Path(__file__).resolve().parent.parent / "toolchain" / "manifest.json").is_file(),
        reason="needs the Toolchain — run scripts/toolchain/build.sh",
    ),
]


#: conftest's `repo_root` is function-scoped, and the server and the booted
#: page have to outlive a single test — booting one costs minutes.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """The application, served exactly as #57 requires: plain HTTP, no COOP/COEP."""
    port = free_port()
    process = subprocess.Popen(
        ["uv", "run", "app/serve.py", "--port", str(port)],
        cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except OSError:
            time.sleep(1)
    else:
        process.terminate()
        pytest.fail("the dev server never came up")
    yield base
    process.terminate()
    process.wait(timeout=30)


@pytest.fixture(scope="module")
def page_context(server: str):
    """One booted page for the whole module — booting it costs minutes."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        # An explicit context, because the OPFS test opens a second page in it:
        # the cache is per origin, so proving it was populated means visiting
        # again from somewhere that shares storage with the first visit.
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(BUILD_TIMEOUT_MS)
        problems: list[str] = []
        page.on("pageerror", lambda error: problems.append(str(error)))
        page.goto(f"{server}/app/", wait_until="domcontentloaded")
        page.wait_for_function("globalThis.libellus?.ready === true", timeout=BUILD_TIMEOUT_MS)
        yield page, context, problems
        browser.close()


def build_in_browser(page, feast: str, compact: bool, into: Path) -> Path:
    """Build one booklet in the tab and write the bytes out for comparison."""
    result = page.evaluate(
        """async ([feast, compact]) => {
             const built = await globalThis.libellus.build(feast, compact);
             return { stem: built.stem, bytes: built.bytes };
           }""",
        [feast, compact],
    )
    pdf = into / f"{result['stem']}-browser.pdf"
    pdf.write_bytes(bytes(result["bytes"]))
    return pdf


def build_natively(repo_root: Path, feast: str, compact: bool) -> Path:
    """The reference: the same feast through the installed toolchain, here, now."""
    subprocess.run(
        [
            "uv", "run", "libellus", "build", f"feasts/{feast}.yaml",
            "--compact" if compact else "--no-compact",
        ],
        cwd=repo_root, check=True, capture_output=True,
    )
    stem = f"{feast}-kurzfassung" if compact else feast
    return repo_root / "build" / stem / f"{stem}.pdf"


@pytest.mark.parametrize("compact", [False, True], ids=["full", "kurzfassung"])
def test_the_browser_booklet_is_pixel_identical_to_a_native_one(
    page_context, repo_root: Path, tmp_path: Path, compact: bool
) -> None:
    page, _context, problems = page_context
    feast = "2026-09-18-lambertus"

    from_browser = build_in_browser(page, feast, compact, tmp_path)
    from_toolchain = build_natively(repo_root, feast, compact)

    comparison = subprocess.run(
        ["uv", "run", "scripts/pdfdiff.py", str(from_toolchain), str(from_browser)],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    assert comparison.returncode == 0, comparison.stdout + comparison.stderr
    assert "ALL PAGES PIXEL-IDENTICAL" in comparison.stdout
    assert not problems, problems


def test_the_page_needs_no_cross_origin_isolation(page_context) -> None:
    """GitHub Pages cannot send COOP/COEP, so the build must not want them.

    ADR-0026 decision 7 keeps that host, which rules out `SharedArrayBuffer` —
    and *that* is what forces the compile runner to be synchronous, the engine
    instances to be pre-created, and the whole pipeline into a Worker.
    """
    page, _context, _ = page_context

    assert page.evaluate("globalThis.crossOriginIsolated") is False
    assert page.evaluate("typeof SharedArrayBuffer === 'undefined'") is True


def test_the_toolchain_is_cached_rather_than_refetched(page_context, server: str) -> None:
    """A second visit reads ~80 MB out of OPFS instead of the network."""
    _page, context, _ = page_context
    reloaded = context.new_page()
    fetched: list[str] = []
    reloaded.on(
        "request",
        lambda request: fetched.append(request.url) if "/toolchain/" in request.url else None,
    )
    reloaded.set_default_timeout(BUILD_TIMEOUT_MS)
    reloaded.goto(f"{server}/app/", wait_until="domcontentloaded")
    reloaded.wait_for_function("globalThis.libellus?.ready === true", timeout=BUILD_TIMEOUT_MS)

    # The manifest is always read — it is what the cache is validated against.
    # The payload behind it must not be.
    heavy = [url for url in fetched if not url.endswith(("manifest.json", ".whl"))]
    assert heavy == [], heavy
    reloaded.close()

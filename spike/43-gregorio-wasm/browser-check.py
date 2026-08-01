# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""Spike #43, part 1: run gregorio.wasm in real Chrome and compare the .gtex it
produces against the natively-produced reference in tmp-gre/.

The server deliberately sends no COOP/COEP headers, so the page runs under the
same constraints GitHub Pages imposes. That is the point of the exercise: if
the build needed SharedArrayBuffer, this is where it would fail.

    uv run browser-check.py
"""

import functools
import hashlib
import http.server
import json
import shutil
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
REPO = HERE.parent.parent
STAGE = REPO / "build/2026-09-18-lambertus"
REFERENCE = STAGE / "tmp-gre"
OUT = HERE / "work/out"
VOWELS = Path("/usr/local/texlive/2026/texmf-dist/tex/luatex/gregoriotex/gregorio-vowels.dat")
SERVE = HERE / "work/serve"


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static server sending no cross-origin isolation headers."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
    }

    def log_message(self, format, *args):  # noqa: A002 — signature is the base class's
        pass


def assemble() -> list[str]:
    """Lay out the directory the page is served from; returns the score list."""
    if SERVE.exists():
        shutil.rmtree(SERVE)
    SERVE.mkdir(parents=True)

    for name in ("gregorio-memfs.mjs", "gregorio-memfs.wasm"):
        shutil.copy(OUT / name, SERVE / name)
    shutil.copy(VOWELS, SERVE / VOWELS.name)
    shutil.copy(HERE / "browser-page.html", SERVE / "index.html")
    shutil.copytree(STAGE / "chant", SERVE / "chant")

    scores = sorted(str(p.relative_to(STAGE)) for p in STAGE.rglob("chant/**/*.gabc"))
    (SERVE / "manifest.json").write_text(json.dumps(scores))
    return scores


def main() -> None:
    assemble()

    handler = functools.partial(Handler, directory=str(SERVE))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome")
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/index.html")
            page.wait_for_function("window.__spike !== undefined", timeout=180_000)
            spike = page.evaluate("window.__spike")
            browser.close()

    if "error" in spike:
        print("PAGE ERROR:", spike["error"])
        raise SystemExit(1)

    identical = differ = 0
    for rel, got in spike["results"].items():
        want = hashlib.sha256(
            (REFERENCE / rel.replace(".gabc", "-6_1_0.gtex")).read_bytes()
        ).hexdigest()
        if got == want:
            identical += 1
        else:
            differ += 1
            print("DIFFERS:", rel)

    print(f"browser scores:      {spike['count']}")
    print(f"identical to native: {identical}")
    print(f"differ:              {differ}")
    print(f"nonzero exits:       {spike['nonzero']}")
    print(f"crossOriginIsolated: {spike['crossOriginIsolated']}")
    print(f"SharedArrayBuffer:   {spike['hasSAB']}")
    if errors:
        print("page errors:", errors)


if __name__ == "__main__":
    main()

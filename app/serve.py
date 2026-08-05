#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Serve the browser application for #57.

    uv run app/serve.py [--port 8017]

Builds a fresh ``libellus`` wheel, then serves the repository root so the page
can reach four things: itself under ``/app/``, the Toolchain under
``/toolchain/``, that wheel under ``/dist/``, and the Working directory —
feast specs, their pictures and the Psalter — from the checkout.

Deliberately plain. It sends **no** ``Cross-Origin-Opener-Policy`` and no
``Cross-Origin-Embedder-Policy``, so the page runs without cross-origin
isolation and therefore without ``SharedArrayBuffer``. That is not an omission
to be fixed: it is the condition #57 has to hold under, because GitHub Pages
cannot send those headers and ADR-0026 decision 7 keeps that host.

NOTE ON THE PSALTER: this serves ``psalter/`` off the local disk, because a
booklet that is not ``latin_only`` needs one to set its German verses
(ADR-0025). Bremen's copies are the Einheitsübersetzung — © Katholische
Bibelanstalt, not redistributable (ADR-0023). Serving them to your own browser
on localhost is fine; publishing this directory anywhere is not.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Logical prefixes the wheel does NOT carry, because they are the user's
#: content rather than the tool (see libellus.paths). The page copies these
#: into Pyodide's filesystem, which is what makes it a Working directory.
CONTENT = (
    ("feasts", "*.yaml"),
    ("images", "**/*"),
    ("psalter", "**/*.yaml"),
)


def build_wheel() -> str:
    """Build the wheel the page installs, and return its filename."""
    print("building the libellus wheel…", file=sys.stderr)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", "dist"],
        cwd=ROOT, check=True, capture_output=True,
    )
    wheels = sorted((ROOT / "dist").glob("libellus-*.whl"), key=lambda p: p.stat().st_mtime)
    return wheels[-1].name


def content_files(base: Path, pattern: str) -> Iterator[Path]:
    """Paths under ``base`` matching ``pattern``, descending into symlinked directories.

    ``Path.glob``'s ``**`` deliberately does not recurse into symlinks, and
    ``recurse_symlinks`` is 3.13+ while this supports 3.12. A worktree shares the
    private Psalter one symlink per translation (``scripts/worktree-add.sh``), so
    without this it serves only the tracked public Allioli-Arndt and every feast
    naming the Einheitsübersetzung fails to resolve its German — on a checkout
    that looks provisioned (#83).

    One level down is enough, and is the point: the symlinks are the immediate
    children of a shared directory, and what they point at is ordinary.
    """
    yield from base.glob(pattern)
    if pattern.startswith("**") and base.is_dir():
        for entry in base.iterdir():
            if entry.is_symlink() and entry.is_dir():
                yield from entry.glob(pattern)


def manifests(libellus_wheel: str) -> dict[str, str]:
    """The two JSON files the page asks for, generated so they cannot go stale."""
    # Flat, alongside the rest of the Toolchain — not toolchain/wheels/, which
    # a GitHub release asset cannot have (#58). Pyodide's own package wheels
    # live in the same directory; harmless here since only VENDORED_WHEELS'
    # names are ever looked up from this dict.
    vendored = {
        path.name.split("-")[0]: path.name
        for path in sorted((ROOT / "toolchain").glob("*.whl"))
    }
    files = []
    for directory, pattern in CONTENT:
        for path in sorted(content_files(ROOT / directory, pattern)):
            if path.is_file() and not path.name.startswith("."):
                files.append(path.relative_to(ROOT).as_posix())
    return {
        "/app/wheels.json": json.dumps({**vendored, "libellus": libellus_wheel}),
        "/app/workdir.json": json.dumps(files),
    }


class Handler(SimpleHTTPRequestHandler):
    """Static files, correct WebAssembly and ES-module types, no isolation headers."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
        ".whl": "application/zip",
    }

    def __init__(self, *args, generated: dict[str, str], **kwargs):
        self.generated = generated
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 — http.server's spelling
        body = self.generated.get(self.path)
        if body is None:
            super().do_GET()
            return
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        pass  # a booklet is thousands of requests; the page has its own log


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument(
        "--no-build", action="store_true", help="reuse the wheel already in dist/"
    )
    arguments = parser.parse_args()

    if arguments.no_build:
        wheel = sorted((ROOT / "dist").glob("libellus-*.whl"))[-1].name
    else:
        wheel = build_wheel()

    if not (ROOT / "toolchain" / "manifest.json").is_file():
        sys.exit("no Toolchain — run scripts/toolchain/build.sh first")

    handler = partial(Handler, generated=manifests(wheel))
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), handler)
    print(f"serving {wheel} at http://127.0.0.1:{arguments.port}/app/", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()

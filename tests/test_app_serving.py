"""What ``/app/`` serves is the built application, not its sources (#91, ADR-0046).

Since the editing surface became a Vite build, ``app/`` holds TSX that no
browser can run and ``app/dist/`` holds what both hosts actually serve. The URL
shape is deliberately unchanged — ``pipeline/worker.mjs`` reaches its siblings
and its own ``wheels.json`` relatively, and ``electron/main.mjs`` reproduces
the same paths under ``libellus://bundle/`` — so the whole of that change lives
in one path rewrite, tested here.

Getting it wrong is quiet rather than loud: serving ``app/`` would hand the
browser ``index.html``'s ``<script src="/src/main.tsx">`` and a blank page, with
nothing in the pipeline log to say why.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

APP_BUILD = PROJECT_ROOT / "app" / "dist"

requires_build = pytest.mark.skipif(
    not (APP_BUILD / "index.html").is_file(),
    reason="needs the application — run `npm install && npm run build`",
)


@pytest.fixture
def translate(serve: ModuleType):
    """`Handler.translate_path`, without a socket to bind or a request to make."""
    handler = serve.Handler.__new__(serve.Handler)
    handler.directory = str(serve.ROOT)
    return lambda url: Path(handler.translate_path(url))


def test_the_application_is_served_from_the_build(translate) -> None:
    assert translate("/app/") == PROJECT_ROOT / "app" / "dist"
    assert translate("/app/index.html") == PROJECT_ROOT / "app" / "dist" / "index.html"


def test_the_pipeline_modules_keep_the_urls_they_had(translate) -> None:
    """Vite's public directory puts them back at the top of the build output.

    `worker.mjs` fetches `./wheels.json` and imports `./engines.mjs`; `impose.mjs`
    imports `./vendor/pdf-lib.esm.min.js`. All of that is relative to these URLs.
    """
    build = PROJECT_ROOT / "app" / "dist"

    assert translate("/app/worker.mjs") == build / "worker.mjs"
    assert translate("/app/vendor/pdf-lib.esm.min.js") == build / "vendor" / "pdf-lib.esm.min.js"


def test_the_sources_are_no_longer_reachable(translate) -> None:
    """`app/serve.py` and `app/src/` are inputs to a build, not things to serve."""
    assert not translate("/app/serve.py").exists()
    assert not translate("/app/src/main.tsx").exists()


def test_everything_else_still_comes_off_the_checkout(translate) -> None:
    assert translate("/feasts/2026-09-18-lambertus.yaml") == (
        PROJECT_ROOT / "feasts" / "2026-09-18-lambertus.yaml"
    )
    assert translate("/toolchain/manifest.json") == PROJECT_ROOT / "toolchain" / "manifest.json"
    assert translate("/dist/libellus-0.1.0-py3-none-any.whl") == (
        PROJECT_ROOT / "dist" / "libellus-0.1.0-py3-none-any.whl"
    )


def test_the_rewrite_cannot_be_walked_out_of(translate) -> None:
    """The base class normalises first, so this only ever inserts one segment."""
    assert translate("/app/../../../etc/passwd") == PROJECT_ROOT / "etc" / "passwd"
    assert translate("/app/../feasts/x.yaml") == PROJECT_ROOT / "feasts" / "x.yaml"


@requires_build
def test_the_pipeline_modules_are_copied_verbatim() -> None:
    """ADR-0035 decision 5 reuses them unchanged; ADR-0046 decision 2 enforces it.

    Vite's public directory transforms nothing, which is exactly why they live
    there rather than in the bundler's path — a rewritten `import` or an
    inlined `fetch` URL in any of these would break the Electron shell's whole
    premise. Compared here rather than trusted to the setting.
    """
    pipeline = PROJECT_ROOT / "app" / "pipeline"
    sources = sorted(path for path in pipeline.rglob("*") if path.is_file())
    assert [path.name for path in sources], "no pipeline modules found at all"

    for source in sources:
        copied = APP_BUILD / source.relative_to(pipeline)
        assert copied.is_file(), f"{source.relative_to(PROJECT_ROOT)} never reached the build"
        assert copied.read_bytes() == source.read_bytes(), f"{copied.name} was transformed"

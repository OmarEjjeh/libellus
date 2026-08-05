"""The Working directory a host lists is the one on disk, symlinks included (#83).

`scripts/worktree-add.sh` shares the private Psalter into a worktree one symlink
per translation, because `psalter/` is a real directory there — git checks the
tracked public Allioli-Arndt out into it (ADR-0041), so the whole directory
cannot be one symlink the way the other shared items are.

Nothing in the suite noticed when the browser host stopped listing those
translations, because the failure surfaces one layer away, as a feast naming a
translation that „does not exist" — wording that points at the feast file rather
than at the checkout. Hence a test on the enumeration itself.

`electron/main.mjs`'s `listContentFiles` mirrors this and is not covered here;
the Electron shell has no test harness in this suite.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SERVE = Path(__file__).resolve().parent.parent / "app" / "serve.py"


@pytest.fixture(scope="module")
def serve() -> ModuleType:
    """`app/serve.py`, imported by path — it is a script, not part of the package."""
    spec = importlib.util.spec_from_file_location("libellus_app_serve", SERVE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shared_psalter(tmp_path: Path) -> Path:
    """A worktree's `psalter/`: a checked-out translation, and one shared by symlink."""
    elsewhere = tmp_path / "main-checkout" / "psalter" / "eu1980"
    elsewhere.mkdir(parents=True)
    (elsewhere / "109.yaml").write_text("verses: []\n", encoding="utf-8")

    psalter = tmp_path / "worktree" / "psalter"
    (psalter / "allioli-arndt").mkdir(parents=True)
    (psalter / "allioli-arndt" / "109.yaml").write_text("verses: []\n", encoding="utf-8")
    (psalter / "eu1980").symlink_to(elsewhere)
    return psalter


def _listed(paths, base: Path) -> set[str]:
    return {path.relative_to(base).as_posix() for path in paths}


def test_a_symlinked_translation_is_listed(serve: ModuleType, shared_psalter: Path) -> None:
    """The shared translations reach the manifest, not just the checked-out one."""
    # The shape of the bug, pinned so the reason for `content_files` stays legible:
    # `**` walks straight past a symlinked directory, and says nothing about it.
    assert _listed(shared_psalter.glob("**/*.yaml"), shared_psalter) == {
        "allioli-arndt/109.yaml"
    }

    assert _listed(
        serve.content_files(shared_psalter, "**/*.yaml"), shared_psalter
    ) == {"allioli-arndt/109.yaml", "eu1980/109.yaml"}


def test_a_flat_pattern_does_not_start_descending(
    serve: ModuleType, shared_psalter: Path
) -> None:
    """Only recursive patterns follow symlinks — `feasts/*.yaml` stays one level deep."""
    assert _listed(serve.content_files(shared_psalter, "*.yaml"), shared_psalter) == set()


def test_a_broken_symlink_is_skipped_rather_than_raising(
    serve: ModuleType, shared_psalter: Path
) -> None:
    """A stale share — the main checkout moved — degrades to a missing translation."""
    (shared_psalter / "eu2016").symlink_to(shared_psalter.parent / "gone")

    assert _listed(
        serve.content_files(shared_psalter, "**/*.yaml"), shared_psalter
    ) == {"allioli-arndt/109.yaml", "eu1980/109.yaml"}

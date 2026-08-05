import importlib
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """The repository root — the working directory a build runs in."""
    return Path(__file__).resolve().parent.parent


#: The probe Psalter: synthetic German, one line per sung verse, generated with
#: verse counts taken from the psalm-tone engine.
PROBE_PSALTER_DIR = Path("tests/fixtures/psalter")

#: The shipped preference order, captured before `probe_psalter` overrides it.
#: A test that wants to assert what a real install prefers cannot read the
#: constant directly — the autouse fixture below has already replaced it.
REAL_PSALTER_DE_PREFERENCE = importlib.import_module(
    "libellus.resolve"
).PSALTER_DE_PREFERENCE


@pytest.fixture(autouse=True)
def probe_psalter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every German verse from the probe Psalter, never a real one.

    A Psalter is supplied rather than bundled (ADR-0024), and the one Bremen
    prints is the Einheitsübersetzung — not redistributable, absent from a
    fresh clone, and not something a test suite should assert against. Pointing
    the lookup at the probe makes the suite give the same answers in a
    contributor's checkout, in CI, and in a fork's pull request.
    """
    monkeypatch.setattr("libellus.resolve.PSALTER_DIR", PROBE_PSALTER_DIR)
    monkeypatch.setattr("libellus.resolve.PSALTER_DE_PREFERENCE", ("probe",))


def _has_real_psalter() -> bool:
    """Whether a Psalter is checked out at ``psalter/`` in this working copy."""
    root = Path(__file__).resolve().parent.parent
    return any((root / "psalter").glob("*/[0-9]*.yaml"))


#: The committed data island records which psalms have German, which depends on
#: the Psalter this working copy happens to have (formdata reads ``psalter/``).
#: The island in the repository is Bremen's, generated against the
#: Einheitsübersetzung; a clone without a Psalter would regenerate a different
#: one, so its freshness gate can only run where a Psalter exists. It protects
#: whoever regenerates the island, which is the person who has one.
requires_psalter = pytest.mark.skipif(
    not _has_real_psalter(),
    reason="needs a Psalter checked out at psalter/ (the committed data island "
    "is Bremen's, listing the psalms its Einheitsübersetzung covers)",
)


#: A real compile needs the Toolchain, which CI deliberately does not install —
#: it runs the suite on a bare Ubuntu image, and a TeX Live is minutes of setup
#: for one test. So the one test that compiles rather than renders skips itself
#: where the tools are absent, and runs for whoever has them (which is anyone
#: who can build a booklet at all).
requires_toolchain = pytest.mark.skipif(
    shutil.which("lualatex") is None or shutil.which("gregorio") is None,
    reason="needs the Toolchain (gregorio + lualatex with gregoriotex)",
)


#: The pipeline's `romanum-cum-precibus` fixture: St. Lambert, the first real
#: feast authored against the schema (issue #13).
SMOKE_FEAST = "feasts/2026-09-18-lambertus.yaml"

#: The `monasticum` fixture: the Benedict office as actually celebrated, and
#: the feast that reproduces the printed booklet (roadmap item 8).
BENEDICT_FEAST = "feasts/2026-07-10-benedictus.yaml"


@pytest.fixture
def smoke_feast(repo_root: Path) -> Path:
    """Path to the `romanum-cum-precibus` fixture."""
    return repo_root / SMOKE_FEAST


@pytest.fixture
def benedict_feast(repo_root: Path) -> Path:
    """Path to the `monasticum` fixture."""
    return repo_root / BENEDICT_FEAST

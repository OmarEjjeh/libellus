"""Shared test helpers."""

from pathlib import Path

from libellus.paths import source_of

REPO_ROOT = Path(__file__).resolve().parent.parent


def physical(logical: str | Path) -> Path:
    """Where a logical asset path actually lives.

    Bundled assets come from inside the package, generated ones from
    ``build/.cache/``, content from the working directory (ADR-0024). Tests ask
    this the same way production does, so a test cannot pass by reading a file
    from a provider the real code would never consult — which is exactly the
    mistake that hid behind a stale ``chant/**/toni/`` directory once already.
    """
    return source_of(Path(logical), REPO_ROOT)

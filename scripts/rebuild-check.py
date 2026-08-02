#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Check that a staged folder builds the same booklet twice from cold.

    uv run scripts/rebuild-check.py build/2026-09-18-lambertus

Staging promises a folder that "compiles to the booklet without libellus or the
rest of the repo" (CONTEXT.md). The shipped Lambertus booklet did not keep that
promise: it was emitted by a pass GregorioTeX had asked to rerun, so it was a
layout behind its own `.gaux` and no rebuild could reproduce it (#56). Nothing
caught that, because nothing ever rebuilt it.

So: two copies, both stripped back to sources with `make clean`, both built,
compared page by page. Two runs rather than one against a stored reference,
because the thing worth defending is that the folder *converges* — a stored
reference would only ever prove that today's toolchain matches the day it was
recorded.

Takes a few minutes: `make clean` throws away the notation too, so each copy
runs all of gregorio and every LuaTeX pass.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def build(staged: Path, into: Path, stem: str) -> Path:
    """Copy the staged folder, strip it back to sources, and `make` the PDF."""
    shutil.copytree(staged, into)
    subprocess.run(["make", "clean"], cwd=into, check=True, capture_output=True)
    print(f"building in {into.name} …", flush=True)
    result = subprocess.run(["make", f"{stem}.pdf"], cwd=into, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-3000:], file=sys.stderr)
        raise SystemExit(f"build failed in {into}")
    return into / f"{stem}.pdf"


staged = Path(sys.argv[1]).resolve()
stem = staged.name
if not (staged / f"{stem}.tex").is_file():
    raise SystemExit(f"{staged} does not look like a staged folder ({stem}.tex missing)")

with tempfile.TemporaryDirectory() as workspace:
    work = Path(workspace)
    first = build(staged, work / "first", stem)
    second = build(staged, work / "second", stem)
    print(f"comparing {first.name} from two cold builds", flush=True)
    comparison = subprocess.run(
        ["uv", "run", str(Path(__file__).parent / "pdfdiff.py"), str(first), str(second)]
    )

raise SystemExit(comparison.returncode)

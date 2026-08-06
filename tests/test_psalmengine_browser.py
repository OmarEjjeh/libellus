"""The browser's psalm-tone engine answers exactly as ``node`` does.

``app/pipeline/psalmengine.mjs`` runs the vendored ``generate.js`` in the page
instead of in a process (ADR-0027). The engine file itself is untouched, so the
whole risk is in the four node built-ins the browser has to supply — and that
risk is real: reproducing ``vm.runInContext`` faithfully means getting both a
declaration (``var gloria_patri``) and an implicit global
(``var o_g_tones = g_tones = {…}``) onto the sandbox, and an earlier attempt
that handled only the first produced silently empty notation.

So the test is a comparison, not an assertion about mechanism: for every
command the pipeline actually issues, the browser engine and node must agree
byte for byte. Notation that is merely plausible is worth nothing here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from libellus.psalmtone import GENERATOR

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="needs node to compare the two hosts against"
)

#: Every shape `resolve.py` asks for, plus both ways of being rejected. The
#: `--open-notes` Magnificat is the Kurzfassung's two-verse system (ADR-0022),
#: which is the one case that exercises the hollow reciting notes.
COMMANDS = [
    ["list-toni"],
    ["euouae"],
    ["verses", "--psalmus", "109", "--tonus", "8G"],
    ["verses", "--psalmus", "112", "--tonus", "peregrinus"],
    ["verses", "--psalmus", "magnificat", "--tonus", "6F"],
    ["verses", "--psalmus", "magnificat", "--tonus", "1D", "--open-notes"],
    ["verses", "--psalmus", "999", "--tonus", "8G"],
    ["verses", "--psalmus", "109", "--tonus", "9Z"],
]

#: Drives app/pipeline/psalmengine.mjs with a Pyodide stand-in whose filesystem
#: is the real one — the module only ever reads files and asks for the
#: generator path.
HARNESS = """
import {{ readFileSync, existsSync }} from "fs";
const {{ psalmEngine }} = await import("{app}/psalmengine.mjs");
const engine = psalmEngine({{
  runPython: () => "{generator}",
  FS: {{
    readFile: (path) => new Uint8Array(readFileSync(path)),
    analyzePath: (path) => ({{ exists: existsSync(path) }}),
  }},
}});
const [code, stdout, stderr] = engine({args});
process.stdout.write(JSON.stringify({{ code, stdout, stderr }}));
"""


def browser_engine(repo_root: Path, args: list[str], tmp_path: Path) -> tuple[int, str]:
    """Run one command through the browser engine, under node."""
    script = tmp_path / "harness.mjs"
    script.write_text(
        HARNESS.format(
            app=(repo_root / "app" / "pipeline").as_posix(),
            generator=GENERATOR.as_posix(),
            args=json.dumps(args),
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    assert not payload["stderr"], payload["stderr"]
    return payload["code"], payload["stdout"]


def node_engine(args: list[str]) -> tuple[int, str]:
    """Run the same command the way the CLI does."""
    result = subprocess.run(
        ["node", str(GENERATOR), *args], capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout


@pytest.mark.parametrize("args", COMMANDS, ids=lambda a: " ".join(a))
def test_the_browser_engine_matches_node(
    repo_root: Path, args: list[str], tmp_path: Path
) -> None:
    assert browser_engine(repo_root, args, tmp_path) == node_engine(args)

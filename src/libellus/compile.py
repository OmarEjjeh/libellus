"""Compile a staged build folder to the final booklet PDFs.

Two steps. gregorio runs first, over every staged ``.gabc``, so that the TeX
pass finds the notation already made and never autocompiles (ADR-0026
decision 3) — which is what lets lualatex run without ``--shell-escape``.
lualatex then runs until the layout stops moving: GregorioTeX and LaTeX each
ask for a rerun while their caches are still settling, and a pass that emits
its PDF with a request outstanding produces a booklet laid out from the
*previous* pass's cache (#56).

Everything runs inside the staged folder (see libellus.stage), which carries a
Makefile with the identical two steps for latex-only environments — keep the
two in sync.

*How* the two tools are run is the one host-dependent part, and it is the
:data:`Runner` seam: child processes by default, WebAssembly in the browser
application (ADR-0026). Imposition still shells out unconditionally — ADR-0026
decision 4 replaces pdfjam and pdftk with pdf-lib, which has not happened yet.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

_LUALATEX = ["lualatex", "--interaction=nonstopmode"]

#: Run one toolchain command inside a staged folder and return its stdout.
#:
#: Deliberately does not report the exit status, because neither caller may use
#: it: gregorio exits non-zero for a score it none the less sets usably
#: (ADR-0032 decision 4), and lualatex under ``-interaction=nonstopmode`` exits
#: non-zero on an error it recovered from. Both test the artefact instead — the
#: ``.gtex`` that came out, the log that was written. A backend that cannot run
#: the command at all raises :class:`CompileError`.
#:
#: The folder is the whole interface to the filesystem: everything a command
#: reads and writes is inside it, which is what lets a host without a shell
#: satisfy this by copying that one folder into a virtual filesystem and back
#: (ADR-0026 — WebAssembly in a browser).
Runner = Callable[[Sequence[str], Path], str]


class CompileError(Exception):
    """LaTeX or imposition failure, with a German summary."""


def subprocess_runner(command: Sequence[str], folder: Path) -> str:
    """Run the command as a child process in ``folder``. The default."""
    result = subprocess.run(
        list(command), cwd=folder, capture_output=True, text=True, check=False
    )
    return result.stdout


_runner: Runner = subprocess_runner


def set_runner(runner: Runner) -> None:
    """Point the compile steps at another toolchain.

    The browser application swaps in WebAssembly builds of gregorio and
    LuaHBTeX, because Pyodide has no ``subprocess`` (ADR-0026). Everything above
    this line — which scores to set, how many passes the layout may take, when
    it has settled — is host-independent and stays here. Pass
    :func:`subprocess_runner` to restore the default.
    """
    global _runner  # noqa: PLW0603 — one process-wide toolchain, chosen by the host
    logger.debug("Satz-Werkzeugkette gewechselt: %s.", getattr(runner, "__name__", runner))
    _runner = runner


def _error_lines(log_file: Path) -> list[str]:
    """The ``!``-prefixed error lines of a LaTeX log (all lines = errors if missing)."""
    if not log_file.is_file():
        return [f"„{log_file.name}“ wurde nicht geschrieben."]
    return [
        line
        for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith("!")
    ]


def _run_pass(tex_file: Path, label: str) -> list[str]:
    """One lualatex pass in the staged folder; returns the log's error lines."""
    command = [*_LUALATEX, tex_file.name]
    logger.debug("LaTeX-Aufruf (%s): %s  [cwd=%s]", label, " ".join(command), tex_file.parent)
    started = time.perf_counter()
    _runner(command, tex_file.parent)
    duration = time.perf_counter() - started
    errors = _error_lines(tex_file.with_suffix(".log"))
    if errors:
        logger.warning(
            "LaTeX-Durchlauf %s: %d Fehlerzeile(n) nach %.1f s.", label, len(errors), duration
        )
        for line in errors[:5]:
            logger.debug("  LaTeX: %s", line)
    else:
        logger.info("LaTeX-Durchlauf %s: fehlerfrei nach %.1f s.", label, duration)
    return errors


#: A pass that emits its PDF with one of these outstanding used a cache it then
#: went on to correct, so its PDF is a layout behind. Looping until neither
#: appears is the whole of the fix for #56; there is no separate settling pass,
#: because a pass that asks for nothing has by definition laid out what it
#: computed.
_RERUN_REQUESTS = (
    "Rerun to fix",  # GregorioTeX: line heights, brace lengths, soft accidentals
    "Rerun to get cross-references right",  # LaTeX: labels, page references
)

#: How many passes the layout may take to settle before we stop believing it
#: will. Two is the norm with the notation pre-made; six leaves room without
#: letting a genuine oscillation run forever.
#:
#: Public because a host may have to prepare for the worst case rather than
#: discover it: the browser pre-creates one LuaTeX instance per possible pass,
#: since it cannot make another once the synchronous compile has begun
#: (ADR-0034).
MAX_PASSES = 6


def _rerun_requested(log_file: Path) -> str | None:
    """The first outstanding rerun request in a LaTeX log, if any."""
    log = log_file.read_text(encoding="utf-8", errors="replace")
    return next((request for request in _RERUN_REQUESTS if request in log), None)


def _gregorio(folder: Path) -> None:
    """Turn every staged ``.gabc`` into the ``.gtex`` GregorioTeX will look for.

    GregorioTeX does this itself during the TeX pass unless the file is already
    there, which is what forces ``--shell-escape``. The output path and flags
    are its own (``gregoriotex.lua``): ``tmp-gre/<dir>/<base>-<version>.gtex``,
    where the version is gregorio's with dots as underscores, and it reuses the
    file when it is newer than the ``.gabc``.

    gregorio exits non-zero for a score it none the less sets usably, so the
    test is whether notation came out, not what the exit code was (ADR-0032
    decision 4); whatever gregorio had to say is logged either way. The one
    known case, the elision error in ``sanctorum-meritis.gabc``, is fixed
    (#55) — the corpus compiles silently now, so anything logged here is new.

    :param folder: The staged folder; ``.gabc`` files are found beneath it.
    """
    # Matched rather than split on whitespace, because the banner's shape is
    # not fixed: a gregorio built with kpathsea says "Gregorio 6.1.0 (kpathsea
    # version 6.4.2)." and one built without it — the WebAssembly build, which
    # has no kpathsea to ask — says "Gregorio 6.1.0.". Taking the second token
    # gives "6.1.0." there, hence a "-6_1_0_.gtex" that GregorioTeX will never
    # look for, and a booklet with every score silently missing.
    banner = _runner(["gregorio", "--version"], folder)
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", banner)
    if found is None:
        raise CompileError(
            "gregorio hat seine Version nicht genannt — ohne sie ist der "
            f"Dateiname der Notation nicht bekannt, den GregorioTeX sucht. "
            f"Gemeldet wurde: „{banner.strip()[:200]}“."
        )
    version = "_".join(found.groups())

    scores = sorted(folder.glob("chant/**/*.gabc"))
    for score in scores:
        stem = score.relative_to(folder).with_suffix("")
        # kpathsea refuses to write outside the working directory, so gregorio
        # runs *in* the staged folder and every path it is given is relative.
        gtex = Path("tmp-gre") / stem.with_name(f"{stem.name}-{version}.gtex")
        glog = gtex.with_suffix(".glog")
        (folder / gtex).parent.mkdir(parents=True, exist_ok=True)
        if (folder / gtex).is_file() and (folder / gtex).stat().st_mtime >= score.stat().st_mtime:
            continue
        command = [
            "gregorio", "-D", "-W",
            "-o", str(gtex), "-l", str(glog), str(score.relative_to(folder)),
        ]
        logger.debug("Gregorio-Aufruf: %s  [cwd=%s]", " ".join(command), folder)
        _runner(command, folder)
        if not (folder / gtex).is_file() or (folder / gtex).stat().st_size == 0:
            raise CompileError(
                f"gregorio hat für „{stem}“ keine Notation erzeugt — siehe „{folder / glog}“."
            )
        for line in (folder / glog).read_text(encoding="utf-8", errors="replace").splitlines():
            logger.warning("gregorio (%s): %s", stem, line)
    logger.info("Notation bereit: %d Gesänge (gregorio %s).", len(scores), version)


def _lualatex(tex_file: Path) -> None:
    log_file = tex_file.with_suffix(".log")
    for attempt in range(1, MAX_PASSES + 1):
        errors = _run_pass(tex_file, str(attempt))
        if errors:
            for line in errors[:10]:
                logger.error("LaTeX: %s", line)
            raise CompileError(
                f"LaTeX meldet Fehler in Durchlauf {attempt} — siehe „{log_file}“."
            )
        request = _rerun_requested(log_file)
        if request is None:
            logger.info("Satz stabil nach %d Durchläufen.", attempt)
            return
        logger.info("Durchlauf %d noch nicht stabil („%s“).", attempt, request)
    raise CompileError(
        f"Der Satz ist nach {MAX_PASSES} Durchläufen nicht stabil — "
        f"siehe „{log_file}“."
    )


def page_count(pdf: Path) -> int:
    pages = len(PdfReader(pdf).pages)
    logger.debug("„%s“ hat %d Seiten.", pdf.name, pages)
    return pages


def compile_pdf(tex_file: Path) -> Path:
    """Compile a staged ``.tex`` (in its own folder) to ``<stem>.pdf``."""
    _gregorio(tex_file.parent)
    _lualatex(tex_file)
    pdf = tex_file.with_suffix(".pdf")
    if not pdf.is_file():
        raise CompileError(
            f"„{pdf.name}“ wurde nicht erzeugt — siehe „{tex_file.with_suffix('.log')}“."
        )
    logger.info("Kompiliert: „%s“ (%d Seiten).", pdf, page_count(pdf))
    return pdf


def impose(pdf: Path) -> tuple[Path, Path]:
    """Booklet imposition (pdfjam) + the duplex-rotated variant (pdftk)."""
    booklet = pdf.with_name(f"{pdf.stem}-pdfjam.pdf")
    duplex = pdf.with_name(f"{pdf.stem}-pdfjam-duplex.pdf")
    commands = [
        ["pdfjam", "--booklet", "true", "--landscape", "--paper", "a4paper",
         pdf.name, "-o", booklet.name],
        # Duplex printers without a binding-edge option flip the back side
        # upside down; rotate every second page 180° to compensate.
        ["pdftk", booklet.name, "rotate", "1-endevensouth", "output", duplex.name],
    ]
    for command in commands:
        logger.debug("Montage-Aufruf: %s  [cwd=%s]", " ".join(command), pdf.parent)
        started = time.perf_counter()
        try:
            subprocess.run(command, cwd=pdf.parent, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            raise CompileError(
                f"Die Broschüren-Montage mit „{command[0]}“ ist fehlgeschlagen: "
                f"{exc.stderr.decode(errors='replace')[-500:]}"
            ) from exc
        logger.info("Montage-Schritt „%s“ fertig nach %.1f s.", command[0], time.perf_counter() - started)
    return booklet, duplex

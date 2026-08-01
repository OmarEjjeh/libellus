"""Compile a staged build folder to the final booklet PDFs.

Wraps the proven Makefile logic: gregoriotex's autocompile can garble one
source line per run, so lualatex is looped until the log is error-free
(max 4 passes) plus one final settling pass. Everything runs inside the
staged folder (see libellus.stage), which also carries a Makefile with the
identical loop for latex-only environments (Docker) — keep the two in sync.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

_LUALATEX = ["lualatex", "--shell-escape", "--interaction=nonstopmode"]


class CompileError(Exception):
    """LaTeX or imposition failure, with a German summary."""


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
    subprocess.run(command, cwd=tex_file.parent, capture_output=True, check=False)
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


#: How often a pass may fail before the errors are taken to be real.
#: gregoriotex's autocompile turns each new .gabc into a .gtex *during* a pass,
#: so a booklet with scores it has never compiled reports errors until they all
#: exist — one pass per generation of new scores, roughly. Raised from 4 to 8
#: when the Kurzfassung's Magnificat system (ADR-0022) added a score late in the
#: file and pushed a from-scratch compact build one pass over the old limit.
_MAX_ATTEMPTS = 8


def _lualatex(tex_file: Path) -> None:
    log_file = tex_file.with_suffix(".log")
    errors: list[str] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        errors = _run_pass(tex_file, str(attempt))
        if not errors:
            break
        logger.warning(
            "Erneuter Versuch (Autocompile-Flattern), Durchlauf %d/%d.",
            attempt, _MAX_ATTEMPTS,
        )
    else:
        for line in errors[:10]:
            logger.error("LaTeX: %s", line)
        raise CompileError(
            f"LaTeX meldet nach {_MAX_ATTEMPTS} Durchläufen weiterhin Fehler — "
            f"siehe „{log_file}“."
        )
    # One extra pass so cross-references and page counts settle.
    errors = _run_pass(tex_file, "final")
    if errors:
        for line in errors[:10]:
            logger.error("LaTeX: %s", line)
        raise CompileError(f"LaTeX meldet Fehler im letzten Durchlauf — siehe „{log_file}“.")


def page_count(pdf: Path) -> int:
    pages = len(PdfReader(pdf).pages)
    logger.debug("„%s“ hat %d Seiten.", pdf.name, pages)
    return pages


def compile_pdf(tex_file: Path) -> Path:
    """Compile a staged ``.tex`` (in its own folder) to ``<stem>.pdf``."""
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

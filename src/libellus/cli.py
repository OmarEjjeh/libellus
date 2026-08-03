"""CLI: ``libellus build feasts/2026-09-18-lambertus.yaml`` → booklet PDFs."""

from __future__ import annotations

import asyncio
import datetime
import logging
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer

from libellus.bundle import BundleError, bundle
from libellus.compile import CompileError, compile_pdf, impose, page_count
from libellus.errors import FeastFileError
from libellus.imagedata import InlineImageError
from libellus.formdata import FORM_FILE, FormDataError, island_is_current, rewrite_island
from libellus.latin import draft_slug, draft_stamp
from libellus.magnificat import (
    SYSTEM_DIR,
    MagnificatSystemError,
    stale_systems,
    write_systems,
)
from libellus.psalmtone import PsalmToneError
from libellus.render import render
from libellus.resolve import build_context, load_spec
from libellus.stage import stage

logger = logging.getLogger(__name__)

app = typer.Typer(help="Vesper-Heft aus einer Fest-YAML-Datei bauen.")


#: External tools the compile + imposition steps shell out to. `gregorio` is
#: called by us now rather than by LuaTeX (ADR-0032), so its absence has to stop
#: the compile here, where it downgrades to staging, instead of failing mid-run.
LATEX_TOOLS = ("gregorio", "lualatex", "pdfjam", "pdftk")


def build(
    feast_yaml: Path,
    root: Path,
    run_latex: bool = True,
    draft: bool = False,
    compact: bool | None = None,
    builds: Path | None = None,
) -> Path:
    """Validate → resolve → render → stage; then compile + impose in the folder.

    :param run_latex: If False, stop after staging (for latex-less
        environments — the folder builds standalone via its Makefile).
        Also downgraded to False, with a warning, when the LaTeX tools
        are not on PATH.
    :param draft: Mark every page as a draft. OR-ed with the spec's own
        `draft:` field — either alone suffices, neither clears the other
        (ADR-0021).
    :param compact: Build a Kurzfassung, or None to follow the spec's own
        `compact:` field. Unlike a draft, this one can be switched both ways
        from here: True and False both override the field (ADR-0022).
    :param builds: Where staged folders go; defaults to ``root/"build"``. Tests
        point it at a temporary folder: ``stage()`` wipes whatever folder it is
        given, so building into the real ``build/`` would delete the PDFs
        somebody has open — which is exactly what a test run used to do.
    :return: The staged folder (no LaTeX run) or the plain PDF.
    """
    if run_latex:
        missing = [tool for tool in LATEX_TOOLS if shutil.which(tool) is None]
        if missing:
            logger.warning(
                "Nicht im PATH: %s — LaTeX wird übersprungen, es wird nur der "
                "Satzordner erzeugt.",
                ", ".join(missing),
            )
            run_latex = False
    spec = load_spec(feast_yaml)
    stem = feast_yaml.stem
    is_compact = spec.compact if compact is None else compact
    if is_compact:
        # own stem, so a Kurzfassung and the full booklet can coexist —
        # stage() wipes whatever folder it is given
        stem = f"{stem}-kurzfassung"
        logger.info(
            "Kurzfassung: nur der erste Vers in Noten, Satzordner „%s“.", stem
        )
    stamp = None
    if draft or spec.draft:
        # One `now` for both the folder name and the printed line, so a later
        # `make` in that folder can never contradict the folder's own name.
        moment = datetime.datetime.now()
        stamp = draft_stamp(moment)
        stem = f"{stem}-{draft_slug(moment)}"
        logger.info("Entwurf-Modus: „%s“ auf jeder Seite, Satzordner „%s“.", stamp, stem)
    resolved = build_context(spec, root, stamp, is_compact)
    tex_source = render(spec.rite, resolved.context, root)
    build_dir = stage(
        tex_source, resolved.assets, stem, root, (builds or root / "build") / stem
    )
    if not run_latex:
        print(f"Satzordner erstellt: {build_dir} — dort „make“ ausführen für die PDFs.")
        return build_dir

    pdf = compile_pdf(build_dir / f"{stem}.tex")
    pages = page_count(pdf)
    # The template pads with ornament-only pages (partials/filler.tex.j2);
    # this only guards against that TeX logic silently breaking.
    if pages % 4:
        raise CompileError(
            f"Seitenzahl {pages} ist nicht durch 4 teilbar — die "
            f"Zierseiten-Logik in der Vorlage greift nicht."
        )
    booklet, duplex = asyncio.run(impose(pdf))
    print(f"Fertig: {pdf} ({pages} Seiten), {booklet.name}, {duplex.name}")
    return pdf


@app.callback()
def main(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Mehr Ausgaben.")
    ] = False,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s · %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command("build")
def build_command(
    feast: Annotated[
        Path, typer.Argument(help="Fest-Datei, z. B. feasts/2026-09-18-lambertus.yaml")
    ],
    no_latex: Annotated[
        bool,
        typer.Option(
            "--no-latex",
            help="Nur den Satzordner erzeugen; LaTeX, pdfjam und pdftk nicht aufrufen.",
        ),
    ] = False,
    draft: Annotated[
        bool,
        typer.Option(
            "--draft",
            help="Jede Seite als Entwurf kennzeichnen („PRO MANUSCRIPTO“ und "
            "Erstellungszeit). Steht „draft: true“ in der Fest-Datei, ist es "
            "ohnehin ein Entwurf — abschalten lässt sich das nur dort.",
        ),
    ] = False,
    compact: Annotated[
        bool | None,
        typer.Option(
            "--compact/--no-compact",
            help="Kurzfassung: nur der erste Vers je Psalm und des Magnificat "
            "steht in Noten, die weiteren als punktierter Text; vom Hymnus nur "
            "die erste Strophe. Ohne Angabe entscheidet „compact:“ in der "
            "Fest-Datei; „--no-compact“ hebt das Feld auf.",
        ),
    ] = None,
) -> None:
    """Heft-PDFs für ein Fest bauen."""
    if not feast.is_file():
        print(f"Die Datei „{feast}“ wurde nicht gefunden.", file=sys.stderr)
        raise typer.Exit(1)
    try:
        build(feast, Path.cwd(), run_latex=not no_latex, draft=draft, compact=compact)
    except FeastFileError as exc:
        print("Die Fest-Datei hat Fehler:\n", file=sys.stderr)
        for message in exc.messages:
            print(f"  • {message}", file=sys.stderr)
        raise typer.Exit(1) from exc
    except CompileError as exc:
        print(f"Der Satz ist fehlgeschlagen: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc


@app.command("bundle")
def bundle_command(
    feast: Annotated[
        Path, typer.Argument(help="Fest-Datei, z. B. feasts/2026-09-18-lambertus.yaml")
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Zieldatei; ohne Angabe „<name>-gebündelt.yaml“ neben dem Original.",
        ),
    ] = None,
) -> None:
    """Fest-Datei mit allen Noten und Bildern in eine einzige Datei packen."""
    if not feast.is_file():
        print(f"Die Datei „{feast}“ wurde nicht gefunden.", file=sys.stderr)
        raise typer.Exit(1)
    destination = output or feast.with_name(f"{feast.stem}-gebündelt.yaml")
    if destination.resolve() == feast.resolve():
        print(
            "Ziel und Quelle sind dieselbe Datei — das Bündel würde das "
            "Original überschreiben.",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    try:
        written = bundle(feast, Path.cwd(), destination)
    except FeastFileError as exc:
        print("Die Fest-Datei hat Fehler:\n", file=sys.stderr)
        for message in exc.messages:
            print(f"  • {message}", file=sys.stderr)
        raise typer.Exit(1) from exc
    except (BundleError, InlineImageError) as exc:
        print(f"Bündeln fehlgeschlagen: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc
    size = written.stat().st_size / 1024**2
    print(
        f"Gebündelt: {written} ({size:.1f} MB) — diese Datei allein genügt, "
        f"„libellus build {written}“ baut das Heft."
    )


@app.command("magnificat-systems")
def magnificat_systems_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Nur prüfen, ob die Systeme aktuell sind; veraltet → "
            "Fehlercode 1, nichts wird geschrieben.",
        ),
    ] = False,
) -> None:
    """Die Magnificat-Systeme der Kurzfassung neu erzeugen (ADR-0022)."""
    root = Path.cwd()
    try:
        if check:
            stale = stale_systems(root)
            if stale:
                print(
                    f"Diese Magnificat-Systeme in „{SYSTEM_DIR}“ sind veraltet "
                    f"oder fehlen: {', '.join(stale)} — bitte „uv run libellus "
                    f"magnificat-systems“ ausführen.",
                    file=sys.stderr,
                )
                raise typer.Exit(1)
            print(f"Die Magnificat-Systeme in „{SYSTEM_DIR}“ sind aktuell.")
            return
        changed = write_systems(root)
        if changed:
            print(f"{len(changed)} Magnificat-System(e) neu geschrieben in „{SYSTEM_DIR}“.")
        else:
            print(f"Die Magnificat-Systeme in „{SYSTEM_DIR}“ waren schon aktuell.")
    except (MagnificatSystemError, PsalmToneError) as exc:
        print(f"Magnificat-Systeme: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc


@app.command("export-form-data")
def export_form_data_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Nur prüfen, ob der Datenblock im Formular aktuell ist; "
            "veraltet → Fehlercode 1, nichts wird geschrieben.",
        ),
    ] = False,
) -> None:
    """Datenblock im Formular neu schreiben (ADR-0004)."""
    try:
        if check:
            if not island_is_current(Path.cwd()):
                print(
                    f"Der Datenblock in „{FORM_FILE}“ ist veraltet — bitte "
                    "„uv run libellus export-form-data“ ausführen.",
                    file=sys.stderr,
                )
                raise typer.Exit(1)
            print(f"Der Datenblock in „{FORM_FILE}“ ist aktuell.")
        elif rewrite_island(Path.cwd()):
            print(f"Datenblock in „{FORM_FILE}“ neu geschrieben.")
        else:
            print(f"Der Datenblock in „{FORM_FILE}“ war schon aktuell — nichts geändert.")
    except (FormDataError, PsalmToneError) as exc:
        print(f"Datenblock: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()

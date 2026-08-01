#!/usr/bin/env -S uv run --script
"""Proof sheet for the Kurzfassung's Magnificat notation (ADR-0022).

Builds `magnificat-systeme-korrektur.pdf` at the repo root: every tone as the
compact booklet prints it, at the booklet's own page size, fonts and gregorio
settings, so the line breaks on the sheet are the ones that will print. Two
parts, because the booklet does two different things:

1. The 29 tones with a **two-verse system** — verses 1 and 2 under one line of
   notes, reciting notes hollow, the notes verse 1 has no words for standing
   empty. Read straight from the committed `chant/magnificat/kurzfassung/`.
2. The 4 tones **without** one (`2D`, `8G`, `8G*`, `8c`): for those the booklet
   notates both verses in full, and so does this sheet — generated here exactly
   as the booklet generates them, closed notes and all.

Why those four and not ten. Ten tones have a shortened first-half formula for
„Magníficat", but in all ten the *termination* is identical and only the mediant
diverges, in two kinds. Six differ in the mediant's **final note** alone („cat"
on `i.` where verse 2 has `j.`): those two notes stand side by side at the end
of the line and the tone collapses, so a shared system works. The other four
differ in the **intonation** (`8G` is `g hg gj` against `g h j`, compound neumes
against plain), where a merged line would alternate between the verses note by
note. "The first verse has its own festive melody" was the first explanation
offered for all ten and holds only for those four — do not restore it.

Run from the repository root:

    uv run scripts/magnificat-proof/generate.py

Not part of the build. The systems themselves come from
`libellus magnificat-systems`; run that first if the generator changed.

**Checking the sheet for collisions: never by eye, and never with `pdftotext`.**
It merges glyphs that touch into one word, so an overlap scan finds nothing and
a 4pt collision passes as clean — that mistake was made twice here, and the
sheet was twice reported fixed when it was not. Use `pdfplumber` character
boxes, skip the chant font (neume glyphs legitimately share space), and allow
about 1.2pt for real kerning pairs („Te", „Ve").
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from libellus.compile import compile_pdf  # noqa: E402
from libellus.magnificat import SYSTEM_DIR  # noqa: E402
from libellus.psalmtone import generate_verses, list_toni  # noqa: E402

logger = logging.getLogger("magnificat-proof")

WORK_DIR = Path("build/magnificat-proof")
OUTPUT = Path("magnificat-systeme-korrektur.pdf")

#: Copied from template/partials/preamble.tex.j2 — everything that affects how
#: a score and its second text line are set. Kept in step by hand: a proof sheet
#: that sets its scores differently from the booklet proves nothing.
PREAMBLE = r"""\documentclass[11pt,a5paper]{article}
\usepackage[a5paper,top=18mm,bottom=20mm,inner=18mm,outer=13mm,
  headheight=14pt,includehead]{geometry}
\usepackage{fontspec}
\setmainfont{EB Garamond}[Ligatures=TeX,Numbers=OldStyle]
\usepackage[tracking=true]{microtype}
\usepackage{xcolor}
\definecolor{rubricred}{HTML}{8B1414}
\usepackage[autocompile]{gregoriotex}
\gresetlinecolor{black}
\grechangedim{spaceabovelines}{0.35cm}{scalable}
\grechangedim{spacebeneathtext}{0.15cm}{scalable}
\gresetgregoriofont[op]{greciliae}
\grechangestyle{translation}{}
% Gregorio typesets a translation in an \hbox to 0pt, so it claims no width and
% a line wider than the lyric above prints into its neighbour. Same patch as the
% booklet's preamble — pad the syllable by the overhang. Keep them in step.
\makeatletter
\newsavebox{\gretransbox}
\let\gre@orig@writetranslation\GreWriteTranslation
\def\GreWriteTranslation#1{%
  \gre@orig@writetranslation{#1}%
  \sbox\gretransbox{\gre@style@translation#1\endgre@style@translation}%
  \ifdim\wd\gretransbox>\wd\gre@box@syllabletext
    \kern\dimexpr\wd\gretransbox-\wd\gre@box@syllabletext\relax
  \fi}
\makeatother
\gresetinitiallines{0}
\setlength{\parindent}{0pt}
\usepackage{setspace}
\setstretch{1.08}
\pagestyle{plain}
"""


def tone_label(folder: str) -> str:
    """Cache folder back to the books' spelling: ``4astar`` → ``4 A*``."""
    if folder == "peregrinus":
        return "peregrinus"
    mode, ending = folder[0], folder[1:].replace("star", "*")
    return f"{mode} {ending[:1].upper()}{ending[1:]}".strip()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = Path.cwd()
    if not (root / SYSTEM_DIR).is_dir():
        raise SystemExit(
            f"„{SYSTEM_DIR}“ fehlt — bitte zuerst „uv run libellus "
            f"magnificat-systems“ ausführen."
        )
    work = root / WORK_DIR
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    systems: list[str] = []
    pairs: list[tuple[str, str, str]] = []  # (folder, verse 1 stem, verse 2 stem)
    for label in list_toni():
        folder, verses = generate_verses("magnificat", label)
        system = root / SYSTEM_DIR / f"{folder}.gabc"
        if system.is_file():
            shutil.copy(system, work / f"{folder}.gabc")
            systems.append(folder)
            continue
        # no system for this tone: its first verse has the festive melody, so
        # the booklet notates both verses — generated closed, exactly as there
        for number, verse in enumerate(verses[:2], start=1):
            (work / f"{folder}-v{number:02d}.gabc").write_text(verse, encoding="utf-8")
        pairs.append((folder, f"{folder}-v01", f"{folder}-v02"))
    logger.info(
        "%d Töne mit System, %d mit zwei vollständigen Versen.", len(systems), len(pairs)
    )

    body = [
        r"{\centering\large\scshape Magnificat — Kurzfassung\par}\medskip",
        r"{\footnotesize",
        r"Zwei Fassungen, weil das Heft zwei verschiedene Dinge tut.\par\medskip",
        r"\textbf{I. Ein System für Vers 1 und 2} (" + str(len(systems)) + r" Töne) — so",
        r"setzt es der Liber Usualis: die Noten des vollen Verses, darunter die Silben",
        r"von Vers 1 dort, wo sie hinfallen, darunter Vers 2. \textbf{Hohle Noten} sind",
        r"Rezitationsnoten. Wo Vers 1 keine Silben hat („Magní-fi- \dots\ cat“), stehen",
        r"die Noten ohne Text — \emph{das ist Absicht} und der Grund für das ganze",
        r"Verfahren: sonst zeigte das Heft die Kadenz nie, die die übrigen elf Verse",
        r"singen.\par\medskip",
        r"\textbf{II. Beide Verse vollständig} (" + str(len(pairs)) + r" Töne) — dort hat",
        r"Vers 1 eine eigene, feierliche Melodie (Ton 8G etwa: „Ma-gní-fi-cat“ auf",
        r"\emph{g hg gj j} gegen „Et ex-sul-“ auf \emph{g h j}), die beiden Verse können",
        r"also kein System teilen. Das Heft notiert für diese Töne beide Verse ganz,",
        r"und so stehen sie hier.\par\medskip",
        r"\textbf{Zu prüfen:} Sitzen die Silben von Vers 1 auf den richtigen Noten?",
        r"Stehen die hohlen Noten dort, wo Ihr Liber sie hohl setzt? Sind die",
        r"Silbentrennungen beider Zeilen richtig? Und: setzt Ihr Liber für die Töne",
        r"unter II. \emph{doch} ein gemeinsames System — dann weicht die Silbenverteilung",
        r"von jgabc ab und wir brauchen die des Buches.\par}",
        r"\bigskip",
        r"{\centering\footnotesize\scshape I. Ein System für Vers 1 und 2\par}\medskip",
    ]
    for folder in systems:
        body += [
            r"\noindent{\footnotesize\scshape Tonus " + tone_label(folder) + r"}\par\nopagebreak",
            r"\gregorioscore{" + folder + r"}\par\vspace{0.45cm}",
        ]
    body += [
        r"\clearpage",
        r"{\centering\footnotesize\scshape II. Beide Verse vollständig\par}\medskip",
        r"{\footnotesize Ton 1 mit der feierlichen Melodie, Ton 2 wie alle",
        r"folgenden Verse.\par}\medskip",
    ]
    for folder, first, second in pairs:
        body += [
            r"\noindent{\footnotesize\scshape Tonus " + tone_label(folder) + r"}\par\nopagebreak",
            r"\gregorioscore{" + first + r"}\par\nopagebreak",
            r"\gregorioscore{" + second + r"}\par\vspace{0.45cm}",
        ]

    tex = work / "magnificat-systeme-korrektur.tex"
    tex.write_text(
        PREAMBLE + "\\begin{document}\n" + "\n".join(body) + "\n\\end{document}\n",
        encoding="utf-8",
    )
    pdf = compile_pdf(tex)
    shutil.copy(pdf, root / OUTPUT)
    logger.info("Korrekturbogen: %s (Arbeitsordner %s).", OUTPUT, WORK_DIR)


if __name__ == "__main__":
    main()

"""Render the ordo skeleton for a feast via Jinja2 with LaTeX-safe delimiters."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from libellus.paths import source_of

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path("template")


#: Every LaTeX special renders as its literal glyph — text fields are pure
#: plain text (ADR-0002); the old \/{}/~ pass-through is closed.
_TEX_SPECIALS = {
    "\\": "\\textbackslash{}",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}",
    "&": "\\&",
    "%": "\\%",
    "#": "\\#",
    "$": "\\$",
    "_": "\\_",
}

_TEX_SPECIALS_PATTERN = re.compile("|".join(re.escape(c) for c in _TEX_SPECIALS))


def _tex_escape(text: str | None) -> str:
    """Convert plain YAML prose to LaTeX (the ``|tex`` filter).

    Escapes every special character, then binds ℣./℟. marks to their
    following word with a non-breaking space (authors type a plain space,
    as printed in the chant books).

    ``None`` renders as nothing: every ``de:`` field is optional for a
    ``latin_only`` feast (ADR-0025), so a missing translation is a value here,
    not a mistake. A genuinely misspelled field name is still caught, by
    StrictUndefined rather than here.
    """
    if text is None:
        return ""
    escaped = _TEX_SPECIALS_PATTERN.sub(lambda m: _TEX_SPECIALS[m.group()], text)
    return escaped.replace("℣. ", "℣.~").replace("℟. ", "℟.~")


def _style_pause_marks(text: str) -> str:
    """Style literal † and * pause marks rubric-red, bound to the following word.

    Matches the booklet's \\cros/\\vc/\\rc convention: red mark, then a
    non-breaking space so the mark never ends a line alone.
    """
    return re.sub(
        r"([†*])( ?)",
        lambda m: "{\\color{rubricred}" + m.group(1) + "}" + ("~" if m.group(2) else ""),
        text,
    )


def _style_pointing(lines: list[str]) -> str:
    """Pointed Latin lines (``gabc.pointed_halves``) as LaTeX — the ``|pointing``
    filter of a Kurzfassung (ADR-0022).

    The tone engine's accent and preparation tags become \\textbf/\\textit,
    the pause marks turn rubric-red like everywhere else, and the lines break
    where the chant breaks them. The indent of a continuation line belongs to
    the surrounding macro (\\hangindent), not here.
    """
    styled: list[str] = []
    for line in lines:
        # escape first: the tags survive it untouched, so no LaTeX the text
        # itself contains can reach the output as a command
        text = _tex_escape(line)
        text = re.sub(r"<b>(.*?)</b>", r"\\textbf{\1}", text)
        text = re.sub(r"<i>(.*?)</i>", r"\\textit{\1}", text)
        styled.append(_style_pause_marks(text))
    return "\\\\\n".join(styled)


def make_environment(root: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(source_of(TEMPLATE_DIR, root)),
        # LaTeX-safe delimiters: the defaults ({{ }}, {% %}) collide with TeX.
        block_start_string="\\BLOCK{",
        block_end_string="}",
        variable_start_string="\\VAR{",
        variable_end_string="}",
        comment_start_string="\\#{",
        comment_end_string="}",
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["tex"] = _tex_escape
    # plain multi-line YAML text: newlines become LaTeX line breaks
    env.filters["breaks"] = lambda text: text.replace("\n", "\\\\\n")
    env.filters["pausemarks"] = _style_pause_marks
    env.filters["pointing"] = _style_pointing
    return env


def render(rite: str, context: dict[str, Any], root: Path) -> str:
    """Render the skeleton for ``rite`` (template/<rite>.tex.j2) to LaTeX source."""
    env = make_environment(root)
    template_name = f"{rite}.tex.j2"
    tex_source = env.get_template(template_name).render(**context)
    logger.info(
        "Vorlage „%s“ gerendert: %d Zeilen LaTeX.", template_name, tex_source.count("\n")
    )
    return tex_source

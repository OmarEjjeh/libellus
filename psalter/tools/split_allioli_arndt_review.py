#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Split the Allioli-Arndt review page into four, one per Hore (issue #1).

One 150-psalm page overwhelms a reviewer. The eu1980 recut was reviewed the
same way: `psalm-spotcheck-vespers-review.html`, `-komplet-review.html` and
`-terz-sext-non-review.html` at the repo root (all gitignored, all
untracked - the pattern this script follows). This produces the same four
groupings for the Allioli-Arndt draft, covering the full 150 psalms + the
Magnificat rather than just the subset those three files touched:

- Vesperpsalmen: 109-147
- Komplet: 4, 90, 132
- Terz/Sext/Non: 119-128
- Alles andere: 1-108 (minus 4, 90, already in Komplet), 148-150, Magnificat

The 119-128 and 132 overlaps with the Vesper range are intentional and
mirror the original three files - those psalms genuinely serve more than
one Hore.

Reads the already-committed `psalter/allioli-arndt/*.yaml` plus the
alignment notes recorded in `allioli-arndt-work-items.json` (produced by
`scrape_allioli_arndt.py`, gitignored/untracked working material) - this
script does not re-fetch or re-align anything.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_allioli_arndt import (  # noqa: E402
    OUTPUT_DIR,
    clementine_lines,
    clementine_lines_magnificat,
    load_eu1980,
    load_eu1980_magnificat,
)

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
WORK_ITEMS_FILE = SCRIPT_DIR / "allioli-arndt-work-items.json"
TEMPLATE_FILE = SCRIPT_DIR / "allioli-arndt-review-template.html"
OLD_SINGLE_FILE = REPO_ROOT / "allioli-arndt-review.html"

VESPERS = list(range(109, 148))
KOMPLET = [4, 90, 132]
TERZ_SEXT_NON = list(range(119, 129))
REST = [n for n in range(1, 109) if n not in KOMPLET] + [148, 149, 150]

GROUPS = [
    {
        "key": "vespers",
        "filename": "psalm-spotcheck-allioli-arndt-vespers-review.html",
        "title": "Vesperpsalmen 109–147",
        "description": "die Vesperpsalmen 109–147 (39 Psalmen)",
        "numbers": VESPERS,
        "magnificat": False,
    },
    {
        "key": "komplet",
        "filename": "psalm-spotcheck-allioli-arndt-komplet-review.html",
        "title": "Komplet-Psalmen",
        "description": "die Komplet-Psalmen 4, 90 und 132",
        "numbers": KOMPLET,
        "magnificat": False,
    },
    {
        "key": "terz-sext-non",
        "filename": "psalm-spotcheck-allioli-arndt-terz-sext-non-review.html",
        "title": "Terz-, Sext- und Non-Psalmen 119–128",
        "description": "die Psalmen 119–128 für Terz, Sext und Non",
        "numbers": TERZ_SEXT_NON,
        "magnificat": False,
    },
    {
        "key": "rest",
        "filename": "psalm-spotcheck-allioli-arndt-rest-review.html",
        "title": "die übrigen Psalmen",
        "description": (
            "die übrigen Psalmen (1–108 ohne die schon bei Komplet "
            "gezeigten 4 und 90, sowie 148–150) und das Magnificat"
        ),
        "numbers": REST,
        "magnificat": True,
    },
]


def note_for_item(item: dict[str, Any]) -> str:
    nums = [r["number"] for r in item["sung_verses"]]
    label = "Vers " + str(nums[0]) if len(nums) == 1 else "Verse " + "/".join(str(n) for n in nums)
    if item["type"] == "trim":
        text = f"{label}: Ueberschrift/Titel entfernt (kein Aequivalent im gesungenen Text)."
    elif item["type"] == "split":
        av = item["allioli_verses"][0]["number"]
        text = f"{label}: aus Allioli-Vers {av} neu aufgeteilt (2. Durchgang, Editor-KI) - bitte Zuschnitt pruefen."
    else:  # tangled
        avs = "/".join(str(v["number"]) for v in item["allioli_verses"])
        text = (
            f"{label}: aus Allioli-Versen {avs} neu zusammengefuehrt und aufgeteilt "
            "(2. Durchgang, Editor-KI) - bitte Zuschnitt pruefen."
        )
    if item["superscription_latin"] and item["type"] != "trim":
        text += " (erster Vers zusaetzlich um Ueberschrift gekuerzt.)"
    return text


def build_psalm_entry(psalmus: int, items_by_psalm: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target = OUTPUT_DIR / f"{psalmus}.yaml"
    sung_lines = clementine_lines(psalmus)
    eu1980 = load_eu1980(psalmus)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    verses = {int(k): v for k, v in data["verses"].items()}
    key = str(psalmus)
    touched = items_by_psalm.get(key, [])
    touched_verses = {r["number"] for item in touched for r in item["sung_verses"]}
    notes = [note_for_item(item) for item in touched]
    rows = []
    for i in range(len(sung_lines)):
        n = i + 1
        rows.append(
            {
                "label": str(n),
                "latin": sung_lines[i],
                "allioli": verses.get(n, ""),
                "eu1980": eu1980.get(n, ""),
                "needs_review": n in touched_verses or not verses.get(n, "").strip(),
            }
        )
    return {"number": psalmus, "status": "regrouped" if notes else "clean", "notes": notes, "rows": rows}


def build_magnificat_entry(items_by_psalm: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target = OUTPUT_DIR / "magnificat.yaml"
    sung_lines = clementine_lines_magnificat()
    eu1980 = load_eu1980_magnificat()
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    verses = {int(k): v for k, v in data["verses"].items()}
    touched = items_by_psalm.get("Magnificat", [])
    touched_verses = {r["number"] for item in touched for r in item["sung_verses"]}
    notes = [note_for_item(item) for item in touched]
    rows = []
    for i in range(len(sung_lines)):
        n = i + 1
        rows.append(
            {
                "label": str(n),
                "latin": sung_lines[i],
                "allioli": verses.get(n, ""),
                "eu1980": eu1980.get(n, ""),
                "needs_review": n in touched_verses or not verses.get(n, "").strip(),
            }
        )
    return {"number": "Magnificat", "status": "regrouped" if notes else "clean", "notes": notes, "rows": rows}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)

    work_items = json.loads(WORK_ITEMS_FILE.read_text(encoding="utf-8"))
    items_by_psalm: dict[str, list[dict[str, Any]]] = {}
    for item in work_items:
        items_by_psalm.setdefault(str(item["psalm"]), []).append(item)

    entries_by_number: dict[int, dict[str, Any]] = {
        n: build_psalm_entry(n, items_by_psalm) for n in range(1, 151)
    }
    magnificat_entry = build_magnificat_entry(items_by_psalm)

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    seen: set[int] = set()

    for group in GROUPS:
        results = [entries_by_number[n] for n in group["numbers"]]
        if group["magnificat"]:
            results.append(magnificat_entry)
        seen.update(group["numbers"])

        html = (
            template.replace("__SCOPE_TITLE__", group["title"])
            .replace("__SCOPE_DESCRIPTION__", group["description"])
            .replace("__SCOPE_KEY__", group["key"])
            .replace("__PSALMS_JSON__", json.dumps(results, ensure_ascii=False))
        )
        target = REPO_ROOT / group["filename"]
        target.write_text(html, encoding="utf-8")
        logger.info("%s: %d Eintraege -> %s", group["key"], len(results), group["filename"])

    missing = set(range(1, 151)) - seen
    if missing:
        logger.warning("Nicht in irgendeiner Gruppe enthalten: %s", sorted(missing))

    if OLD_SINGLE_FILE.is_file():
        OLD_SINGLE_FILE.unlink()
        logger.info("Alte Einzelseite entfernt: %s", OLD_SINGLE_FILE.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())

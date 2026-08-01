"""Rewrite validation failures into plain-language German messages.

Successors read these at the top of the GitHub Actions job summary; they
must be understandable without knowing Python or Pydantic.
"""

from __future__ import annotations

from pydantic import ValidationError


class FeastFileError(Exception):
    """A feast YAML problem, carrying ready-to-print German messages."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("\n".join(messages))


def _field_path(loc: tuple) -> str:
    """Render a Pydantic error location like ('antiphonae', 2, 'tonus') as „antiphonae → 3. Eintrag → tonus“."""
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"{item + 1}. Eintrag")
        else:
            parts.append(str(item))
    return " → ".join(parts)


#: Pydantic error type → German template ({field}, {input} available).
_GERMAN: dict[str, str] = {
    "missing": "Das Feld „{field}“ fehlt.",
    "extra_forbidden": "Unbekanntes Feld „{field}“ — vermutlich ein Tippfehler.",
    "string_type": "Das Feld „{field}“ muss ein Text sein (nicht {input!r}).",
    "int_type": "Das Feld „{field}“ muss eine Zahl sein (nicht {input!r}).",
    "int_parsing": "Das Feld „{field}“ muss eine Zahl sein (nicht {input!r}).",
    "greater_than_equal": "Das Feld „{field}“ ist zu klein: {input!r}.",
    "less_than_equal": "Das Feld „{field}“ ist zu groß: {input!r}.",
    "date_type": "Das Feld „{field}“ muss ein Datum sein, z. B. 2026-09-18 (nicht {input!r}).",
    "date_from_datetime_parsing": "Das Feld „{field}“ muss ein Datum im Format JJJJ-MM-TT sein, z. B. 2026-09-18 (nicht {input!r}).",
    "literal_error": "Das Feld „{field}“ hat einen ungültigen Wert: {input!r}. {expected_de}",
    "list_type": "Das Feld „{field}“ muss eine Liste sein.",
    "model_type": "Das Feld „{field}“ muss ein Block mit Unterfeldern sein (Einrückung prüfen).",
    "path_type": "Das Feld „{field}“ muss ein Dateipfad sein.",
}

#: Extra explanation for literal fields, keyed by the last element of the location.
_LITERAL_HINTS: dict[str, str] = {
    "rite": "Gültige Riten: romanum-1962, monasticum, romanum-cum-precibus.",
    "vesperae": "Gültig sind: I oder II (erste oder zweite Vesper).",
    "border": "Gültige Werte: none, vine, grapevine, knot, feather.",
    "rank": (
        "Gültige Werte (vor 1955): Duplex I classis, Duplex II classis, Duplex majus, "
        "Duplex, Duplex minus, Semiduplex, Simplex, Feria („Duplex“ und „Duplex "
        "minus“ sind derselbe Rang, nur anders geschrieben). Gültige Werte "
        "(Codex Rubricarum 1960): I classis, II classis, III classis, IV classis."
    ),
}


def german_messages(error: ValidationError) -> list[str]:
    """Translate a Pydantic ValidationError into a list of German sentences."""
    messages: list[str] = []
    for err in error.errors():
        field = _field_path(err["loc"]) or "(Dateianfang)"
        if err["type"] == "value_error":
            # Messages raised in our own validators are already German;
            # prefix the location so field-level errors are findable.
            msg = err["msg"].removeprefix("Value error, ")
            messages.append(f"{field}: {msg}" if err["loc"] else msg)
            continue
        template = _GERMAN.get(err["type"])
        if template is None:
            messages.append(f"Das Feld „{field}“ ist ungültig: {err['msg']}")
            continue
        last = err["loc"][-1] if err["loc"] else ""
        messages.append(
            template.format(
                field=field,
                input=err.get("input"),
                expected_de=_LITERAL_HINTS.get(str(last), ""),
            ).strip()
        )
    return messages

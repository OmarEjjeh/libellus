"""Which psalm tone an antiphon wants — one resolver, two operations (issue #46).

An antiphon is followed by a psalm sung to a `Tonus`, and which tone that is
has to come from somewhere. Two things can say, and they are not two
implementations of one function:

**Measurement** reads the antiphon's own transcribed `Euouae`. Every one of
the engine's 33 endings has a distinct EUOUAE, so where a transcription
prints one it names its tone outright — but most scores print none.

**Inference** applies the traditional connection rule: a differentia is
chosen so that its termination's closing note runs smoothly into the note the
antiphon starts again on. It needs nothing but the mode and the first note, so
it is available everywhere — but not every mode's endings close on different
notes, so it ties.

They cover each other's blind spots. Mode 1's ``D`` and ``D-`` close on the
same note and the rule cannot separate them; their EUOUAEs differ at the
fifth neume and measurement can.

Three properties hold whatever the two of them find:

1. **Never guess.** An ambiguous derivation yields the whole candidate set,
   a failed one yields nothing. No single label is ever synthesised.
2. **Never auto-fill** ``tonus:``. The schema field stays human-authored.
   This is a suggestion engine and a validator, not an input to typesetting:
   ADR-0016/ADR-0017 make the EUOUAE *derived* from the tone, and running that
   arrow backwards into the spec would close the loop on itself.
3. **Disagreement is a signal, not an error.** Where measurement and inference
   both fire and contradict each other, either the transcription is wrong or
   the antiphon uses a differentia that does not follow the convention — and
   the rule is a convention, not a law. Three of the antiphons the two shipped
   booklets sing contradict it, once their ``euouae:`` assertions are given
   alongside. Surface it; do not pick.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libellus.gabc import (
    CANONICAL_CLEF,
    differentia_candidates,
    final_pitch_class,
    find_clef,
    find_euouae,
    find_mode,
    opening_pitch_class,
)

logger = logging.getLogger(__name__)


class Provenance(StrEnum):
    """What a candidate rests on.

    Declared strongest first — a transcription read exactly, a transcription
    read tolerantly, a convention applied, the mode alone — which is the order
    :func:`resolve_tonus` returns candidates in.
    """

    #: Measured: the score's EUOUAE matches this ending completely.
    EUOUAE = "euouae"
    #: Measured tolerantly: it matches on the leading neumes only, which is
    #: what an embellished or mora-less final neume looks like (issue #33).
    EUOUAE_LEADING = "euouae-leading"
    #: Inferred: this ending closes on the note the antiphon opens on.
    CONNECTION = "connection"
    #: Neither fired, but the mode is known — so these are its endings, whole
    #: and unranked, for a human to choose from.
    MODE_ONLY = "mode-only"


#: The provenances that read the transcription rather than apply a convention.
_MEASURED = (Provenance.EUOUAE, Provenance.EUOUAE_LEADING)


class TonusCandidate(BaseModel):
    """One tone an antiphon might be sung to, and why it is being offered."""

    model_config = ConfigDict(frozen=True)

    tonus: str
    provenance: Provenance


def endings_of_mode(mode: str, euouae_per_tonus: dict[str, str]) -> list[str]:
    """Every ending the engine knows for one mode, in the engine's own order.

    A tone label opens with the mode a score declares — ``8G`` for ``mode:8``,
    ``peregrinus`` for ``mode:p`` — which is the whole of the relationship, and
    the reason nothing on this side keeps a table of modes and their endings.

    :param mode: As :func:`~libellus.gabc.find_mode` returns it.
    :param euouae_per_tonus: Tone label → EUOUAE, from
        ``psalmtone.euouae_per_tonus``.
    :return: The matching labels, empty for a mode spelled in a way the
        engine's labels do not (e.g. roman numerals).
    """
    if not mode:
        return []  # an empty prefix would match every label there is
    return [
        label for label in euouae_per_tonus if label.lower().startswith(mode.lower())
    ]


def resolve_tonus(
    gabc: str,
    euouae_per_tonus: dict[str, str],
    euouae: str | None = None,
    clef: str | None = None,
) -> list[TonusCandidate]:
    """Every tone a gabc score could be sung to, ranked, each tagged with why.

    Measurement first, then inference, then the mode's endings if neither
    fired — see the module docstring for what separates them. A label the two
    operations both propose appears twice, once per provenance: they are
    different statements about the same antiphon, and collapsing them would
    make agreement indistinguishable from inference having stayed silent.

    Pure: the tone table is a parameter rather than a call, so this is
    testable without a JavaScript runtime and callable from the browser.
    ``psalmtone.euouae_per_tonus`` raises where no runtime exists, and what
    that failure should read like belongs to whoever asked.

    :param gabc: A whole gabc score, headers included.
    :param euouae_per_tonus: Tone label → EUOUAE, from
        ``psalmtone.euouae_per_tonus`` — written in
        :data:`~libellus.gabc.CANONICAL_CLEF`.
    :param euouae: A EUOUAE to measure instead of the score's own — the feast
        spec's ``euouae:`` assertion, which records what a printed source
        shows for a score that transcribes none. Spelled in the score's clef.
    :param clef: The clef the score is notated under. Derived from the score
        itself unless given; a score naming none is read as canonical, which
        is what a caller holding a filename overrides in order to say so.
    """
    if clef is None:
        clef = find_clef(gabc) or CANONICAL_CLEF
    mode = find_mode(gabc)
    cue = euouae if euouae is not None else find_euouae(gabc)

    candidates = [
        *_measured(cue, euouae_per_tonus, clef),
        *_inferred(gabc, mode, euouae_per_tonus, clef),
    ]
    if not candidates and mode is not None:
        candidates = [
            TonusCandidate(tonus=label, provenance=Provenance.MODE_ONLY)
            for label in endings_of_mode(mode, euouae_per_tonus)
        ]
    logger.debug(
        "Psalmton abgeleitet (Modus %s, Schlüssel %s): %s.",
        mode, clef,
        ", ".join(f"{c.tonus} ({c.provenance})" for c in candidates) or "nichts",
    )
    return candidates


def _measured(
    euouae: str | None, euouae_per_tonus: dict[str, str], clef: str
) -> list[TonusCandidate]:
    """What a notated EUOUAE says, exactly or on its leading neumes.

    The two readings are alternatives, not a union: the tolerant one exists
    only for a EUOUAE that matches nothing exactly, and reporting it beside an
    exact match would widen a set that is already settled.
    """
    if euouae is None:
        return []
    exact, leading = differentia_candidates(euouae, euouae_per_tonus, clef)
    if exact:
        return [
            TonusCandidate(tonus=label, provenance=Provenance.EUOUAE) for label in exact
        ]
    return [
        TonusCandidate(tonus=label, provenance=Provenance.EUOUAE_LEADING)
        for label in leading
    ]


def _inferred(
    gabc: str, mode: str | None, euouae_per_tonus: dict[str, str], clef: str
) -> list[TonusCandidate]:
    """The connection rule: endings of the mode that close where the antiphon
    opens. Silent — not relaxed — when none of them do."""
    opening = opening_pitch_class(gabc, clef)
    if mode is None or opening is None:
        return []
    return [
        TonusCandidate(tonus=label, provenance=Provenance.CONNECTION)
        for label in endings_of_mode(mode, euouae_per_tonus)
        if final_pitch_class(euouae_per_tonus[label]) == opening
    ]


def labels_with(
    candidates: list[TonusCandidate], *provenances: Provenance
) -> list[str]:
    """The tone labels among ``candidates`` that rest on one of ``provenances``.

    Public because reading a candidate list back apart is what every caller
    does — and a caller writing its own comprehension over ``.provenance`` is
    the drift this module exists to prevent.
    """
    return [c.tonus for c in candidates if c.provenance in provenances]


def disagrees(candidates: list[TonusCandidate]) -> bool:
    """Whether measurement and inference both fired and named disjoint sets.

    Not an error (property 3). It is worth saying out loud all the same,
    because the other thing it can mean is a mistranscribed EUOUAE — which is
    exactly what the check in ``resolve`` exists to catch.
    """
    measured = set(labels_with(candidates, *_MEASURED))
    inferred = set(labels_with(candidates, Provenance.CONNECTION))
    return bool(measured and inferred and not measured & inferred)


def tonus_message(candidates: list[TonusCandidate]) -> str:
    """The German a surface prints beside an unfilled ``tonus:`` field.

    Every case says what it rests on, because a suggestion the author cannot
    weigh is worse than none. The five readings are genuinely five different
    situations — in particular a contradiction is not an absence, and neither
    is a mode without an ending.

    The cue is called *notiert* rather than the antiphon's own, because a
    measured candidate may equally have come from the ``euouae:`` assertion,
    which records what a printed source shows for a score transcribing none.
    """
    exact = labels_with(candidates, Provenance.EUOUAE)
    leading = labels_with(candidates, Provenance.EUOUAE_LEADING)
    inferred = labels_with(candidates, Provenance.CONNECTION)
    mode_only = labels_with(candidates, Provenance.MODE_ONLY)

    if disagrees(candidates):
        return (
            f"Die notierte Schlussformel nennt {_enumeration(exact + leading)}, "
            f"der Anfangston widerspricht dem und spräche für "
            f"{_enumeration(inferred)} — bitte prüfen, welcher Ton gemeint ist."
        )
    if exact:
        return f"Ton {_enumeration(exact)} — aus der notierten Schlussformel."
    if leading:
        return (
            f"Ton {_enumeration(leading)} — nach den ersten Neumen der "
            f"Schlussformel; die letzte weicht ab."
        )
    if inferred:
        return f"Ton {_enumeration(inferred)} — nach dem Anfangston der Antiphon."
    if mode_only:
        # The mode a label opens with — a digit for the eight numbered modes.
        # The tonus peregrinus is its own label and names no number, so it
        # cannot be announced that way.
        mode = mode_only[0][0]
        opening = f"Modus {mode} — " if mode.isdigit() else ""
        return f"{opening}Endung bitte wählen: {_enumeration(mode_only)}."
    return "Kein Psalmton ableitbar — bitte von Hand wählen."


def _enumeration(labels: list[str]) -> str:
    """Tone labels as a German enumeration: „8G“, „8G*“ oder „8c“."""
    quoted = [f"„{label}“" for label in labels]
    if len(quoted) < 2:
        return "".join(quoted)
    return f"{', '.join(quoted[:-1])} oder {quoted[-1]}"

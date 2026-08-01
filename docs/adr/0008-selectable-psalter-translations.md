# ADR-0008: Selectable psalter translations (de-<versio>.yaml variants)

Date: 2026-07-22
Status: superseded in part by ADR-0024 (2026-08-01)

> **Superseded:** the *mechanism* below stands — several German translations
> coexist and a feast picks one with `psalter_de:` — but the file layout does
> not. Translations are no longer 155 files named `de-<versio>.yaml` scattered
> one per psalm folder; a **Psalter** is one directory, `psalter/<versio>/`,
> holding `<psalm number>.yaml` and `magnificat.yaml`, kept outside the package
> because no German translation ships with libellus. See ADR-0024.

## Context

While implementing ADR-0007 it turned out the hand-made psalm German
(Pss 109–112 + Magnificat) is the Einheitsübersetzung **2016** — caps
„HERR“ and 2016 wording — not the 1980 text ADR-0007 chose for the full
psalter. The 1980 batch therefore cannot "reproduce the hand-made files";
both texts are legitimate (the 2016 re-cuts are what the printed Benedict
booklet used, the 1980 is the Stundenbuch psalter) and Omar wants to keep
choosing per booklet.

## Decision

A psalm's German is a set of variant files
`chant/psalmi/<n>/de-<versio>.yaml` (same for `chant/magnificat/`); the
old single `de.yaml` name is gone. Versio slugs: `eu1980`, `eu2016`, and
anything a successor invents. The existing hand-made files are renamed to
`de-eu2016.yaml` and marked as EÜ-2016-based in a header comment.

The feast spec selects with an optional top-level `psalter_de:` field.
Without it, the preference order **eu1980 → eu2016 → the single available
variant of any name** decides; several non-preferred variants without an
explicit choice are a curated German error. The Benedict smoke fixture
pins `psalter_de: eu2016` (the printed booklet's texts).

## Consequences

- ADR-0007's fidelity gate is reinterpreted: the 1980 scrape is checked
  against the hand-made files as a **documented version-difference
  report** (re-cut boundary conventions still apply), not byte fidelity.
- Whether Pss 109–112 also get `de-eu1980.yaml` re-cuts (full-psalter
  consistency) is decided in #16's review.
- The form edits `psalter_de` starting with the frontend batch (#17 ff.);
  until then the comment-preserving round-trip keeps the field intact,
  and the island's `psalmi_cum_de` means "has at least one variant".

# ADR-0015: Liturgical rank as a closed vocabulary, two systems

Date: 2026-07-25
Status: accepted

## Context

`rank:` (cover-page label, e.g. Benedict's booklet) was a free `str`,
rendered verbatim. It was wrong in practice: `vesper.tex`'s hardcoded
`Classis~I · Duplex` matches neither real system's spelling. Omar's
priest corrected it by email — the Benedict feast (11 July) was, in the
*pre-1960* vocabulary, `Duplex I classis`, not `Classis I · Duplex`; a
follow-up email supplied a fuller cross-reference table of four historical
rubric systems (pre-1960, Codex Rubricarum 1960, Calendarium Romanum
1970, Deutscher Regionalkalender), each with its own rank ladder that
only partially lines up with the others (e.g. old `Duplex II classis`
and `Duplex majus` both collapse into 1960's `II classis`; old `Duplex`,
`Semiduplex` and `Simplex` all collapse into 1960's `III classis` despite
`Simplex` alone having only one Vespers, not two).

Resolved via a grilling session (full branch-by-branch log in the
session transcript, not reproduced here):

- Both the pre-1960 and Codex Rubricarum 1960 vocabularies are modeled;
  the 1970/German-regional columns are **not** — this project only ever
  typesets from 1962-era (or earlier) books, so a feast never needs to
  *hold* a Novus Ordo-era value. That table is kept as background only
  (this ADR), not as selectable data anywhere.
- A feast picks **one vocabulary, freely** — not tied to `rite`, and not
  cross-validated against `vesperae` (I/II) even though, per the priest,
  a `Simplex` feast structurally has only one Vespers ever (unlike every
  other rank, which has both). Which other ranks share that property
  (`Feria`? the 1960 classes, which each absorb old ranks on both sides
  of the divide?) isn't yet confirmed with the priest — deliberately left
  unenforced rather than guessed.
- `Commemoratio`/monastic `Memoria` are **excluded** — structurally a
  different feature (appending a saint's antiphon+versicle+oration onto
  a *higher*-ranking day's own office, not a rank of a day's own primary
  office), tracked separately for a future ticket.

## Decision

`rank: Rank` is now a closed `Literal` of 11 values (`schema.py`), not a
free string:

- Pre-1960: `Duplex I classis`, `Duplex II classis`, `Duplex majus`,
  `Duplex`, `Duplex minus`, `Semiduplex`, `Simplex`, `Feria`
- Codex Rubricarum 1960: `I classis`, `II classis`, `III classis`,
  `IV classis`

**Update 2026-07-27 — `Duplex minus` admitted as a second spelling.** The
priest identified St. Lambert as *duplex minus* and noted that such a feast
may simply be written `Duplex`. Both are therefore accepted, and they name
the *same rung* of the ladder: the books write the fuller `Duplex minus`
where the contrast with `Duplex majus` matters, and the bare `Duplex`
otherwise. Since the value is printed verbatim, which one a feast holds is
purely a choice of cover wording, not of rank — so the vocabulary grew to 12
values while the pre-1955 ladder still has seven rungs. No logic keys off
either spelling (only `Simplex` carries behaviour) and nothing derives an
ordering from the tuple, so admitting a synonym needed no other change.
Rejected: normalising one spelling to the other on load, which would
silently override the author's printing choice; and modelling rank as
(rung, spelling), which is a lot of structure for a single alias.

*Footnote, same day:* St. Lambert turned out to be `Semiduplex`, so the feast
that prompted this no longer illustrates it. The addition stands on its own —
`Duplex minus` is a real spelling the books use, and admitting it cost
nothing — but do not read `feasts/2026-09-18-lambertus.yaml` as the worked
example.

The printed cover string is the value itself, verbatim — no per-system
formatting. `Simplex` is the one rank where the cover suppresses the
"Primæ/Secundæ in Festo" qualifier line (`cover.tex.j2`), since a Simplex
feast never has a second Vespers to distinguish from; every other rank's
cover behaves as before, pending confirmation of the other ranks'
Vespers-count from the priest. The vocabulary is exposed to the form via
the existing data-island mechanism (`rank_pre_1960`/`rank_codex_1960`,
ADR-0004) as a `<select>` with two `<optgroup>`s and no other embellishment
— the four-system cross-reference table above is deliberately *not*
surfaced in the UI as a per-option gloss, since baking an ad-hoc
correspondence into the interface would misrepresent it as authoritative.

## Consequences

- `rank: TODO`-style placeholders (used while a value is still pending
  from the priest, e.g. `feasts/2026-09-18-lambertus.yaml`) no longer
  validate — an unresolved rank now blocks the build. Accepted
  deliberately: the previous free-string field let a forgotten placeholder
  silently ship on a real cover.
- `vesper.tex`'s cover string is corrected to `Duplex I classis`
  (pre-1960, matching that booklet's monastic/old-terminology character)
  as a one-line stopgap; the file itself is unaffected otherwise and
  stays until the `monasticum` skeleton reproduces it.
- `Commemoratio`/monastic `Memoria` and the `rank`↔`vesperae` Vespers-count
  question are logged as open follow-ups, not solved here.

## Update (2026-07-25)

Two corrections from Omar's priest, both about this ADR's own work:

- **"Pre-1960" was the wrong dating.** `Semiduplex` was abolished by Pius
  XII in 1955, five years before the Codex Rubricarum reform — the four
  ranks `Duplex, Semiduplex, Simplex, Commemoratio` existed until 1960,
  but `Semiduplex` itself did not survive to see it. A ladder that still
  includes `Semiduplex` is therefore a *pre-1955* rubric, not pre-1960.
  Renamed throughout: `RANK_PRE_1960` → `RANK_PRE_1955` (`schema.py`),
  `rank_pre_1960` → `rank_pre_1955` (data island / `formdata.py` /
  `form/formular.html`), the "vor 1960" `<optgroup>` label → "vor 1955",
  and the matching `errors.py` hint. The vocabulary's *values* are
  unchanged — only the "pre-19xx" name for it.
- **`Simplex`'s one-Vespers rule now reaches the form, not just the
  cover — and the schema, not just the UI.** First cut only touched the
  form: the `#vesperae` select got `disabled` when `rank === "Simplex"`,
  after an initial attempt to unmount it entirely (same conditional-field
  pattern as `border_size`, shown only for `border == "gilded"`) turned
  out to make the form jump around when switching ranks — every field
  below it reflowed. That first cut left `schema.py`'s `vesperae:
  Literal["I", "II"]` required and unconstrained, on the assumption the
  value was merely *unused* for `Simplex`, not wrong. Omar caught the
  actual bug this exposed: `preamble.tex.j2`'s running header
  (`Ad Vesperas \VAR{feast.vesperae}`) prints the raw `I`/`II` value
  unconditionally, so a Simplex feast's header *did* show a First/Second
  qualifier the cover deliberately omits — the value wasn't inert after
  all, just inconsistently ignored.

  A grilling session (`/grill-with-docs`) settled the deeper question:
  for `Simplex`, `vesperae: I` isn't a true-but-unprinted fact, the I/II
  distinction is *inapplicable* — a Simplex feast has exactly one
  Vespers, full stop. That reframes this as a schema bug, not a template
  bug. Fix: `vesperae` is now `Literal["I", "II"] | None = None`, with a
  new `_vesperae_matches_rank` validator (mirrors the existing
  `_responsorium_matches_rite` pattern) that **rejects** the file if
  `vesperae` is set on a `Simplex` feast, and requires it for every other
  rank — matching ADR-0015's own precedent of blocking the build on an
  unresolved/contradictory field rather than silently shipping it. Both
  templates now guard on `feast.vesperae` itself (truthy only when set)
  instead of re-deriving the condition from `rank != "Simplex"` in two
  places: `cover.tex.j2` unchanged in effect, and `preamble.tex.j2`'s
  header now prints bare `Ad Vesperas` for `Simplex`, `Ad Vesperas I`/`II`
  otherwise. `form/formular.html`'s `alsFeastSpec` omits `vesperae` from
  the emitted YAML when `rank === "Simplex"` (the `#vesperae` select stays
  `disabled`+mounted as before, for the same no-layout-shift reason); its
  upload path (`ausFeastSpec`) no longer warns "`vesperae` fehlt" when
  loading a `Simplex` file that correctly omits it.
- The `rank`↔`vesperae` Vespers-count question for ranks other than
  `Simplex` (`Feria`? the Codex-1960 classes?) is still open and still
  unconfirmed with the priest — the new validator deliberately checks
  only the literal `"Simplex"` string, not derived rank properties, so
  extending it later means adding another explicit case, not guessing one
  in as a side effect of something else.

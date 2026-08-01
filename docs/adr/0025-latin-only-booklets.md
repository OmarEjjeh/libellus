# ADR-0025: Latin-only booklets — a spec field, not a command-line flag

Date: 2026-08-01
Status: accepted

## Context

ADR-0024 leaves no German psalter in the published package, because none is
redistributable. A fresh `pip install libellus` therefore cannot set a psalm
verse: the German is a hard validation error, not a graceful degrade. Worse,
`de` was a *required* field throughout the feast schema — on antiphons, the
capitulum, every hymn stanza, the responsory, versicle, Magnificat antiphon,
oration and back-cover quote — so someone with no German at all could not even
author a valid spec.

Two things were wanted: a wheel a stranger can actually use, and a booklet for a
community that sings the office in Latin alone.

## Decisions

1. **`latin_only: true` in the feast spec suppresses every translation.** All
   `de` fields go unrendered, and so does the interlinear German under the psalm
   and Magnificat verses. The booklet's own **rubrics and headings stay German**
   — „Schola", „Man steht", „Alle — beide Seiten Vers um Vers im Wechsel". They
   name the parts of the office and direct the congregation; they translate
   nothing. Provenance footnotes (ADR-0011) stay for the same reason: a footnote
   documents a source.

2. **There is no `--latin-only` flag.** Unlike a draft (ADR-0021) or a
   Kurzfassung (ADR-0022), this is not a choice made per printing — it is a
   standing property of a community. Both the full booklet and the Kurzfassung of
   one celebration are wanted the same evening, which is why `--compact` exists;
   nobody wants a Latin-only and a bilingual booklet of the same office.

   The decisive reason is narrower, though: `latin_only` relaxes the schema, and
   a command-line flag must never do that. The browser form validates a spec
   against this schema client-side (ADR-0004) and has no flags to pass, so
   requiredness that depended on how a build was invoked would make the form
   unable to validate. Validity stays a property of the file alone.

3. **`de` becomes optional in the schema, and a top-level validator enforces
   it.** A nested model cannot see the top-level flag, so the fields are declared
   optional and `FeastSpec._german_present_unless_latin_only` requires all of
   them unless the feast is Latin-only. It reports every missing translation at
   once: someone filling in a new feast should see the whole list, not one field
   per run.

4. **The suppression is a template conditional, not a LaTeX macro.** This was
   tried the other way first. A `\transblock` macro in the preamble, with the
   decision in LaTeX, reads better and puts the rule in one place — and it
   **repaginated ten of Lambert's thirty-six pages**, because wrapping that
   markup in a macro does not expand to quite the same tokens. So each partial
   guards its own German with `if not latin_only`, which emits the original
   markup byte-for-byte when the booklet is bilingual and therefore cannot move
   the type.

   Two traps met on the way, worth writing down:

   - A LaTeX `%` comment written in a *template* still reaches the `.tex`.
     Comment lines added inside the back cover's minipage were enough to shift
     pages; template comments must use `\#{ … }`, which emits nothing.
   - Jinja runs at render time, LaTeX at compile time. An `\iflatinonly` in a
     partial emits **both** branches into the `.tex`, which duplicated a
     footnote. Structural choices belong to the template; only a macro body can
     use a LaTeX conditional.

## Considered / rejected

- **Suppressing only the psalm and Magnificat verse German** — the one part that
  cannot ship — leaving the capitulum, hymn and oration bilingual: rejected as a
  half-bilingual artifact nobody asked for.
- **Fully Latin, rubrics included:** rejected. That is ADR-0012's multi-locale
  work (a 2026 priority) arriving through the back door; every hardcoded German
  string in the partials would need a locale mechanism, and it should be done
  deliberately rather than as a side effect of this flag.
- **A pure render mode, with `de` still required:** rejected. A Latin-only
  author would have to type a German translation for every antiphon, stanza and
  oration in order to print a booklet that shows none of it.
- **Making missing German a warning rather than an error:** rejected. It would
  silently produce a booklet with holes in it, and it changes the interlinear
  layout for a case Bremen will never hit.

## Consequences

- A `pip install libellus` can set a complete booklet with no Psalter: verified
  at 32 pages, and 24 as a Kurzfassung, from a directory holding only a feast
  spec and one picture.
- This is what CI's release gate builds, since no Psalter is available there
  (ADR-0023).
- The German error for a missing translation now names `latin_only` as the way
  out, so the absence of a Psalter is self-explaining rather than a dead end.
- `_tex_escape` renders `None` as nothing: with `de` optional everywhere, a
  missing translation is a value rather than a mistake. A misspelled field name
  is still caught, by `StrictUndefined`.
- Bilingual output is unchanged — verified pixel-identical across all three
  reference booklets.

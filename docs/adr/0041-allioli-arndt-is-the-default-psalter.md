# ADR-0041: Allioli-Arndt is the default German psalter

Date: 2026-08-04
Status: accepted

## Context

ADR-0007 made the Einheitsübersetzung 1980 the German psalter; ADR-0008 made the
choice per-feast via `psalter_de:`, defaulting through
`PSALTER_DE_PREFERENCE = ("eu1980", "eu2016")`.

Both of those translations are © Katholische Bibelanstalt and not
redistributable. They are supplied separately and never shipped (ADR-0024), so
the documented default named something a fresh install cannot legally have: a
clone with no private Psalter checkout resolved *no* German at all and failed.
The default was Bremen's default, not the project's.

Issue #1 exists to fix that, and the work is done: Allioli's translation in
Arndt's 1914 revision, all 150 psalms plus the Magnificat, realigned from
k-bibel.de's edition onto the sung Vulgate verse boundaries by
`psalter/tools/scrape_allioli_arndt.py`. The 1914 text is long out of copyright.

Two things about it are still open, and this decision closes neither: the priest
has not reviewed the translation, and the copyright status of that particular
*digitization* — as distinct from Allioli's text — has not been judged.

## Decision

`PSALTER_DE_PREFERENCE = ("allioli-arndt", "eu1980", "eu2016")`. The public-domain
psalter is what a feast gets when it does not ask for something else.

**Shipped booklets name their translation instead of inheriting it.** The Benedict
booklet already pinned `psalter_de: eu2016` (ADR-0008); St. Lambert now names
`psalter_de: [eu1980, eu2016]`. That is the load-bearing half of this decision.
Lambert is sung on 18 September 2026 and its German is under review by the
priest; letting it inherit a new default would have retranslated every psalm
verse in it as a side effect of a constant in `resolve.py`. Changing what a
congregation sings has to be an edit to that booklet, visible in its own diff.

**`psalter_de` therefore accepts an ordered list, not just one name.** This was
forced by a fact nobody had had to write down before: **Bremen's eu1980 has all
150 psalms and no Magnificat.** Resolution is per item, so the unpinned Lambert
booklet had always been quietly mixing — psalms from eu1980, Magnificat from
eu2016, because the preference walk fell past eu1980 for that one file. Naming a
single translation could not reproduce that, and `psalter_de: eu1980` alone made
the booklet fail to build.

Two ways out were tried. The first — let a named translation fall back through
`PSALTER_DE_PREFERENCE` for what it lacks — is wrong, and the build proved it:
with Allioli now first in that tuple, Lambert's Magnificat silently moved from
eu2016 to Allioli, changing three pages of a booklet this ADR exists to keep
unchanged. A named translation falling through to the global default means
editing the default retranslates part of a booklet that had already chosen,
which is the exact accident being avoided. So the list is explicit instead: a
feast that names translations gets **those, in that order, and no others**, and
is told plainly when none of them has a file.

**Ship it before the review, not after.** The alternative — hold the default back
until the priest signs off and the copyright question is judged — was rejected:
it keeps the project in the state where its documented default is unusable by
anyone but its maintainer, and that state is what issue #1 is about. The
translation being unreviewed is recorded rather than hidden: in `CREDITS.md`, in
the scraper's docstring, and in the header of all 151 psalm files, which say in
German that the psalter is the default *and* not yet signed off. Errors found
meanwhile are fixed as their own corrections — one already was, below.

## Consequences

Neither existing booklet changes a byte: both name their translation, verified by
rebuilding both and diffing the PDFs. What changes is a new feast written by
someone who does not say `psalter_de:` — they now get a psalter they are allowed
to have, which is the point.

The copyright judgement on the digitization is now a **live** exposure rather
than a theoretical one, because the psalter is the default and is credited. The
1914 text is safe; a faithful transcription of a public-domain text attracts no
new copyright in Germany, which is the reading this proceeds on — but it is a
reading, not a cleared right, and issue #1 keeps it open. If it goes the wrong
way the fix is small and local: drop `allioli-arndt` from the tuple and the
default falls back to what it was.

The psalter files were found to be **stale against their own generator** while
doing this: re-running `scrape_allioli_arndt.py` from its cache reproduces only
12 of 151 files byte-for-byte, so the committed YAML was written by an earlier
version of the aligner. Deliberately not resolved here — regenerating would
rewrite 139 files of a translation that is pending review, which is a change
that wants its own issue and its own review pass, not a side effect of setting a
default. Only Psalm 118 was regenerated, for the fix below.

### The Psalm 118 fix that came with it

Psalm 118 is the alphabetic psalm: 22 stanzas of 8 verses, each headed by a
Hebrew letter. k-bibel marks those headings as their own element
(`<p class="HebrewAlphabetWord">`) but nests each one *at the end of the verse
before the stanza it heads* — "Beth." closes verse 8 and heads verse 9 — and puts
Aleph in an unnumbered verse beside "Alleluja". The scraper stripped tags
without looking, so every letter was glued to the last verse of the previous
stanza and Aleph was dropped entirely, its verse having no number to key on.

`parse_chapter` now lifts the heading out of the verse body and carries it to the
next German verse, which restores Aleph as a side effect of the same rule. The
Latin copy is dropped rather than carried: the sung text comes from the
Clementine, which prints no letters, and k-bibel's Latin exists only to align
against it, so keeping "BETH." would put a word on one side of that comparison
and not the other.

Verified against the cached source: all 22 letters head their own stanza, none
trails a verse, and with the letters ignored the verse text is unchanged — so
no verse boundary moved.

# ADR-0038: A front-matter provenance rubric, not per-item negations

Date: 2026-08-04
Status: accepted

## Context

ADR-0011 gave every proper an optional `note:`, rendered as a footnote where
the item appears. For the Lambertus booklet four of those notes ended up
saying what their proper was *not*:

- p. 20, capitulum — "… nicht die Capitulum-Lesung aus dem Commune."
- p. 23, versiculus — "… nicht die Fassung des Liber Usualis."
- p. 24, Magnificat antiphon — "… nicht die Antiphon aus dem Commune."
- p. 30, oratio — "… nicht die Oration aus dem Commune."

The reviewing priest called these placeholders and asked for them to go. A
negation only informs a reader who already knows what the Commune has, and
four of them tell the same reader the same thing four times without ever
stating the default they are departing from. What the booklet never said out
loud was the positive fact: the antiphons, hymn and versicles are the Commune
of several martyrs, out of two named books, unless a note says otherwise.

`source:` on the cover ("Cantus ex …") cannot carry it. It is one line of the
cover's smallest type, it names the chant edition rather than the liturgical
Common, and it has no German — while the rubric has to be bilingual, like every
other text the congregation reads.

## Decision

A new optional top-level field, `praenotanda:` — the liturgical books' own name
for front matter — holding `text:` (Latin) and `de:` (German, required unless
the feast is `latin_only`, per ADR-0025):

```yaml
praenotanda:
  text: >-
    Antiphonae, Hymnus et Versiculi de Communi plurimorum martyrum secundum
    Antiphonale Romanum (Romae 1912) et Librum Usualem (Solesmis 1961), nisi
    aliter notetur.
  de: >-
    Die Antiphonen, der Hymnus und die Versikel sind aus dem Commune mehrerer
    Märtyrer gemäß dem Antiphonale Romanum (1912) und dem Liber Usualis
    (Solesmes 1961), wenn es nicht anders vermerkt ist.
```

It prints under the Ordo table, centred, Latin in italic `\footnotesize` and
German in `\scriptsize` beneath it. The Ordo page was chosen over a page of its
own and over the "Zum Gebrauch dieses Heftes" page:

- a page of its own shifts every page number after it, and the priest's
  annotations — like any future review — cite pages. It also costs a sheet:
  `pdfjam --booklet` pads to a multiple of four, so 36 pages become 40, not 37;
- the "Zum Gebrauch" page explains *how to sing*, which is a different subject
  from *what book this comes from* — and, measured, it has under 30pt of free
  height, less than the Ordo page;
- the Ordo lists exactly the pieces the rubric speaks about, so the rubric
  reads as a footer to that list.

Fitting it there took two changes to `ordo-table.tex.j2`, both recorded in the
template's own comments because both are traps:

- the page's vertical centring moved from `\null\vfill … \vfill\null` to
  `\vspace*{\fill}` at both ends. The two `\null` boxes each occupy a
  `\baselineskip` that must fit on the page, costing about 55pt — enough that
  the rubric no longer fitted. TeX's failure is silent and expensive: it ships
  the leading `\null` as a blank page, the block as the next, the trailing
  `\null` as a third, turning one page into three. This is the same trap
  `filler.tex.j2` already records ("No trailing `\null` on a filler page: on a
  page filled to the brim it spills onto the next one"), met a second time and
  fixed the same way; the padding-ornament loop at the end of that partial
  keeps `\null\vfill` because its pages hold one ornament and cannot fill up.
  Looking for it deliberately then turned up a third, older instance:
  `instructions.tex.j2` had been failing this way in every **Kurzfassung**
  since ADR-0022, because `compact` adds a paragraph to that page and pushed it
  over. The heading printed alone at the foot of one page, the body on the
  next, and every folio after it moved by one — never noticed, because the ÷4
  ornament loop absorbed the extra page and the total stayed at 28. It now
  centres in a `\vbox` too;
- the rubric is set as ordinary centred paragraphs, not in a `minipage`. A box
  is one unbreakable item the page builder cannot fit beside the table, and
  produces the same three-page split.

Measured headroom after both: the page holds the table and roughly 20pt more
than this rubric. That is real but thin, and nothing enforces it.

With the default stated once, every `note:` goes back to being positive: the
capitulum note names the Liège Missae propriae, the versiculus note the
Antiphonale Monasticum 1934, the Magnificat antiphon the Vesperale Romanum of
1835, the oratio the Osnabrück Collectarium. `nisi aliter notetur` in the
rubric is what ties them together — a footnote *is* the "otherwise noted".

The field is optional. A feast whose propers all come from one book, already
named on the cover, has nothing to state twice.

## Consequences

The four negations are deleted. A reader who wants to know where a Commune
piece comes from now finds it in one place instead of inferring it from four
denials, and a proper that departs from the Commune says so positively.

`praenotanda` is prose the author writes, not something derived from `source:`
or from the notes — nothing checks that the rubric and the notes agree. That is
deliberate: the wording is the reviewing priest's, in his Latin, and a
generated approximation of it would be worse than no rubric. It does mean the
rubric can go stale if a proper's source changes and the rubric is not reread.

The 20pt of headroom is the real cost, and it is unguarded. A longer rubric —
or a feast with a Responsorium breve, which adds a row to the table — will
overflow, and will do it by quietly growing the booklet instead of raising an
error: `compile` reports LaTeX's exit status, not its `Underfull \vbox`
warnings. Whoever edits `praenotanda:` has to check the resulting page count.
Making that a real check (assert the booklet's page count, or fail on a front
matter overflow) is left for the issue that next needs it.

Only the Lambertus feast sets it so far. The Benedictus booklet's propers are
all from the Antiphonale Monasticum named on its cover, so it stays absent —
which is the case the field being optional is for.

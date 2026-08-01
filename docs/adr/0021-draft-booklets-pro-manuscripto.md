# A draft booklet is marked PRO MANUSCRIPTO on every page

Date: 2026-07-30
Status: accepted

A booklet has to be readable by other people before it is final — the priest
checks the propers, a singer checks the German. Sending them a PDF that looks
exactly like the finished article invites the obvious accident: somebody prints
thirty copies of unreviewed text. `libellus build --draft`, or `draft: true` in
the feast spec, marks every page instead.

Both switches exist because they serve different people. The field is what the
form can set and what travels inside a `Bündel` (ADR-0019), so a spec handed to
someone else stays a draft in their hands too. The flag is for sending a quick
draft of a spec you do not want to edit.

**Either switch alone marks the booklet, and neither can clear the other.** The
alternative — a `--no-draft` that overrides the field — was rejected: it hands
you a clean, printable PDF of material its own author marked unreviewed, which
is the exact outcome the feature exists to prevent. Turning a draft into a final
booklet therefore means removing the field, a deliberate act performed in the
place where you can see it. That place is the form (the checkbox sits in „Das
Fest" with the title and rank, not among the rendering options at the bottom):
the command line can only ever switch a draft *on*.

Design decisions worth recording:

- **`PRO MANUSCRIPTO`, in Latin, with a German dated line beneath it.** The
  Latin is the standing ecclesiastical formula for a provisional or privately
  circulated printing, and it is the register the cover already speaks in — it
  prints „Ad usum amicorum". But the formula makes a claim about *publication
  status*, not about *provisionality*: strictly, every booklet here is already
  pro manuscripto. So the page also carries „Entwurf vom 30. Juli 2026, 14:32
  Uhr", which is the part a reader with no Latin can act on. Latin primary,
  German gloss beneath, exactly as every chant in the book is set. Rejected:
  `MINUTA` (too obscure to function as a warning), `EXEMPLAR` (means "copy",
  actively misleading), an English `DRAFT` (a foreign object in a Latin and
  German book).
- **Both marks are drawn in the `shipout/background` layer**, the diagonal by
  `draftwatermark`, the dated line by `eso-pic`'s `\AddToShipoutPictureBG`.
  Background material is painted at absolute page coordinates and contributes
  nothing to the galley, so it cannot reflow a line — and, decisively, cannot
  shift the page count off the multiple of four the imposition needs. It is also
  the only way to reach *every* page: a `fancyhdr` footer would silently vanish
  on the cover (`\thispagestyle{empty}`) and the filler pages
  (`\pagestyle{plain}`), which are the first pages anyone flips to. The dated
  line sits inside `geometry`'s 20 mm bottom margin, structurally below the text
  block and therefore below every provenance footnote (ADR-0011).
- **A draft still produces all three PDFs, imposed booklet included.** Not
  shipping the print-ready files would discourage printing more effectively, but
  reviewers — priests especially — mark up paper with a pen. So the watermark
  carries the whole burden, which is why it is large and on every page rather
  than a discreet footer note.
- **The timestamp is the build clock, formatted in Python and baked into the
  `.tex`.** Not TeX's `\today`, because the draft's identity is when it was
  *created*: re-running `make` in a staged folder months later must not restamp
  it, and must not contradict the folder's own name. The date is spelled out
  („30. Juli") rather than numeric, since the only other date in the book is set
  in Latin roman numerals and `30.07.` reads like machine output there.
- **A draft build gets its own stem**,
  `<feast>-entwurf-<yyyy-mm-dd-hhmm>`, hence its own staged folder and its own
  PDF names. `stage()` wipes its target folder, so without this a draft build
  would delete the final build; and successive drafts would arrive in a
  reviewer's inbox under one filename, indistinguishable without opening them.
  The cost is that `build/` accumulates folders, each with a copy of the feast's
  assets (~3 MB for Lambert), pruned by hand.

Consequence: draft PDFs are not reproducible — two builds of an unchanged spec
differ in the stamp. Final booklets are unaffected, and the spec field is off by
default, so `draft: false` is never written to a file; the absence of the key
*is* "not a draft", following `drollery: auto` (ADR-0018's precedent).

Known limit: on the back cover the picture covers the background layer, so the
diagonal is hidden behind it and only its ends show. The dated line still reads,
and that page carries no liturgical text to mistake for final.

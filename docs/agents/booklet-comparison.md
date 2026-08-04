# Booklet Comparison

How to show someone what changed between two versions of a booklet — normally the
reviewing priest, after his annotations have been worked in.

Compare the **rendered PDFs**, never the LaTeX. `latexdiff` is the obvious tool
and the wrong one here: half of what a booklet says is notation, the notation
lives in `.gabc` files that the `.tex` only references by path, and so a
correction to a neume, an accent, an annotation or a divisio is invisible to it.
It also mangles the Ordo page — `\vbox to \textheight` gets its dimension
wrapped in `\DIFadd{}` and the document stops compiling. `diff-pdf` compares
pixels and therefore sees everything that will actually be printed.

## Produce three files

Build the current booklet, and build the previous version in a throwaway
detached worktree — `git worktree add --detach <scratch>/booklet-old <ref>`,
symlinking `psalter` and `toolchain` back to the main checkout so it can
resolve and compile. Not `scripts/worktree-add.sh`: that is for a line of work
and insists on a `<type>/<issue>-<slug>` branch. Remove the worktree afterwards.

```sh
diff-pdf --verbose old.pdf new.pdf                    # which pages differ
diff-pdf --grayscale --output-diff=…-aenderungen.pdf old.pdf new.pdf
diff-pdf --grayscale --skip-identical \
         --output-diff=…-aenderungen-nur-seiten.pdf old.pdf new.pdf
```

`--grayscale` leaves unchanged material grey so only the changes carry colour.
`--skip-identical` keeps just the pages that moved. `diff-pdf` exits **1** when
the documents differ — that is its answer, not a failure.

Then the one that actually gets sent: a **side-by-side sheet**. Rasterise each
differing page from both PDFs (`pdftoppm -r 160 -png -singlefile`) and set them
two-up on A4 landscape, `vorher` left and `nachher` right, each page carrying
its folio number and one German line naming what changed.

## Why all three

The overlay finds *where* something changed and is poor at showing *what*:
wherever text reflowed — a wider annotation shifting a staff, a footnote
growing a line — both versions superimpose into unreadable colour. The
side-by-side is what a reviewer reads; the overlay is the locator that proves
nothing else moved. Send the side-by-side, keep the overlays as evidence.

## Get the page numbers right

A reviewer cites pages, so **pagination is part of the deliverable**. Check that
the page count is unchanged and that `diff-pdf` reports only the pages you meant
to touch; anything else means something reflowed and his page references have
gone stale. If the count does have to change, say so on the comparison sheet.

Two things routinely mislead here. `pdfjam --booklet` pads to a multiple of
four, so one extra page can cost four. And the ÷4 ornament-padding loop in
`filler.tex.j2` silently absorbs a page you accidentally added — the total stays
put while everything inside shifts, which is exactly the failure the per-page
`diff-pdf` report catches and a page count alone does not.

## Say what the comparison cannot show

The sheet's cover note should name what is *not* in it, or the reviewer will
assume his point was dropped:

- corrections already applied in an earlier round, which no longer diff;
- anything still open and awaiting his word.

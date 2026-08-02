# ADR-0032: A build stops when the layout stops moving, and reproducibility is proven by rebuilding

Date: 2026-08-02
Status: accepted

## Context

`build/2026-09-18-lambertus/2026-09-18-lambertus.pdf` — the booklet due to be
sung on 18 September 2026 — could not be rebuilt from the staged folder sitting
beside it. Ten pages differed every time (#56), by a small vertical shift of one
or two chant systems. It surfaced while establishing a native control for the
WebAssembly spike, and had nothing to do with WebAssembly.

The natural reading was that the shipped PDF was the reference and the rebuild
the deviation, and the natural suspect was GregorioTeX's `.gaux` position cache
settling into a different fixed point. Three builds, varying only the cache and
holding the recipe fixed, refuted that:

| build, from cold | result |
|---|---|
| no `.gaux` | PDF **A** |
| `.gaux` from A | pixel-identical to A |
| the **shipped** `.gaux` | pixel-identical to A, and converged in one pass |

All three differed from the shipped PDF on the same ten pages. The shipped
`.gaux` is, loaded and compared as a Lua table, *identical* to the one a cold
rebuild produces — 78/78/29/78 keys, nothing differing.

The logs gave the answer. The shipped PDF's final pass ends with

```
Module gregoriotex Warning: Line heights, variable brace lengths, or soft flats/
sharps may have changed. Rerun to fix. on input line 0
```

The recipe's loop reran only while the log had `!` error lines, so it never saw
this. The shipped PDF is the output of a pass GregorioTeX had explicitly asked
to repeat: laid out from the *previous* pass's cache, while writing the
corrected cache next to itself. Hence an artefact that disagrees with its own
sources, and a rebuild that lands somewhere else — the right somewhere else.

A third disagreement turned up while re-shipping, with a different cause and the
same shape: the staged folder's `.tex` was a spec revision behind `feasts/`,
because the back-cover source note had been reworded after the folder was
staged. A staged folder is a snapshot, and nothing was checking that the
snapshot still matched. Re-staging fixes this instance; noticing that "the
artefact disagrees with its sources" has more than one cause is the durable part.

Two further things came out of the same investigation. A genuinely cold build
had never been possible: `gregorio` exits non-zero on
`chant/hymni/sanctorum-meritis.gabc` (#55, a forced centre inside an elision)
while none the less writing complete notation, and GregorioTeX's autocompile
turns that exit code into a LaTeX error. Every "cold" build to date, including
the ones that found this bug, kept `tmp-gre/` and so never ran gregorio at all.
And the loop being wrong mattered more than it looked: with the notation
pre-made there are no LaTeX errors at all, so an error-watching loop stops after
the first pass every time.

## Decisions

1. **The stopping condition is convergence, not the absence of errors.** The
   loop reruns while the log contains `Rerun to fix` (GregorioTeX: line heights,
   brace lengths, soft accidentals) or `Rerun to get cross-references right`
   (LaTeX: labels, page references), and stops when neither appears. A pass that
   asks for nothing has by definition laid out what it computed, so there is no
   separate settling pass any more — the old unconditional final pass is gone.
   An error is now fatal on the pass that reports it rather than retried eight
   times, because the only reason for those retries was autocompile, and
   decision 3 removes autocompile.

2. **The shipped Lambertus PDF is superseded, not reproduced.** It is a
   defective artefact, not a reference: ten of its pages carry stale line
   heights. Bending the pipeline to reproduce it would be reproducing the bug.
   It is rebuilt and re-shipped, and the rebuilt booklet is the reference from
   here. Checked page by page first — the differences are layout settling only,
   with no change to any note, neume or word.

3. **gregorio runs before TeX in the native pipeline too, and
   `--shell-escape` goes.** ADR-0026 decision 3 scoped this to the all-in-one
   application; it applies just as well to what exists today, and it is a
   precondition for decision 1 being tested honestly. The staged `Makefile`
   gains a `tmp-gre/%-<version>.gtex: %.gabc` rule invoking exactly what
   GregorioTeX would have invoked, `gregorio -D -W -o … -l … …`, with the
   version suffix read from the installed gregorio so the staged folder stays
   correct on whatever toolchain it later meets. Verified: 77/77 `.gtex`
   byte-identical to what autocompile produced, and the booklet then builds
   from true cold in two passes.

4. **gregorio's exit code is not the gate; produced notation is.** It exits
   non-zero for scores it none the less sets usably, and one of them is in the
   booklet that shipped. The build fails only when no notation came out, and the
   `.glog` is echoed on every run either way — so #55 is now visible on each
   build instead of being swallowed by a `tmp-gre/` that happened to be warm.

5. **Reproducibility is checked by building twice from cold, never against a
   stored reference PDF.** `scripts/rebuild-check.py` copies a staged folder
   twice, runs `make clean` in each so the notation goes too, builds both, and
   compares them page by page with `scripts/pdfdiff.py`. What is worth defending
   is that the folder *converges*; a stored reference would only ever prove that
   today's toolchain agrees with the day the reference was recorded.

## Alternatives considered

- **Delete `.gaux` before the first pass**, as #56 originally proposed. It would
  not have helped: the cache was never stale, and starting from an empty one
  reaches the same fixed point. It would also have thrown away the one thing
  that makes the second pass cheap.
- **Treat the shipped PDF as the contract and reproduce it.** Rejected once the
  logs showed it was emitted mid-convergence. There is no principled way to
  reproduce "one iteration short" other than to stop one iteration short.
- **Keep autocompile and only fix the loop.** Sufficient for the bug, and it
  would have left `--shell-escape`, a subprocess per score inside the TeX pass,
  and a cold build that fails on #55. The two changes are cheaper together than
  separately, and each verified the other: the recipe change is trustworthy
  precisely because the diagnosis was completed against the unchanged recipe
  first.
- **Fail the build on gregorio's exit code.** Correct in principle, and it would
  block a booklet that is due to be sung over notation that has shipped and is
  legible. The error is surfaced instead, and fixing the score stays #55.
- **Compare each build against a committed reference PDF.** Rejected per
  decision 5; it converts every legitimate toolchain update into a failure while
  proving nothing about convergence.

## Consequences

- The staged folder now needs `gregorio` on `PATH` as an explicit build tool
  rather than as something LuaTeX happens to spawn. It was always required; it
  is now honest about it. `--shell-escape` is no longer needed anywhere, which
  removes arbitrary code execution from the compile step.
- Builds are slower from true cold — all 77 scores are set before TeX starts —
  and faster in every other case, because two passes replace up to five.
- `make clean` in a staged folder now discards the notation too, so a "clean"
  rebuild really is one. `rebuild-check.py` depends on that.
- #55 will now announce itself on every single build until the score is fixed.
  That is intended, and it is the reason the message names the file.
- The claim in CONTEXT.md that a staged folder "compiles to the booklet without
  libellus or the rest of the repo" is testable for the first time, and tested.

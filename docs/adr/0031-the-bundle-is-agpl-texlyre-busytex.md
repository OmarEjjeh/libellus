# ADR-0031: The distributed application is AGPL-3.0-or-later, built on TeXlyre-BusyTeX

Date: 2026-08-02
Status: accepted
Supersedes: ADR-0029 decision 2. ADR-0029's decisions 1 and 3 stand.

## Context

ADR-0029 decision 2 chose the copyleft ceiling before anything had been built.
It preferred upstream `busytex` (MIT scripts) over TeXlyre-BusyTeX
(**AGPL-3.0-or-later**), and it named a specific reason that had nothing to do
with this project's own convenience:

> §13 attaches obligations to *anyone who hosts the browser build*, including a
> parish that puts it on their own web space, and this project's whole ethos is
> not handing successors obligations they cannot evaluate.

It also recorded, honestly, that the preference was not free: TeXlyre is the
maintained fork and the one that actually ships TeX Live 2026 with LuaTeX, while
upstream busytex is "the older, quieter base."

Spike #43 then built the thing. Part 2 compiled both Lambertus booklets under
TeXlyre-BusyTeX's LuaHBTeX, pixel-identical to native on every page, against a
46 MB custom texmf tree. It did that deliberately on TeXlyre — feasibility
first — and **never compared upstream busytex at all**.

One finding sharpens the choice. TeXlyre advertises lualatex, and its pipeline
names a `lualatex.fmt` path, but **no LaTeX format ships in any of its three
data packages** — only `pdflatex.fmt`, `xelatex.fmt` and `tex.fmt`. The format
has to be built inside the WebAssembly, once, from `lualatex.ini`. It takes 1.1
seconds and produces 5.39 MB.

That matters for the alternative: the premise under which ADR-0029 preferred
upstream was that TeXlyre's advantage is a *ready-made* TL2026-with-LuaTeX
build. It is not ready-made. What TeXlyre supplies is a LuaHBTeX binary that
works and a tree the format can be built from — and upstream busytex, being
older and quieter, is unlikely to supply even that.

## Decisions

1. **Build on TeXlyre-BusyTeX. The distributed application is
   AGPL-3.0-or-later.** ADR-0029 decision 2 is reversed.

2. **This is a decision by fiat, not the outcome of a comparison.** Recorded
   plainly because the distinction will matter to whoever reads this next: the
   maintainer judged the licence ceiling not worth further effort, and upstream
   busytex was **never benchmarked**. ADR-0029's argument was not refuted. It
   was set aside.

   Anyone reopening this has a well-specified experiment rather than an open
   question: can upstream `busytex` produce a LuaHBTeX binary against which
   `luahbtex -ini … lualatex.ini` succeeds? Everything downstream of that —
   the 46 MB tree, the fonts, the `\GreWriteTranslation` patch, the two-pass
   convergence — is already known to work and is engine-independent.

3. **The §13 consequence is accepted, not dissolved.** It is unchanged from
   ADR-0029's description, and it is the one cost that falls on people other
   than this project:

   > AGPL §13 requires that anyone who *modifies* the software and lets users
   > interact with it over a network offer those users the Corresponding Source.

   One correction to how ADR-0029 framed it, which makes the cost slightly
   larger rather than smaller. §13 is not the only clause in play: a browser
   build **sends the compiled WebAssembly to every visitor**, which is
   plausibly *conveying* object code under §6 rather than merely providing
   remote access — in which case the source obligation attaches whether or not
   the host modified anything. Whether serving code to a browser counts as
   conveying is contested and this project does not need it resolved.

   For this project the cost is nil either way: the repository is public, so
   the offer is honoured by existing. For a third party the honest summary is
   that a host must be able to point at the source of the build they serve.
   That is a link for an unmodified copy and a published fork for a modified
   one — achievable for a parish, but not *nothing*. ADR-0029 was right that
   this is a real cost falling on people other than us. This ADR accepts it.

4. **`CREDITS.md` gains the bundle section ADR-0029 decision 3 called for**,
   written for AGPL rather than GPLv3. That section had never been written;
   this ADR is what finally forces it, because the ceiling is now settled.

5. **The 0BSD grant on the sources is untouched.** ADR-0029 decision 1 stands
   verbatim: 0BSD covers what is ours to license, and one-way compatibility
   means the bundle's stronger copyleft changes nothing for anyone lifting a
   module out of the source tree. AGPL rather than GPLv3 as the bundle licence
   does not alter that reasoning; it only raises the ceiling.

## Consequences

- The application's `LICENSE` for the *distributed artifact* is
  AGPL-3.0-or-later. The repository's `LICENSE` stays 0BSD. Two licences,
  two scopes, as ADR-0029 decision 1 set up.
- `CREDITS.md` must say AGPL wherever it describes the bundle.
- The published Python wheel is unaffected while it merely invokes an
  externally installed toolchain. Only bundling triggers this.
- If the hosting obligation later proves to bite someone in practice, the
  experiment in decision 2 is the way back, and it is cheap.

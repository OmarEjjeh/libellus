# ADR-0036: The CLI's retirement is a target, gated on #49, not a decision to execute today

Date: 2026-08-03
Status: accepted
Scopes: ADR-0026 decision 1; CONTEXT.md's definition of **Libellus**.

## Context

CONTEXT.md defines Libellus as "one product in three shapes: the
application (browser and Electron), the command line, and the `core`
library both are built on." The command line is not a legacy shape sitting
alongside a finished application — it is the *only* shipped product today.
v0.1.0 is on PyPI, `release.yml`'s `booklet-from-the-wheel` job uses
`libellus build` as the release gate for that wheel, and Bremen's actual
production workflow is written entirely in CLI terms: the README's "Bremen
operations" section says to build "without `--draft`" and to print the
`-montage-duplex` PDF (renamed from `-pdfjam-duplex`, see CONTEXT.md) on a
duplex printer. St. Lambert is sung on 18 September 2026 off exactly that
workflow, and Electron does not exist yet.

Retiring the CLI outright, now, would leave Bremen's real production with
no working replacement. But keeping it as a permanent third shape
indefinitely contradicts the reach and simplicity motives behind ADR-0026
in the first place — "one web codebase everywhere," not one web codebase
plus a command line kept alive forever out of caution.

## Decision

The CLI's retirement is recorded as a target end-state, not executed by
this ADR. It is gated on **#49** — "the least technical schola member
produces one booklet unassisted" — passing against the app, not merely on
the app's features (imposition, Electron) existing. A features-only gate
("imposition ships, Electron ships") would confirm the app *can* do what
the CLI does; #49 confirms someone who is not the maintainer actually can,
which is the real bar the reach motive sets. Until #49 passes, the CLI
remains fully supported and unchanged, and `release.yml`'s wheel-installed
smoke test keeps using it as the release gate.

This does not retire the Python package itself. ADR-0027 already has
Pyodide's `micropip.install("libellus")` pulling the same wheel to run the
pipeline in-browser — the wheel keeps existing as an internal build
artifact regardless of what happens to its command-line entry point.

## Consequences

- CONTEXT.md's three-shapes definition of Libellus stays accurate until
  #49 passes; this ADR does not rewrite it pre-emptively. The definition
  should be revisited when retirement actually executes, not now.
- ADR-0026 decision 1 ("the same code runs in a browser, in Electron, and
  in the CLI") is unchanged in the interim — the CLI keeps needing the same
  pipeline parity every other host gets, including the imposition seam
  (Montage) landing behind the same `Runner`-style injectable hook rather
  than a CLI-only shortcut.
- What replaces `booklet-from-the-wheel` as the release gate once the CLI
  retires is left open — plausibly a browser-build check in the spirit of
  `tests/test_browser_build.py` — and is not designed by this ADR.

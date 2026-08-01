# ADR-0024: Assets ship inside the package; a Psalter is a directory beside it

Date: 2026-08-01
Status: accepted
Supersedes: ADR-0008's `de-<versio>.yaml` file convention

## Context

Everything the generator needs lived outside the Python package: `template/`,
`chant/`, `images/borders/` and the psalm-tone engine at
`scripts/psalm-library/`. Every path resolved against `Path.cwd()` — 44 sites of
`root / <asset>` — so libellus only ever worked from the repository root. A
wheel contained 20 Python files and nothing else, and `pip install libellus`
produced a command that could not set a single note.

The obvious fix — move the assets into `src/libellus/` — collides with two
things.

**The staged folder's layout is a contract.** `libellus build` writes a
self-contained `build/<feast>/` holding the rendered TeX plus every asset under
its *original relative path*, because the TeX references them that way
(`\gregorioscore{chant/…}`). Those paths cannot change.

**Not all of it can be bundled.** The German psalm translations are the
Einheitsübersetzung: not redistributable (ADR-0007), and no public-domain German
psalter exists yet. Meanwhile per-feast photographs are the user's content, not
the tool's, and three directories are build-time caches that must be written
even when the package sits in a read-only `site-packages`.

## Decisions

1. **Asset paths become logical; only their provider changes.** A path like
   `chant/ant/laetare.gabc` still names what the TeX reads and what a staged
   folder reproduces. What changed is where it is *read from*, and
   `libellus/paths.py` owns that single mapping:

   - **Bundled** — `chant/`, `template/`, `psalm-library/`, `images/borders/`,
     `images/drollery/` come from inside the installed package. These are the
     tool.
   - **Generated** — anything with an `inline` or `toni` component is build-time
     output, written under `build/.cache/` in the working directory while
     keeping its logical name, so the staged folder and the TeX are unchanged.
     Never written into the package.
   - **Content** — everything else, from the working directory: `feasts/`,
     per-feast pictures, and the Psalter.

   Deliberately a *mapping by prefix*, not a fallback chain: a given logical
   path has exactly one provider, so behaviour cannot depend on which files
   happen to exist.

2. **The psalm-tone engine ships in the package.** It is not a development
   script: `psalmtone.py` shells out to it on every build of every feast, so an
   installed wheel without it could not set a single psalm. It moves to
   `src/libellus/psalm-library/`. Its `root` parameters go with the move, having
   become meaningless.

   This makes **Node.js (or Bun) a hard runtime prerequisite**, which the README
   had never stated.

3. **A Psalter is a first-class directory: `psalter/<versio>/`,** holding
   `<psalm number>.yaml` and `magnificat.yaml`. One translator's complete German
   is one directory — which is what it always was in substance, though ADR-0008
   scattered it as 155 files named `de-<versio>.yaml`, one per psalm folder. That
   convention is superseded.

   The Psalter lives *outside* the package and no translation ships with
   libellus. A fresh install has no Psalter at all; the German error names the
   path a Psalter goes in and points at `latin_only` as the way to build without
   one.

4. **The wheel is proven, not assumed.** `.gitignore`'s picture patterns are
   deliberately broad and hatchling selects files via VCS — which silently
   emptied `images/` out of the first wheel built after the move. `artifacts`
   in `pyproject.toml` forces those tracked-by-exception files back in, `exclude`
   keeps `de-eu*` and `psalter/` out, and CI asserts both by inspecting the
   built artifacts (ADR-0023).

5. **The test suite stops reading the real psalter.** A probe Psalter under
   `tests/fixtures/psalter/` supplies synthetic German with verse counts
   generated from the engine, and the suite resolves against it in every
   environment. The suite therefore gives the same answers in a contributor's
   checkout, in CI and in a fork's pull request, and no longer asserts against
   copyrighted text.

## Considered / rejected

- **A layered lookup** — try the working directory, fall back to the package:
  rejected as unnecessary machinery. With an editable install the repository
  *is* the package, so nothing needs shadowing, and a fallback chain makes
  behaviour depend on which files happen to be present.
- **Scaffolding on `libellus init`** — copy the assets into a new directory and
  keep resolving against the working directory: rejected. It freezes the
  templates: typesetting fixes like the `\GreWriteTranslation` patch would never
  reach anyone who had already run it.
- **Keeping the Einheitsübersetzung inside the package and excluding it by
  glob:** accepted first, then overtaken by ADR-0023's repository split, which
  moves the psalter out of the tree entirely — structurally safer than a glob,
  and it is what forced the psalter to become a content-directory lookup.

## Consequences

- `root` no longer means "the repository root"; it means the working directory.
  Bundled assets ignore it entirely.
- Nothing generated is stored anywhere: clearing `build/` clears every cache.
  `.gitignore` no longer needs per-cache entries.
- Verified against the pre-change output: Lambert, its Kurzfassung and the
  Benedict booklet are pixel-identical page for page, and a wheel installed into
  a clean environment reproduces Lambert byte-identically from a directory
  holding only a feast spec, one picture and a Psalter.
- Fixing the engine's location surfaced a bug it had been hiding: psalm files
  are named with three digits (`042.txt`) and the driver looked them up
  unpadded, so **every psalm below 100 was unreachable** — two thirds of the
  psalter, unnoticed because only Pss 109–116 had ever been sung from it.
- Anything reading assets must go through `paths.source_of`, tests included.
  A test that builds paths itself can pass by reading a file the real code would
  never consult — which is exactly how a stale `chant/**/toni/` directory made a
  broken build look green during this work.

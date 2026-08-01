# AGENTS.md

## GitHub account

For this repo, ALWAYS use the private GitHub account **OmarEjjeh** with the
`gh` CLI — never the `omar-ejjeh_webcom` work account. Check the active
account with `gh auth status` and switch if needed:

```
gh auth switch --user OmarEjjeh
```

## Version control

This repository uses **plain Git**. Jujutsu was used until July 2026 and has
been dropped (ADR-0023); the private `vesper` archive keeps that history.
`main` is the default branch.

Commit messages follow **Conventional Commits**, and that is load-bearing
rather than cosmetic: `commitizen` derives the version bump and the changelog
from them (`[tool.commitizen]` in `pyproject.toml`). A `feat:` bumps the
minor, a `fix:` the patch, and while `major_version_zero = true` a breaking
change bumps the minor too rather than reaching 1.0.0. Content-only changes
under `feasts/`, `images/` or `psalter/` bump the version like any other —
one repo, one version.

Releasing is deliberate and local: run `cz bump`, review the version,
`CHANGELOG.md` and tag it produced, then `git push --follow-tags`. Pushing
the tag is what triggers `release.yml` to publish to PyPI, so a release never
happens by merging alone.

## Python

Always use **uv** for anything Python — never `python`/`python3` directly and
never `pip`/`pip3 install`. Run scripts with `uv run` and pull in dependencies
inline rather than installing into a global environment:

- One-off script: `uv run script.py`
- Script with dependencies: add a PEP 723 inline metadata block at the top of
  the script and run it with `uv run` (uv resolves the deps automatically), or
  use `uv run --with <pkg> script.py`.
- Ad-hoc REPL/one-liner: `uv run --with <pkg> python -c '...'`.

Do not fall back to `pip install` or a bare `python` invocation.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (OmarEjjeh/libellus, via the
`gh` CLI with the OmarEjjeh account). See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (label string = role name). See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root is the domain glossary,
decisions live in `docs/adr/`. See `docs/agents/domain.md`.

## Handoff notes

This repo has an in-progress, multi-session task (currently: the St. Lambert
booklet, sung 18 September 2026, and the generator's survivability work).
`HANDOFF.md` at the repo root tracks what's done, what's pending, and why —
keep it up to date at the end of any work session that changes this task's
state (files fetched/moved, decisions made, blockers hit), not only once
the whole task is finished.

`HANDOFF.md` is **untracked and stays that way** (see `.gitignore`). It is
working state, not documentation: it names people, quotes correspondence, and
records half-finished reasoning, none of which belongs in a public repo. The
same goes for any `*-review.html` spotcheck or scratch note. Anything in it
worth publishing gets restated in `docs/adr/` or `CREDITS.md`, attributed by
role rather than by name.

## Stray ideas

Tangential ideas that come up mid-task but aren't part of the current work
belong in `IDEAS.md` at the repo root — one line per idea, append-only, no
structure required. Capture should cost nothing: don't stop to develop the
idea, just log it and keep going. Revisit `IDEAS.md` periodically (e.g.
during grilling/triage sessions) to promote entries into real issues or ADRs.

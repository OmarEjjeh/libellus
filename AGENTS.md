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

Branches are named `<type>/<issue-number>-<slug>`, where `<type>` is the
Conventional Commits type the work will land as — so `fix/56-cold-rebuild`,
`feat/30-psalm-by-incipit`, `docs/48-runbook`. Exploratory work that is not
meant to land as-is uses `spike/` instead, e.g.
`spike/43-browser-tex-toolchain`. The type is a promise about the branch, not
about every commit on it.

**Never work an issue from `main`.** Before the first edit, check whether the
issue's branch already exists — locally with `git branch --list '*/<n>-*'`, and
remotely with `git branch -r --list 'origin/*/<n>-*'`. Switch to it if it does;
otherwise create it from an up-to-date `main` and switch to it:

```
git switch -c <type>/<issue-number>-<slug> main
```

Do this at the start of the work, not at the end — a branch cut afterwards
means the work already happened on `main`.

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

## Session state

Work in progress lives in the **map issue** — one pinned GitHub issue labelled
`wayfinder:map`, currently **#54**, holding the status, the ordered frontier,
the open problems, and the reasoning that has not earned an ADR. Read it at the
start of a session (`gh issue view 54`) and update it at the end of any session
that changes the picture. **Prune it** rather than appending: it replaced a
3300-line handoff file that grew unreadable precisely because nothing was ever
removed from it.

Everything else has a home of its own and belongs there, not in the map:

| what | where |
|---|---|
| one piece of work | its own issue, linked to the map as a sub-issue |
| a decision, with its alternatives | `docs/adr/` — dated records, superseded rather than edited |
| a domain term | `CONTEXT.md` |
| a stray idea | `IDEAS.md` |
| how to run or operate the thing | `README.md` |
| a gotcha about one file | a comment in that file |

Nothing that names a person, quotes correspondence, or records half-finished
reasoning about people goes into any of those. That material stays **untracked**
in `private-notes.md`, `lambertus-email-threads.md`, `lambertus-hintergrund.md`
and the `*-review.html` spotcheck tools (all gitignored). Those files are source
material, not a state store — do not let one grow back into a handoff document.
Anything in them worth publishing gets restated in the map issue, `docs/adr/` or
`CREDITS.md`, attributed by role rather than by name.

## Stray ideas

Tangential ideas that come up mid-task but aren't part of the current work
belong in `IDEAS.md` at the repo root — one line per idea, append-only, no
structure required. Capture should cost nothing: don't stop to develop the
idea, just log it and keep going. Revisit `IDEAS.md` periodically (e.g.
during grilling/triage sessions) to promote entries into real issues or ADRs.

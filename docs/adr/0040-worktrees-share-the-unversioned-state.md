# ADR-0040: Parallel work happens in git worktrees, which share the unversioned state by symlink

Date: 2026-08-04
Status: accepted

## Context

Several lines of work are ready at once — #45 and #46 (the psalm-tone
resolver), #30 (psalm fields by incipit), #38 (`lyrics()` eating gabc special
characters), the succession issues #48–#51 — and switching branches in one
checkout serialises them for no reason. Git worktrees are the ordinary answer,
and the repository is unusually well prepared for them: every path resolves off
a `root` passed in rather than off the process's cwd (`resolve.py`'s
`PSALTER_DIR`, `tests/conftest.py`'s `repo_root`), and ADR-0032 made a staged
folder self-contained with its own `tmp-gre/` and `.gaux`, so two worktrees can
compile simultaneously without fighting over a cache.

The obstacle is that almost nothing which lets a checkout build a booklet is in
git. Measured in this working copy:

| gitignored state | size | how it is obtained |
|---|---|---|
| `node_modules/` | 398 MB | `npm install`; Electron work only |
| `.venv/` | 182 MB | `uv sync` |
| `toolchain/` | 93 MB | `scripts/toolchain/build.sh` — downloads busytex and Pyodide, cuts texmf from a local TeX Live, needs emsdk for `gregorio.wasm` |
| `scripts/toolchain/.cache/` | 46 MB | that script's download cache |
| `build/` | 33 MB | output |
| `psalter/` | 3.8 MB | a clone of the private `psalter-eu` (ADR-0023) |
| `private-notes.md`, `lambertus-*.md`, `lambert-corrections.md`, `*-review.html` | small | untracked source material, per AGENTS.md "Session state" |
| `.envrc`, `.claude/`, `.agents/`, `skills-lock.json` | tiny | local tooling |

A bare `git worktree add` therefore produces a directory that resolves no
German (no `psalter/`), cannot run the browser application (no `toolchain/`),
has no interpreter, and has lost the notes the feast work is being done
against. Provisioning one by hand is both tedious and easy to get half-right,
and a half-provisioned worktree fails in the project's least favourite way:
plausibly, and later.

## Decisions

1. **Worktrees live in a sibling directory, named from the branch.**
   `../libellus-worktrees/<slug>`, where `<slug>` is the branch minus its type
   prefix — `feat/30-psalm-by-incipit` becomes
   `libellus-worktrees/30-psalm-by-incipit`. The branch convention in AGENTS.md
   is unchanged and now does double duty as the directory convention.
   `$LIBELLUS_WORKTREES` overrides the parent.

2. **`scripts/worktree-add.sh` is the way one is created**, not a documented
   list of steps. It validates the branch name against the convention (the
   directory name is derived from it, so a typo would put the worktree
   somewhere surprising), creates the worktree, symlinks the shared state,
   writes the two-line `.envrc`, and runs `uv sync --all-groups`.

3. **The expensive, stable state is shared by absolute symlink; the cheap or
   branch-specific state is not.** Shared: `toolchain/`, its download cache,
   `psalter/`, the private notes, and the agent configuration. Not shared:
   `.venv/` (branch-specific dependencies, and cheap — see below), `build/`
   (output), `node_modules/`.

   - **Amended 2026-08-05 (see #83): a shared item the checkout already
     provides is shared entry by entry, not as one symlink.** `ln -s X D`
     puts the link *inside* `D` when `D` is a directory, and ADR-0041 made
     `psalter/` one — git checks the tracked public Allioli-Arndt out into it.
     The shared Psalter therefore landed as `psalter/psalter`, so every
     worktree created after that silently resolved no Einheitsübersetzung
     while looking provisioned. `link_into` now links the entries the checkout
     does not already have, and skips dotfiles — which is what keeps the
     companion repository's own `.git` from being linked into the worktree.

     This has a cost the whole-directory symlink did not: the shared
     translations are now symlinked *directories*, and a walk that does not
     follow symlinks steps straight over them. Both hosts had to be taught to
     follow one (`app/serve.py`'s `content_files`, `electron/main.mjs`'s
     `listContentFiles`), because `Path.glob`'s `**` and a `Dirent`'s
     `isDirectory()` each answer no by default.

4. **`node_modules/` is installed on demand, never symlinked.** It is the
   largest item and the least often needed — only Electron work touches it —
   and an `npm install` through a shared symlink would rewrite the directory
   every other worktree is running from.

5. **`--own-toolchain` opts out of the shared `toolchain/`** for the one case
   that needs it: a branch that changes what the Toolchain *is* (bumping
   gregorio, recutting texmf) must not mutate what its neighbours are testing
   against.

6. **Releasing stays in the main checkout, on `main`.** `cz bump` writes
   `pyproject.toml`, `CHANGELOG.md` and a tag; doing that from a worktree is
   possible and there is no reason to. The main checkout stays on `main` for
   this and so that the symlink targets have a stable home.

7. **Teardown is `git worktree remove --force <dir> && git branch -d
   <branch>`,** and `--force` is normal rather than a warning sign: `.venv/`
   and `build/` are untracked, so git always refuses without it. The script
   prints the exact command.

## Verified, not assumed

- **`git worktree remove --force` unlinks the symlinks rather than deleting
  through them.** Tested directly, in a throwaway repository, with a symlink to
  a file outside the worktree: the target survived. This was worth proving
  because the failure would have been silent destruction of the shared
  `psalter/` clone — whose only backup it is — and of 139 MB of Toolchain.
- **A provisioned worktree passes the whole suite**: 338 passed in 8m28s, from
  a worktree in a different filesystem location, against the shared `psalter/`.
- **`.venv` per worktree costs about 9 MB, not the 172 MB `du` reports.** uv
  clones packages copy-on-write on APFS, so the files have a link count of 1
  and look like copies while sharing blocks; removing one venv reclaimed 9 MB
  of actual free space. Per-worktree venvs are therefore not the extravagance
  they appear to be, which is what makes decision 3 affordable.
- **`uv run` in a worktree warns** — `VIRTUAL_ENV=<main>/.venv does not match
  the project environment path` — when the shell still has the main checkout's
  venv activated. uv ignores the stale variable and uses the right environment,
  so this is noise rather than a fault, and `direnv allow` in the worktree ends
  it.

## Alternatives considered

- **Copy the shared state into each worktree.** Fully independent, so a branch
  could change the Toolchain without a flag — at 700 MB and a toolchain rebuild
  (with emsdk) per worktree. Decision 5 buys the same independence for the rare
  branch that needs it, at no cost to the common one.
- **Symlink `node_modules/` too**, saving 398 MB per Electron worktree. Rejected
  per decision 4: the saving is real and the failure mode — one worktree's
  `npm install` silently changing another's dependencies — is exactly the class
  of bug this project keeps finding the expensive way.
- **`.claude/worktrees/`, where Claude Code's own `EnterWorktree` puts them.**
  Already gitignored, and convenient for agents. Rejected because it nests
  hundreds of megabytes of build state inside the main checkout, where
  `scripts/toolchain/build.sh`, backups and every `find` sweep walk.
- **Flat siblings** (`../libellus-30-psalm-by-incipit`). Easier to tab-complete,
  and `repos-local/` fills up with them once several are open.
- **A `git worktree` alias or plain documentation instead of a script.** An
  alias cannot symlink nine things conditionally, and documentation of nine
  steps is a checklist someone will perform eight of.

## Consequences

The map issue gains one small **In flight** table — issue, branch, worktree,
one-line status — and nothing else; per-work detail stays in each issue, and a
row is deleted when the branch merges. This is the first thing the map has ever
needed to track that is genuinely about *where* work is happening rather than
what it is.

Two shared items are shared mutably, and that is a deliberate accepted risk.
`git -C psalter pull` in any worktree changes the Psalter that every worktree
resolves against; rebuilding `toolchain/` in any worktree without
`--own-toolchain` changes what every worktree tests against. Both are content
with a version of their own and neither changes often, but nothing enforces
this and a surprising diff in an unrelated worktree is the symptom to expect.

The script is macOS/Linux bash, like `scripts/toolchain/build.sh`. Nothing in
the workflow is Windows-aware, which is consistent with the rest of the
development tooling even though the *product* now targets Windows via Electron
(ADR-0035).

New unversioned state is now a maintenance obligation: anything gitignored that
a build needs has to be added to the script's `shared` list or a worktree
silently loses it. The list is commented with what each item is for so the next
addition has somewhere obvious to go.

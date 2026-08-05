#!/usr/bin/env bash
# Add a worktree for one line of work, provisioned so it can actually build
# (ADR-0040).
#
#   scripts/worktree-add.sh feat/30-psalm-by-incipit     # new branch
#   scripts/worktree-add.sh --checkout fix/55-elision    # branch that exists
#   scripts/worktree-add.sh --own-toolchain feat/…       # rebuilds toolchain/
#
# The worktree lands in ../libellus-worktrees/<slug>, where <slug> is the
# branch minus its type prefix — feat/30-psalm-by-incipit becomes
# 30-psalm-by-incipit. Override the parent with $LIBELLUS_WORKTREES.
#
# Almost everything that lets a checkout build a booklet is gitignored, so a
# bare `git worktree add` produces a directory that resolves no German, has no
# Toolchain and no venv. This script symlinks the expensive, shared parts back
# to the main checkout and syncs the cheap ones. node_modules is deliberately
# not among them: it is 400 MB, only Electron work needs it, and an `npm
# install` through a shared symlink would rewrite what every other worktree is
# using.
set -euo pipefail

OWN_TOOLCHAIN=0
CHECKOUT=0
while [[ ${1-} == --* ]]; do
    case "$1" in
        --own-toolchain) OWN_TOOLCHAIN=1 ;;
        --checkout) CHECKOUT=1 ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
    shift
done

BRANCH="${1-}"
if [[ -z $BRANCH ]]; then
    echo "usage: $0 [--checkout] [--own-toolchain] <type>/<issue>-<slug>" >&2
    exit 2
fi

# The convention from AGENTS.md, enforced because the directory name is derived
# from it: a branch without a type prefix would put the worktree somewhere
# surprising. `spike/` is the exception for work not meant to land as-is.
if ! [[ $BRANCH =~ ^(feat|fix|docs|chore|style|refactor|perf|test|build|ci|revert|spike)/[0-9]+-[a-z0-9][a-z0-9-]*$ ]]; then
    echo "branch must be <type>/<issue-number>-<slug>, e.g. feat/30-psalm-by-incipit" >&2
    echo "  got: $BRANCH" >&2
    exit 2
fi

# Resolve the *main* checkout, not whichever worktree this was invoked from:
# --git-common-dir points at the one real .git directory in every case.
MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
SLUG="${BRANCH#*/}"
WT="${LIBELLUS_WORKTREES:-$(dirname "$MAIN")/libellus-worktrees}/$SLUG"

if [[ -e $WT ]]; then
    echo "$WT already exists" >&2
    exit 1
fi

mkdir -p "$(dirname "$WT")"
if (( CHECKOUT )); then
    git -C "$MAIN" worktree add "$WT" "$BRANCH"
else
    git -C "$MAIN" worktree add -b "$BRANCH" "$WT"
fi

# Shared by symlink, all absolute so they survive however deep $WT sits:
#
#   toolchain/ + its download cache   93 MB and 46 MB, pinned versions built by
#                                     scripts/toolchain/build.sh, reproducible
#                                     rather than precious — but slow, and the
#                                     gregorio half needs emsdk
#   psalter/                          a clone of the private psalter-eu; without
#                                     it every German booklet fails to resolve
#                                     (resolve.py's PSALTER_DIR)
#   the private notes                 untracked source material for the feast
#                                     work, per AGENTS.md "Session state"
#   .claude/, .agents/, skills-lock   agent configuration, shared on purpose
#
# A `git -C psalter pull` in any worktree therefore changes the Psalter every
# worktree resolves against. That is intended — it is content with a repository
# of its own — but it is why psalter/ is shared and .venv is not.
shared=(
    "scripts/toolchain/.cache"
    psalter
    private-notes.md
    lambertus-email-threads.md
    lambertus-hintergrund.md
    lambert-corrections.md
    .claude
    .agents
    skills-lock.json
)
(( OWN_TOOLCHAIN )) || shared+=(toolchain)

shopt -s nullglob
for f in "$MAIN"/*-review.html; do shared+=("$(basename "$f")"); done
shopt -u nullglob

# `ln -s X D` puts the link *inside* D when D is already a directory, and since
# ADR-0041 psalter/ is one: git checks the tracked public Allioli-Arndt out into
# it. The shared Psalter therefore used to land as psalter/psalter, leaving the
# Einheitsübersetzung unreachable and every German booklet failing on a checkout
# that looked provisioned (#83). So link the entries instead, and leave whatever
# the checkout already provided alone.
#
# `"$src"/*` skipping dotfiles is load-bearing rather than incidental: psalter/
# is a clone of the companion repository, and a symlinked psalter/.git would
# make this worktree treat it as a nested repository.
link_into() {
    local src=$1 dst=$2 entry name
    for entry in "$src"/*; do
        [[ -e "$entry" ]] || continue
        name=$(basename "$entry")
        [[ -e "$dst/$name" ]] && continue
        ln -s "$entry" "$dst/$name"
    done
}

for item in "${shared[@]}"; do
    [[ -e "$MAIN/$item" ]] || continue
    if [[ -L "$WT/$item" || ( -e "$WT/$item" && ! -d "$WT/$item" ) ]]; then
        echo "worktree-add: $WT/$item already exists and is not a directory" >&2
        exit 1
    elif [[ -d "$WT/$item" ]]; then
        link_into "$MAIN/$item" "$WT/$item"
    else
        ln -s "$MAIN/$item" "$WT/$item"
    fi
done

# Two lines, gitignored globally, so no worktree ever inherits one.
printf 'uv sync\nsource .venv/bin/activate\n' > "$WT/.envrc"

uv sync --all-groups --project "$WT"

echo
echo "worktree:  $WT"
echo "branch:    $BRANCH"
if (( OWN_TOOLCHAIN )); then
    echo "toolchain: private — run scripts/toolchain/build.sh in the worktree"
else
    echo "toolchain: shared with $MAIN"
fi
echo
echo "next:  cd $WT && direnv allow"
echo "       npm install          # only if the work touches the Electron shell"
echo
echo "when it merges:  git worktree remove --force $WT && git branch -d $BRANCH"
echo "  (--force is normal here: .venv/ and build/ are untracked. Verified that"
echo "   it unlinks the symlinks above rather than deleting through them.)"

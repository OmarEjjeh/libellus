#!/usr/bin/env bash
# Spike #43, part 2, step 1: work out which texmf files the booklet actually
# needs, by asking the *native* toolchain with -recorder.
#
# Two runs, because they need different things:
#   - lualatex over the staged booklet  → the runtime set
#   - luahbtex -ini over lualatex.ini   → the format-build set
#
# Writes tree-union.txt, consumed by make-tree.sh.
#
# Caveat worth knowing before trusting the output: a recorder run records what
# was *opened*, which is not the same as what a cold start needs. The reference
# run had a warm luaotfload cache and only ever loaded one face per font
# family. make-tree.sh compensates by taking some directories whole.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
STAGE="${1:-$REPO/build/2026-09-18-lambertus}"
WORK="$HERE/work"

command -v lualatex >/dev/null || { echo "need a native TeX Live on PATH" >&2; exit 1; }

mkdir -p "$WORK"
rm -rf "$WORK/recorder"
cp -R "$STAGE" "$WORK/recorder"

stem="$(basename "$STAGE")"
(
  cd "$WORK/recorder"
  lualatex --recorder --shell-escape --interaction=nonstopmode "$stem.tex" >/dev/null 2>&1
  grep '^INPUT' "$stem.fls" | sed 's/^INPUT //' | grep '^/usr/local/texlive' | sort -u
) > "$HERE/runtime-files.txt"

# luaotfload loads fonts outside the recorder, so scrape them from the log.
tr -d '\n' < "$WORK/recorder/$stem.log" \
  | grep -oE '/usr/local/texlive/[0-9]+/texmf-dist/fonts/[a-zA-Z0-9_/.-]+\.(otf|ttf)' \
  | sort -u >> "$HERE/runtime-files.txt"

rm -rf "$WORK/ini"; mkdir -p "$WORK/ini"
(
  cd "$WORK/ini"
  luahbtex -ini -recorder -interaction=nonstopmode \
    -jobname=lualatex -progname=lualatex lualatex.ini >/dev/null 2>&1
  grep '^INPUT' lualatex.fls | sed 's/^INPUT //' | grep '^/usr/local/texlive' | sort -u
) > "$HERE/ini-files.txt"

sort -u "$HERE/runtime-files.txt" "$HERE/ini-files.txt" > "$HERE/tree-union.txt"

echo "runtime files: $(wc -l < "$HERE/runtime-files.txt")"
echo "ini files:     $(wc -l < "$HERE/ini-files.txt")"
echo "union:         $(wc -l < "$HERE/tree-union.txt")"

#!/usr/bin/env bash
# Spike #43, part 2, step 2: lay out the minimal texmf tree, in the layout
# busytex expects inside its virtual filesystem.
#
# Starts from the recorder-derived list (collect-deps.sh) and then widens it in
# three places where "what one run opened" is not "what a cold start needs".
set -euo pipefail
SP="$(cd "$(dirname "$0")" && pwd)"
TL=/usr/local/texlive/2026
OUT="$SP/tree"

rm -rf "$OUT"
mkdir -p "$OUT/texmf-dist/web2c" "$OUT/texmf-var/web2c/luahbtex"

n=0
while IFS= read -r src; do
  # The natively built lualatex.fmt is useless to us: a format is tied to the
  # engine binary that wrote it, so busytex has to build its own.
  [[ "$src" == *"/texmf-var/web2c/luahbtex/lualatex.fmt" ]] && continue

  case "$src" in
    "$TL/texmf-dist/"*)   rel="texmf-dist/${src#"$TL"/texmf-dist/}" ;;
    "$TL/texmf-var/"*)    rel="texmf-var/${src#"$TL"/texmf-var/}" ;;
    "$TL/texmf-config/"*) rel="texmf-dist/${src#"$TL"/texmf-config/}" ;;
    *) echo "unexpected path: $src" >&2; exit 1 ;;
  esac

  mkdir -p "$OUT/$(dirname "$rel")"
  cp "$src" "$OUT/$rel"
  n=$((n + 1))
done < "$SP/tree-union.txt"
echo "from the recorder list: $n files"

# kpathsea's own configuration is found via TEXMFCNF rather than by being
# opened as an input, so the recorder never saw it.
cp "$TL/texmf-dist/web2c/texmf.cnf" "$OUT/texmf-dist/web2c/texmf.cnf"

# (1) luaotfload and lualibs load modules dynamically by name, and the
# reference run had a warm font cache so it never touched the cold-start path.
# unicode-data is here for the same reason: luaotfload-multiscript reads
# Scripts.txt and ScriptExtensions.txt only when building its database.
for d in tex/luatex/luaotfload tex/luatex/lualibs tex/luatex/lua-uni-algos \
         tex/generic/unicode-data; do
  mkdir -p "$OUT/texmf-dist/$(dirname "$d")"
  rm -rf "$OUT/texmf-dist/$d"
  cp -R "$TL/texmf-dist/$d" "$OUT/texmf-dist/$d"
done
echo "added whole Lua module trees"

# (2) A recorder run records only the faces actually loaded, but fontspec
# queries a whole family (bold, italic, bold-italic) even when the booklet uses
# one face. Latin Modern is the default before fontspec takes over.
for d in fonts/opentype/public/ebgaramond fonts/truetype/SIL/charissil \
         fonts/opentype/public/xits fonts/opentype/public/lm; do
  mkdir -p "$OUT/texmf-dist/$(dirname "$d")"
  rm -rf "$OUT/texmf-dist/$d"
  cp -R "$TL/texmf-dist/$d" "$OUT/texmf-dist/$d"
done

# (3) gregoriotex ships six music fonts at 25 MB; the booklet uses greciliae.
mkdir -p "$OUT/texmf-dist/fonts/truetype/public/gregoriotex"
cp "$TL"/texmf-dist/fonts/truetype/public/gregoriotex/greciliae*.ttf \
   "$TL"/texmf-dist/fonts/truetype/public/gregoriotex/greextra.ttf \
   "$OUT/texmf-dist/fonts/truetype/public/gregoriotex/"
echo "added font families"

# kpathsea reaches TEXMFDIST through `!!`, meaning "use the ls-R database and
# never scan the directory". Without ls-R the whole tree is invisible.
gen_lsr() {
  local root="$1"
  {
    echo "% ls-R -- filename database for kpathsea; do not change this line."
    echo
    (cd "$root" && find . -type d | sort | while IFS= read -r d; do
      echo "${d}:"
      (cd "$d" && ls -A | sort)
      echo
    done)
  } > "$root/ls-R"
}
gen_lsr "$OUT/texmf-dist"
gen_lsr "$OUT/texmf-var"
echo "generated ls-R"

echo
echo "tree: $(find "$OUT" -type f | wc -l | tr -d ' ') files, $(du -sh "$OUT" | cut -f1)"

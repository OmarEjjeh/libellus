#!/usr/bin/env bash
# Assemble the Toolchain the browser application runs on (#57, ADR-0026).
#
#   scripts/toolchain/build.sh [outdir]      # default: ./toolchain
#
# Three components, none of which belongs in git:
#
#   busytex.js/.wasm      LuaHBTeX (TeX Live 2026) as WebAssembly, from
#                         TeXlyre-BusyTeX. Downloaded.
#   gregorio.mjs/.wasm    gregorio 6.1.0 as WebAssembly. Built from the upstream
#                         release with emsdk (spike/43-gregorio-wasm/build.sh).
#   texmf.tar             The minimal texmf tree, cut from a local TeX Live.
#
# WHERE THIS IS GOING (ADR-0026 decision 8): the Toolchain is meant to be a
# separately versioned GitHub release asset — built once, published, pinned by
# a minimum version in the code, downloaded on first use and cached. That is
# the goal, and it is deliberately NOT what this script does yet. Building it
# locally keeps the tracer bullet (#57) from depending on a publishing step
# before the thing is known to work end to end. When it is, this script becomes
# the release job and the application fetches from the release URL instead of
# from the dev server; the layout and the manifest below are already the shape
# that needs, so nothing about the page has to change.
#
# Needs: curl, tar. A TeX Live 2026 for the tree. emsdk only if gregorio.wasm
# is not already built.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$REPO/toolchain}"
CACHE="$HERE/.cache"

TL="${TEXLIVE_ROOT:-/usr/local/texlive/2026}"
BUSYTEX_VERSION=1.2.3
GREGORIO_VERSION=6.1.0

mkdir -p "$OUT" "$CACHE"

# ----------------------------------------------------------------- busytex
# One 480 MB archive holds the engine and three stock data packages we do not
# use — our tree replaces them, and gregoriotex is in none of them anyway. Only
# the engine is extracted; the rest is read off the stream and dropped.
if [[ ! -s "$OUT/busytex.wasm" ]]; then
  echo "downloading TeXlyre-BusyTeX $BUSYTEX_VERSION (480 MB, keeping 33 MB)…"
  curl -sSL --fail \
    "https://github.com/TeXlyre/texlyre-busytex/releases/download/assets-v$BUSYTEX_VERSION/busytex-assets.tar.gz" \
    | tar xz -C "$OUT" --strip-components=1 busytex/busytex.js busytex/busytex.wasm
fi

# ---------------------------------------------------------------- gregorio
# The version is load-bearing: gregorio bakes it into the .gtex filename
# (`<base>-6_1_0.gtex`) and GregorioTeX looks for exactly that, so the WASM
# gregorio and the tree's gregoriotex must come from the same release.
if [[ ! -s "$OUT/gregorio.wasm" ]]; then
  built="$REPO/spike/43-gregorio-wasm/work/out"
  if [[ ! -s "$built/gregorio-memfs.wasm" ]]; then
    echo "building gregorio $GREGORIO_VERSION as WebAssembly (needs emsdk on PATH)…"
    command -v emcc >/dev/null || {
      echo "emcc not found — run 'source ~/emsdk/emsdk_env.sh' first" >&2; exit 1; }
    "$REPO/spike/43-gregorio-wasm/build.sh"
  fi
  cp "$built/gregorio-memfs.mjs" "$OUT/gregorio.mjs"
  cp "$built/gregorio-memfs.wasm" "$OUT/gregorio.wasm"
  # The .mjs resolves its sibling .wasm by the name it was built under.
  sed -i '' 's/gregorio-memfs\.wasm/gregorio.wasm/g' "$OUT/gregorio.mjs"
fi

# gregorio-vowels.dat is a runtime data dependency of gregorio itself, not just
# a TeX input: it carries the vowel and elision rules. It ships inside the
# gregoriotex TeX package, so it is in the tree below as well — two consumers,
# one file, and the WASM build reaches it through $GREGORIO_DATA_DIR because
# the build has no kpathsea to ask.
cp "$TL/texmf-dist/fonts/truetype/public/gregoriotex/gregorio-vowels.dat" \
   "$OUT/gregorio-vowels.dat" 2>/dev/null \
  || cp "$(kpsewhich gregorio-vowels.dat)" "$OUT/gregorio-vowels.dat"

# ------------------------------------------------------------------- texmf
# texmf-files.txt is the recorder-derived list, pinned as data. It was produced
# once by spike/43-tex-wasm/collect-deps.sh, which needs a --shell-escape run
# over a staged booklet; keeping the output instead of the run is what makes
# this script work in a clean checkout.
#
# The list alone is NOT enough, in three documented ways — see the widenings
# below. That is not a defect in the list: a recorder records what one run
# opened, and a cold start opens more.
[[ -d "$TL" ]] || { echo "no TeX Live at $TL (set TEXLIVE_ROOT)" >&2; exit 1; }

TREE="$CACHE/tree"
rm -rf "$TREE"
mkdir -p "$TREE/texmf-dist/web2c" "$TREE/texmf-var/web2c/luahbtex"

while IFS= read -r rel; do
  [[ -n "$rel" ]] || continue
  # texmf-config holds one generated config file; busytex expects it in dist.
  dest="${rel/#texmf-config\//texmf-dist/}"
  mkdir -p "$TREE/$(dirname "$dest")"
  cp "$TL/$rel" "$TREE/$dest"
done < "$HERE/texmf-files.txt"

# kpathsea finds its own configuration through TEXMFCNF rather than by opening
# it as an input, so no recorder run ever sees it.
cp "$TL/texmf-dist/web2c/texmf.cnf" "$TREE/texmf-dist/web2c/texmf.cnf"

# (1) Lua modules are loaded dynamically by name, and the reference run had a
# warm luaotfload cache so it never touched the cold-start path at all.
# unicode-data is here for that reason too: luaotfload-multiscript reads
# Scripts.txt and ScriptExtensions.txt only while building its database.
for dir in tex/luatex/luaotfload tex/luatex/lualibs tex/luatex/lua-uni-algos \
           tex/generic/unicode-data; do
  mkdir -p "$TREE/texmf-dist/$(dirname "$dir")"
  rm -rf "${TREE:?}/texmf-dist/$dir"
  cp -R "$TL/texmf-dist/$dir" "$TREE/texmf-dist/$dir"
done

# (2) fontspec queries a whole family — bold, italic, bold-italic — even where
# the booklet only ever sets Regular, and a recorder records only the face that
# actually loaded. Latin Modern is never recorded at all but is the default
# before fontspec takes over; without it the run dies on "metric data not
# found" before anything else happens.
for dir in fonts/opentype/public/ebgaramond fonts/truetype/SIL/charissil \
           fonts/opentype/public/xits fonts/opentype/public/lm; do
  mkdir -p "$TREE/texmf-dist/$(dirname "$dir")"
  rm -rf "${TREE:?}/texmf-dist/$dir"
  cp -R "$TL/texmf-dist/$dir" "$TREE/texmf-dist/$dir"
done

# (3) gregoriotex ships six music fonts at 25 MB; the booklet uses greciliae.
mkdir -p "$TREE/texmf-dist/fonts/truetype/public/gregoriotex"
cp "$TL"/texmf-dist/fonts/truetype/public/gregoriotex/greciliae*.ttf \
   "$TL"/texmf-dist/fonts/truetype/public/gregoriotex/greextra.ttf \
   "$TREE/texmf-dist/fonts/truetype/public/gregoriotex/"

# Stock texmf.cnf reaches TEXMFDIST through `!!`, which means "use the filename
# database and never scan the directory". Without ls-R a perfectly correct tree
# is completely invisible.
generate_ls_R() {
  local root="$1"
  {
    echo "% ls-R -- filename database for kpathsea; do not change this line."
    echo
    (cd "$root" && find . -type d | sort | while IFS= read -r dir; do
      echo "${dir}:"
      (cd "$dir" && ls -A | sort)
      echo
    done)
  } > "$root/ls-R"
}
generate_ls_R "$TREE/texmf-dist"
generate_ls_R "$TREE/texmf-var"

# One archive rather than ~1 800 files: the page fetches it once, caches the
# bytes in OPFS and unpacks into the WASM filesystem per build. Thousands of
# HTTP requests and thousands of OPFS handles would both be slower.
tar cf "$OUT/texmf.tar" -C "$TREE" texmf-dist texmf-var

# ------------------------------------------------------------------ wheels
# Pyodide's own distribution already carries pydantic, pyyaml, jinja2 and
# click. These three it does not, and all three are pure Python, so they are
# fetched once rather than resolved from PyPI on every page load — which would
# make an offline build impossible and the verification test depend on the
# network.
if [[ ! -d "$OUT/wheels" ]]; then
  mkdir -p "$OUT/wheels"
  uv run --with pip -- python -m pip download --no-deps --quiet \
    --dest "$OUT/wheels" typer pypdf shellingham
fi

# ---------------------------------------------------------------- manifest
# The page keys its OPFS cache on version + size, so a rebuilt Toolchain
# invalidates it. When this becomes a release asset the same file is what the
# minimum-version pin reads.
{
  echo '{'
  echo "  \"busytex\": \"$BUSYTEX_VERSION\","
  echo "  \"gregorio\": \"$GREGORIO_VERSION\","
  echo "  \"texlive\": \"$(basename "$TL")\","
  echo '  "files": {'
  first=1
  for file in busytex.js busytex.wasm gregorio.mjs gregorio.wasm \
              gregorio-vowels.dat texmf.tar; do
    [[ $first -eq 1 ]] || echo ','
    first=0
    printf '    "%s": %s' "$file" "$(wc -c < "$OUT/$file" | tr -d ' ')"
  done
  echo
  echo '  }'
  echo '}'
} > "$OUT/manifest.json"

echo
echo "Toolchain in $OUT:"
ls -lh "$OUT" | tail -n +2
echo
echo "texmf tree: $(find "$TREE" -type f | wc -l | tr -d ' ') files"

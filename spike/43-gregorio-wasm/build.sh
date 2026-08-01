#!/usr/bin/env bash
# Spike #43, part 1: build gregorio 6.1.0 as WebAssembly.
#
# Throwaway by design (ADR-0026 decision 10). Nothing here is wired into
# libellus; it exists to answer whether gregorio survives the crossing.
#
# Needs: emsdk (activated), bison, flex, curl. Writes into ./work.
set -euo pipefail

VERSION=6.1.0
WORK="${1:-$(pwd)/work}"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$WORK"
cd "$WORK"

if [[ ! -d "gregorio-$VERSION" ]]; then
  curl -sSL -o "gregorio-$VERSION.tar.bz2" \
    "https://github.com/gregorio-project/gregorio/releases/download/v$VERSION/gregorio-$VERSION.tar.bz2"
  tar xjf "gregorio-$VERSION.tar.bz2"
  patch -p1 -d "gregorio-$VERSION" < "$HERE/0001-locate-vowel-data-without-kpsewhich.patch"
fi

cd "gregorio-$VERSION"

# --host: configure.ac hard-errors on any host_os it does not recognise, and
# emscripten's wasm32-unknown-emscripten is not one of the four it knows.
# Claiming linux is enough — nothing in the build branches on it beyond the
# automake conditionals.
#
# kpathsea is deliberately absent: --with-kpathsea is opt-in, and the only
# thing gregorio uses it for is locating gregorio-vowels.dat, which the patch
# handles via $GREGORIO_DATA_DIR.
emconfigure ./configure --host=wasm32-unknown-linux --disable-version-in-exe
emmake make -C src

OBJ=(gregorio-utils.o characters.o messages.o struct.o unicode.o sha1.o support.o
     dump/dump.o gregoriotex/gregoriotex-write.o gregoriotex/gregoriotex-position.o
     gabc/gabc-elements-determination.o gabc/gabc-write.o
     gabc/gabc-glyphs-determination.o gabc/gabc-score-determination.o
     gabc/gabc-score-determination-y.o gabc/gabc-score-determination-l.o
     gabc/gabc-notes-determination-l.o
     vowel/vowel.o vowel/vowel-rules-l.o vowel/vowel-rules-y.o)

cd src
mkdir -p "$WORK/out"

# Node build: NODERAWFS so the comparison harness can walk a staged folder
# straight off disk.
emcc -O2 -o "$WORK/out/gregorio-node.js" "${OBJ[@]}" \
  -sNODERAWFS=1 -sALLOW_MEMORY_GROWTH=1 -sEXIT_RUNTIME=1

# Browser build: MEMFS only, ES module, main not run on load. This is the
# shape the real application would consume.
emcc -O2 -o "$WORK/out/gregorio-memfs.mjs" "${OBJ[@]}" \
  -sMODULARIZE=1 -sEXPORT_ES6=1 -sFORCE_FILESYSTEM=1 -sINVOKE_RUN=0 \
  -sEXPORTED_RUNTIME_METHODS=FS,callMain,ENV -sALLOW_MEMORY_GROWTH=1 \
  -sENVIRONMENT=web,worker,node

echo
echo "built into $WORK/out:"
ls -l "$WORK/out"

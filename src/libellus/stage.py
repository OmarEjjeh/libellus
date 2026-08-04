"""Stage a self-contained build folder: rendered TeX + assets + Makefile.

The folder needs neither libellus nor the repository — running ``make``
inside it (gregorio, lualatex with gregoriotex, pdfjam, pdftk) produces the
booklet PDFs. This is the unit a Docker build job will consume. Asset paths are
copied under their logical names, unchanged, because the rendered TeX
references them that way (``\\gregorioscore{chant/...}``) — but those names no
longer say where the file is *read* from: the chant library comes from the
installed package and generated notation from ``build/.cache/``. See
:mod:`libellus.paths`.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from libellus.paths import source_of

logger = logging.getLogger(__name__)

#: `make` in the staged folder = gregorio, then the compile loop + imposition.
#: Mirrors _gregorio()/_lualatex()/impose() in libellus.compile — keep in sync.
#:
#: The gregorio step is GregorioTeX's own autocompile, hoisted out of the TeX
#: pass (ADR-0026 decision 3), so lualatex spawns nothing and needs no
#: --shell-escape. The version suffix and flags are GregorioTeX's, not ours:
#: it looks for exactly `tmp-gre/<dir>/<base>-<version>.gtex` and uses it when
#: it is newer than the .gabc. `gregorio` and the installed GregorioTeX must be
#: the same release, which the suffix enforces by itself.
_MAKEFILE_BODY = """
GABC := $(shell find chant -name '*.gabc' 2>/dev/null)
GREVERSION := $(shell gregorio --version | head -1 | cut -d' ' -f2 | tr . _)
GTEX := $(patsubst %.gabc,tmp-gre/%-$(GREVERSION).gtex,$(GABC))

all: $(STEM)-montage-duplex.pdf

# gregorio exits non-zero for a score it none the less sets usably, so the test
# is whether notation came out, not what the exit code was (ADR-0032 decision 4);
# anything gregorio had to say is echoed rather than swallowed. The one known
# case, the elision error in sanctorum-meritis.gabc, is fixed (#55) — the corpus
# compiles silently now, so anything echoed here is new.
tmp-gre/%-$(GREVERSION).gtex: %.gabc
	@mkdir -p $(dir $@)
	@gregorio -D -W -o $@ -l $(@:.gtex=.glog) $< || true
	@test -s $@ || { echo "gregorio set nothing for $< — see $(@:.gtex=.glog)"; exit 1; }
	@test ! -s $(@:.gtex=.glog) || { echo "gregorio on $<:"; sed 's/^/    /' $(@:.gtex=.glog); }

# GregorioTeX asks for a rerun when line heights, brace lengths or soft
# accidentals have moved; LaTeX asks when a cross-reference has. A pass that
# emits its PDF with either request outstanding is laid out from the *previous*
# pass's .gaux — that is how the shipped Lambertus booklet came to differ from
# its own staged folder on ten pages. Stop only once nothing is outstanding.
$(STEM).pdf: $(STEM).tex $(GTEX)
	@set -e; \\
	for i in 1 2 3 4 5 6; do \\
	  lualatex --interaction=nonstopmode $(STEM).tex || true; \\
	  test -f $(STEM).log || { echo "lualatex wrote no log at all"; exit 1; }; \\
	  if grep -q '^!' $(STEM).log; then \\
	    echo "LaTeX errors — see $(STEM).log"; grep -m5 '^!' $(STEM).log; exit 1; \\
	  fi; \\
	  if ! grep -qE 'Rerun to fix|Rerun to get cross-references right' $(STEM).log; then \\
	    test -s $(STEM).pdf || { echo "no PDF written — see $(STEM).log"; exit 1; }; \\
	    exit 0; \\
	  fi; \\
	  echo "pass $$i: layout not settled, rerunning"; \\
	done; \\
	echo "layout did not settle after 6 passes — see $(STEM).log"; exit 1

$(STEM)-montage.pdf: $(STEM).pdf
	pdfjam --booklet true --landscape --paper a4paper $(STEM).pdf -o $(STEM)-montage.pdf

# duplex printers without a binding-edge option flip the back side upside
# down; rotate every second page 180 degrees to compensate
$(STEM)-montage-duplex.pdf: $(STEM)-montage.pdf
	pdftk $(STEM)-montage.pdf rotate 1-endevensouth output $(STEM)-montage-duplex.pdf

clean:
	rm -rf *.pdf *.aux *.log *.gaux *.gtex tmp-gre/

.PHONY: all clean
"""


def stage(
    tex_source: str, assets: list[Path], stem: str, root: Path, build_dir: Path
) -> Path:
    """Write ``<stem>.tex`` + Makefile into ``build_dir`` and copy all assets.

    :param tex_source: The fully rendered LaTeX source.
    :param assets: Logical paths of the files the TeX reads at compile time;
        reproduced under these same names inside ``build_dir``.
    :param stem: Basename for the .tex/.pdf files (usually the feast slug).
    :param root: The working directory; bundled and generated assets are
        resolved relative to the package and the cache instead.
    :param build_dir: Target folder; wiped first if it already exists.
    :return: ``build_dir``.
    """
    if build_dir.exists():
        logger.info("Räume alten Satzordner „%s“ ab.", build_dir)
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

    tex_file = build_dir / f"{stem}.tex"
    tex_file.write_text(tex_source, encoding="utf-8")
    logger.debug("Geschrieben: %s (%d Zeichen).", tex_file.name, len(tex_source))

    total_bytes = 0
    for asset in sorted(set(assets)):
        source = source_of(asset, root)
        target = build_dir / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        size = source.stat().st_size
        total_bytes += size
        logger.debug("Kopiert: %s (%d Bytes).", asset, size)

    makefile = f"# Generated by libellus — `make` builds the booklet PDFs.\nSTEM := {stem}\n{_MAKEFILE_BODY}"
    (build_dir / "Makefile").write_text(makefile, encoding="utf-8")

    logger.info(
        "Satzordner fertig: „%s“ (%d Anlagen, %.1f MB).",
        build_dir, len(set(assets)), total_bytes / 1_000_000,
    )
    return build_dir

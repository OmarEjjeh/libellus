import re
from pathlib import Path

from libellus.compile import _RERUN_REQUESTS
from libellus.render import render
from libellus.resolve import build_context, load_spec
from libellus.stage import stage

from helpers import physical


def test_assets_cover_referenced_files(repo_root: Path, smoke_feast: Path) -> None:
    """Resolution records every file kind the booklet needs, as existing root-relative paths."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)

    assert all(not asset.is_absolute() for asset in resolved.assets)
    assert all(physical(asset).is_file() for asset in resolved.assets)
    assert Path("chant/ant/omnes-sancti-quanta-passi.gabc") in resolved.assets
    # psalm verses come from the shared, cross-feast tone cache (#33)
    assert Path("chant/psalmi/109/toni/8g/v01.gabc") in resolved.assets
    assert Path("chant/ordinarium/incipit.gabc") in resolved.assets
    assert Path("images/03-lambert/St-Lambert-Liege.jpg") in resolved.assets


def test_staged_folder_is_self_contained(
    repo_root: Path, smoke_feast: Path, tmp_path: Path
) -> None:
    """Every file the rendered TeX reads at compile time exists inside the staged folder."""
    spec = load_spec(smoke_feast)
    resolved = build_context(spec, repo_root)
    tex = render(spec.rite, resolved.context, repo_root)

    build_dir = stage(tex, resolved.assets, "smoke", repo_root, tmp_path / "smoke")

    assert (build_dir / "smoke.tex").read_text(encoding="utf-8") == tex
    makefile = (build_dir / "Makefile").read_text(encoding="utf-8")
    assert "STEM := smoke" in makefile
    assert "lualatex" in makefile and "pdfjam" in makefile and "pdftk" in makefile
    for score in re.findall(r"\\gregorioscore\{([^}]+)\}", tex):
        assert (build_dir / f"{score}.gabc").is_file(), score
    # Scan the document body only, not the preamble: preamble.tex.j2 defines
    # reusable macros (\goldframedimage et al., ADR-0014) whose bodies contain
    # \includegraphics calls that are just macro source — literal `#3`-style
    # parameter placeholders, or corner filenames only meaningful once the
    # macro is actually invoked with real arguments. Neither is a real asset
    # reference unless the macro is called in the body below, in which case
    # the call's own (feast-specific, Jinja-resolved) arguments show up there.
    body = tex[tex.index("\\begin{document}") :]
    for image in re.findall(r"\\includegraphics\[[^]]*\]\{([^}]+)\}", body):
        assert (build_dir / image).is_file(), image
    for filler in re.findall(r"\\input\{([^}]+)\}", tex):
        assert (build_dir / filler).is_file(), filler


def test_makefile_sets_the_notation_before_tex(repo_root: Path, tmp_path: Path) -> None:
    """gregorio runs as its own step, so lualatex spawns nothing (ADR-0026 decision 3)."""
    build_dir = stage("\\documentclass{article}", [], "smoke", repo_root, tmp_path / "smoke")

    makefile = (build_dir / "Makefile").read_text(encoding="utf-8")
    assert "gregorio -D -W" in makefile
    assert "--shell-escape" not in makefile


def test_makefile_reruns_until_the_layout_settles(repo_root: Path, tmp_path: Path) -> None:
    """Stopping with a rerun request outstanding is what shipped a stale layout (#56)."""
    build_dir = stage("\\documentclass{article}", [], "smoke", repo_root, tmp_path / "smoke")

    makefile = (build_dir / "Makefile").read_text(encoding="utf-8")
    for request in _RERUN_REQUESTS:
        assert request in makefile


def test_stage_wipes_stale_folder(repo_root: Path, tmp_path: Path) -> None:
    """Re-staging removes leftovers from a previous run."""
    build_dir = tmp_path / "smoke"
    build_dir.mkdir()
    (build_dir / "stale.aux").write_text("old", encoding="utf-8")

    stage("\\documentclass{article}", [], "smoke", repo_root, build_dir)

    assert not (build_dir / "stale.aux").exists()
    assert (build_dir / "smoke.tex").is_file()

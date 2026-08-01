import datetime
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import requires_psalter
from typer.testing import CliRunner

from libellus import cli
from libellus.formdata import FORM_FILE, embedded_island, form_data, form_data_json


@requires_psalter
def test_form_data_emits_all_vocabularies(repo_root: Path) -> None:
    """The data island (ADR-0004): every vocabulary the form needs."""
    island = form_data(repo_root)

    # tone labels come from the engine, not a hand-kept list
    assert len(island["toni"]) == 33
    assert "8G*" in island["toni"] and "peregrinus" in island["toni"]
    assert "salve-regina-simple" in island["ordinarium"]
    assert "incipit" in island["ordinarium"]
    # psalms with German verse translations actually present on disk — any
    # variant counts (de-eu2016 hand files, de-eu1980 batch, #15 re-cuts)
    assert {109, 110, 111, 112, 113, 118}.issubset(island["psalmi_cum_de"])
    assert island["psalmi_cum_de"] == sorted(set(island["psalmi_cum_de"]))
    assert island["antiphonae_per_rite"] == {
        "monasticum": 4,
        "romanum-1962": 5,
        "romanum-cum-precibus": 5,
    }
    assert "chant/ordinarium/incipit.gabc" in island["chant_paths"]
    # transient caches (generated verses, inline blocks) are not offerable paths
    assert not any("/toni/" in p or "/inline/" in p for p in island["chant_paths"])
    assert "images/02-benedict/st-benedict-mary-evans.jpg" in island["image_paths"]


def test_form_data_is_deterministic(repo_root: Path) -> None:
    """Same repo state → byte-identical output, so freshness can be diffed."""
    first = form_data_json(repo_root)
    assert first == form_data_json(repo_root)
    island = json.loads(first)
    for key in ("ordinarium", "chant_paths", "image_paths", "psalmi_cum_de"):
        assert island[key] == sorted(island[key]), key


@requires_psalter
def test_committed_island_is_current(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The island committed inside the form matches the repo state.

    This is the freshness gate: it fails whenever a vocabulary changes
    without rerunning ``libellus export-form-data`` (ADR-0004).
    """
    monkeypatch.chdir(repo_root)
    result = CliRunner().invoke(cli.app, ["export-form-data", "--check"])
    assert result.exit_code == 0, result.output


@pytest.fixture
def mini_repo(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A minimal tree holding just what export-form-data reads.

    The island is assembled from two providers — the package's chant library and
    the working directory's psalter and pictures (ADR-0024) — so the package is
    pointed here as well, and the two coincide. That keeps this fixture able to
    state the *entire* expected vocabulary, which is the point of the tests
    below; otherwise they would be asserting against the real chant library.

    The psalm-tone engine is unaffected: it is located once at import time, so
    it keeps working and the tone list stays real.
    """
    monkeypatch.setattr("libellus.paths.PACKAGE_ROOT", tmp_path)
    (tmp_path / FORM_FILE.parent).mkdir()
    shutil.copy(repo_root / FORM_FILE, tmp_path / FORM_FILE)
    (tmp_path / "chant" / "ordinarium").mkdir(parents=True)
    (tmp_path / "chant" / "ordinarium" / "salve-regina-simple.gabc").write_text(
        "name:Salve;\n%%\n(c4) Sal(f)ve(g) (::)\n", encoding="utf-8"
    )
    (tmp_path / "psalter" / "eu2016").mkdir(parents=True)
    (tmp_path / "psalter" / "eu2016" / "109.yaml").write_text(
        "1: Es sprach der Herr zu meinem Herrn.\n", encoding="utf-8"
    )
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "beispiel.png").write_bytes(b"")
    return tmp_path


def test_export_rewrites_island_and_reruns_are_noops(
    mini_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The subcommand rewrites only the marked block; rerunning changes nothing."""
    monkeypatch.chdir(mini_repo)
    form_file = mini_repo / FORM_FILE
    before = form_file.read_text(encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["export-form-data"])
    assert result.exit_code == 0, result.output
    after = form_file.read_text(encoding="utf-8")
    island = json.loads(embedded_island(after))
    assert island["ordinarium"] == ["salve-regina-simple"]
    assert island["psalmi_cum_de"] == [109]
    assert len(island["toni"]) == 33
    # everything outside the marked block is untouched
    assert before.replace(embedded_island(before), "") == after.replace(
        embedded_island(after), ""
    )

    rerun = CliRunner().invoke(cli.app, ["export-form-data"])
    assert rerun.exit_code == 0, rerun.output
    assert form_file.read_text(encoding="utf-8") == after


def test_check_fails_after_vocabulary_change(
    mini_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--check passes on a fresh island and fails once a vocabulary changed."""
    monkeypatch.chdir(mini_repo)
    runner = CliRunner()
    assert runner.invoke(cli.app, ["export-form-data"]).exit_code == 0
    assert runner.invoke(cli.app, ["export-form-data", "--check"]).exit_code == 0

    # a new ordinarium chant appears → the embedded island is now stale
    new_chant = mini_repo / "chant" / "ordinarium" / "regina-caeli.gabc"
    new_chant.write_text("name:Regina;\n%%\n(c4) Re(f)gí(g)na(g) (::)\n", encoding="utf-8")
    form_file = mini_repo / FORM_FILE
    before_check = form_file.read_text(encoding="utf-8")
    stale = runner.invoke(cli.app, ["export-form-data", "--check"])
    assert stale.exit_code == 1
    # --check never writes
    assert form_file.read_text(encoding="utf-8") == before_check

    assert runner.invoke(cli.app, ["export-form-data"]).exit_code == 0
    island = json.loads(embedded_island(form_file.read_text(encoding="utf-8")))
    assert "regina-caeli" in island["ordinarium"]
    assert runner.invoke(cli.app, ["export-form-data", "--check"]).exit_code == 0


def test_missing_island_marker_is_a_german_error(
    mini_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A form file without the marked block gets a German message, not a trace."""
    monkeypatch.chdir(mini_repo)
    (mini_repo / FORM_FILE).write_text("<html></html>\n", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["export-form-data"])
    assert result.exit_code == 1
    assert "Datenblock" in result.output + (result.stderr or "")


def test_bundle_defaults_its_output_name_beside_the_source(
    repo_root: Path, smoke_feast: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without -o the bundle lands next to the spec, so the command is safe to
    run without thinking about paths."""
    monkeypatch.chdir(repo_root)
    copied = tmp_path / "fest.yaml"
    copied.write_text(smoke_feast.read_text(encoding="utf-8"), encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["bundle", str(copied)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "fest-gebündelt.yaml").is_file()


def test_bundle_refuses_to_overwrite_its_own_source(
    repo_root: Path, smoke_feast: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """-o pointing at the spec itself would destroy the readable original."""
    monkeypatch.chdir(repo_root)
    before = smoke_feast.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        cli.app, ["bundle", str(smoke_feast), "-o", str(smoke_feast)]
    )

    assert result.exit_code == 1
    assert "dieselbe Datei" in result.output
    assert smoke_feast.read_text(encoding="utf-8") == before


def test_build_downgrades_to_staging_without_latex_tools(
    repo_root: Path,
    smoke_feast: Path,
    tmp_path: Path,
    no_latex: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing LaTeX tools on PATH → warning + build folder only, no compile."""
    monkeypatch.setattr(
        cli, "compile_pdf", lambda tex: pytest.fail("compile_pdf darf nicht laufen")
    )

    result = cli.build(smoke_feast, repo_root, builds=tmp_path)

    stem = smoke_feast.stem
    assert result == tmp_path / stem
    assert (result / f"{stem}.tex").is_file()
    assert (result / "Makefile").is_file()


#: A draft stamps the wall clock into both the folder name and the page;
#: pinning it keeps the test's build folder deterministic.
DRAFT_MOMENT = datetime.datetime(2026, 7, 30, 14, 32)


@pytest.mark.parametrize(("flag", "in_spec"), [(True, False), (False, True), (True, True)])
def test_draft_is_the_or_of_flag_and_field(
    repo_root: Path,
    smoke_feast: Path,
    tmp_path: Path,
    no_latex: None,
    monkeypatch: pytest.MonkeyPatch,
    flag: bool,
    in_spec: bool,
) -> None:
    """`--draft` or `draft: true` — either alone marks the booklet, and the
    build lands in its own timestamped folder, so a draft can never overwrite
    the final build (ADR-0021)."""
    feast = smoke_feast
    if in_spec:
        feast = tmp_path / smoke_feast.name
        feast.write_text(
            smoke_feast.read_text(encoding="utf-8") + "\ndraft: true\n", encoding="utf-8"
        )
    monkeypatch.setattr(
        cli, "datetime", SimpleNamespace(datetime=SimpleNamespace(now=lambda: DRAFT_MOMENT))
    )

    result = cli.build(feast, repo_root, draft=flag, builds=tmp_path / "build")

    stem = f"{smoke_feast.stem}-entwurf-2026-07-30-1432"
    assert result == tmp_path / "build" / stem
    tex = (result / f"{stem}.tex").read_text(encoding="utf-8")
    assert "\\SetWatermarkText{PRO MANUSCRIPTO}" in tex
    assert "Entwurf vom 30. Juli 2026, 14:32 Uhr" in tex


@pytest.fixture
def no_latex(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the LaTeX tools so a build stops after staging.

    Only those: node must stay visible, or no psalm verse can be generated.
    """
    real_which = cli.shutil.which
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda tool: None if tool in cli.LATEX_TOOLS else real_which(tool),
    )


@pytest.mark.parametrize(("flag", "in_spec"), [(True, False), (None, True), (True, True)])
def test_compact_builds_into_its_own_folder(
    repo_root: Path,
    smoke_feast: Path,
    tmp_path: Path,
    no_latex: None,
    flag: bool | None,
    in_spec: bool,
) -> None:
    """`--compact` or `compact: true` — either produces the Kurzfassung, and it
    lands beside the full booklet rather than replacing it (ADR-0022)."""
    feast = smoke_feast
    if in_spec:
        feast = tmp_path / smoke_feast.name
        feast.write_text(
            smoke_feast.read_text(encoding="utf-8") + "\ncompact: true\n", encoding="utf-8"
        )

    result = cli.build(feast, repo_root, compact=flag, builds=tmp_path / "build")

    stem = f"{smoke_feast.stem}-kurzfassung"
    assert result == tmp_path / "build" / stem
    tex = (result / f"{stem}.tex").read_text(encoding="utf-8")
    assert "\\textvers{2}{" in tex
    assert "Editio brevior" in tex


def test_no_compact_overrides_the_spec_field(
    repo_root: Path,
    smoke_feast: Path,
    tmp_path: Path,
    no_latex: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one asymmetry with `--draft`: a full booklet is never the unsafe
    outcome, so the command line may switch the Kurzfassung off again — both
    prints of one celebration have to come out of one spec (ADR-0022).

    Driven through the parser, since the switch is one option with two names
    and a third, unspoken state (absent = whatever the spec says).
    """
    feast = tmp_path / smoke_feast.name
    feast.write_text(
        smoke_feast.read_text(encoding="utf-8") + "\ncompact: true\n", encoding="utf-8"
    )
    monkeypatch.chdir(repo_root)
    # the command itself has no way to redirect the staged folder, so it is
    # injected here — the parsing is what this test is about, and staging into
    # the repo's own build/ would delete PDFs somebody has open
    real_build = cli.build
    monkeypatch.setattr(
        cli, "build", lambda *args, **kwargs: real_build(*args, **kwargs, builds=tmp_path)
    )

    result = CliRunner().invoke(
        cli.app, ["build", str(feast), "--no-latex", "--no-compact"]
    )

    assert result.exit_code == 0, result.output
    tex = (tmp_path / smoke_feast.stem / f"{smoke_feast.stem}.tex").read_text(encoding="utf-8")
    assert "\\textvers{" not in tex
    assert "Editio brevior" not in tex


def test_a_compact_draft_keeps_both_marks_and_both_suffixes(
    repo_root: Path,
    smoke_feast: Path,
    tmp_path: Path,
    no_latex: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The likeliest thing to send a reviewing priest: short enough to read,
    marked so nobody prints it."""
    monkeypatch.setattr(
        cli, "datetime", SimpleNamespace(datetime=SimpleNamespace(now=lambda: DRAFT_MOMENT))
    )

    result = cli.build(smoke_feast, repo_root, draft=True, compact=True, builds=tmp_path)

    stem = f"{smoke_feast.stem}-kurzfassung-entwurf-2026-07-30-1432"
    assert result == tmp_path / stem
    tex = (result / f"{stem}.tex").read_text(encoding="utf-8")
    assert "\\SetWatermarkText{PRO MANUSCRIPTO}" in tex
    assert "Editio brevior" in tex

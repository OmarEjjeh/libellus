import asyncio
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from pypdf import PdfWriter

from libellus.compile import (
    CompileError,
    _rerun_requested,
    compile_pdf,
    impose,
    set_imposer,
    set_runner,
    subprocess_impose,
    subprocess_runner,
)

#: The tail of a LuaLaTeX log that has nothing outstanding.
SETTLED = """Package rerunfilecheck Info: File `smoke.out' has not changed.
Output written on smoke.pdf (36 pages, 2534477 bytes).
"""


def test_settled_log_asks_for_nothing(tmp_path: Path) -> None:
    log = tmp_path / "smoke.log"
    log.write_text(SETTLED, encoding="utf-8")

    assert _rerun_requested(log) is None


def test_gregoriotex_rerun_request_is_seen(tmp_path: Path) -> None:
    """The one the staged Lambertus booklet stopped on top of (#56)."""
    log = tmp_path / "smoke.log"
    log.write_text(
        "Module gregoriotex Warning: Line heights, variable brace lengths, or "
        "soft flats/\nsharps may have changed. Rerun to fix. on input line 0\n"
        + SETTLED,
        encoding="utf-8",
    )

    assert _rerun_requested(log) == "Rerun to fix"


def test_latex_cross_reference_request_is_seen(tmp_path: Path) -> None:
    log = tmp_path / "smoke.log"
    log.write_text(
        "LaTeX Warning: Label(s) may have changed. Rerun to get cross-references "
        "right.\n" + SETTLED,
        encoding="utf-8",
    )

    assert _rerun_requested(log) == "Rerun to get cross-references right"


class FakeToolchain:
    """A runner that satisfies a compile without a shell, as the browser must.

    Writes exactly the artefacts each step is judged by — the ``.gtex`` that
    proves gregorio set the score, the log and PDF that prove LaTeX ran — so
    what it really tests is that those artefacts are the whole contract. If
    :data:`libellus.compile.Runner` ever stops being enough for a host without
    subprocesses, this is where it fails.
    """

    def __init__(self, version: str = "Gregorio 6.1.0 (kpathsea version 6.4.2).") -> None:
        self.version = version
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str], folder: Path) -> str:
        self.commands.append(list(command))
        if command[:2] == ["gregorio", "--version"]:
            return self.version
        if command[0] == "gregorio":
            gtex = folder / command[command.index("-o") + 1]
            gtex.write_text("% notation\n", encoding="utf-8")
            (folder / command[command.index("-l") + 1]).write_text("", encoding="utf-8")
            return ""
        stem = Path(command[-1]).stem
        (folder / f"{stem}.log").write_text(SETTLED, encoding="utf-8")
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with (folder / f"{stem}.pdf").open("wb") as handle:
            writer.write(handle)
        return ""


@pytest.fixture
def toolchain() -> Iterator[FakeToolchain]:
    """A fake toolchain, always uninstalled again — it is process-wide state."""
    fake = FakeToolchain()
    set_runner(fake)
    yield fake
    set_runner(subprocess_runner)


def staged(folder: Path, *scores: str) -> Path:
    """A minimal staged folder: one ``.tex`` and the named ``chant/`` scores."""
    folder.mkdir(parents=True, exist_ok=True)
    tex = folder / "smoke.tex"
    tex.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")
    for score in scores:
        path = folder / "chant" / f"{score}.gabc"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name:x;\n%%\n(c4) A(f)\n", encoding="utf-8")
    return tex


def test_an_injected_runner_compiles_without_a_shell(
    toolchain: FakeToolchain, tmp_path: Path
) -> None:
    """The seam a browser needs: no subprocess anywhere, and a PDF at the end."""
    tex = staged(tmp_path / "smoke", "ant/one", "hymn/two")

    pdf = compile_pdf(tex)

    assert pdf.is_file()
    assert ["gregorio", "--version"] in toolchain.commands
    # The notation is made first and separately, so LaTeX never autocompiles
    # and needs no --shell-escape (ADR-0026 decision 3).
    tools = [command[0] for command in toolchain.commands]
    assert tools.index("lualatex") > max(i for i, t in enumerate(tools) if t == "gregorio")
    assert not any("--shell-escape" in command for command in toolchain.commands)


def test_the_runner_is_given_the_staged_folder_and_relative_paths(
    toolchain: FakeToolchain, tmp_path: Path
) -> None:
    """kpathsea refuses to write outside the working directory, so nothing may be absolute."""
    tex = staged(tmp_path / "smoke", "ant/one")

    compile_pdf(tex)

    for command in toolchain.commands:
        assert not any(argument.startswith("/") for argument in command[1:]), command


def test_the_version_suffix_comes_from_the_toolchain_that_will_read_it(
    toolchain: FakeToolchain, tmp_path: Path
) -> None:
    """GregorioTeX looks for `<base>-<version>.gtex`, so the running gregorio names the file."""
    toolchain.version = "Gregorio 7.2.1 (kpathsea version 6.4.2)."
    tex = staged(tmp_path / "smoke", "ant/one")

    compile_pdf(tex)

    assert (tmp_path / "smoke" / "tmp-gre" / "chant" / "ant" / "one-7_2_1.gtex").is_file()


#: The same gregorio announces itself differently depending on whether it was
#: built with kpathsea. The WebAssembly build has none — that is what
#: `$GREGORIO_DATA_DIR` replaces — so it prints the short form.
@pytest.mark.parametrize(
    "banner",
    [
        "Gregorio 6.1.0 (kpathsea version 6.4.2).",
        "Gregorio 6.1.0.",
        "Gregorio 6.1.0",
    ],
    ids=["with-kpathsea", "without-kpathsea", "bare"],
)
def test_the_version_survives_every_banner_gregorio_prints(
    toolchain: FakeToolchain, tmp_path: Path, banner: str
) -> None:
    """A booklet whose notation is named wrongly loses every score in silence.

    Taking the banner's second token gives "6.1.0." for the kpathsea-less
    build, so the notation lands at `-6_1_0_.gtex`, GregorioTeX looks for
    `-6_1_0.gtex`, finds nothing, tries to autocompile, and cannot. The result
    is a booklet that is merely much shorter — no LaTeX error, nothing raised.
    """
    toolchain.version = banner
    tex = staged(tmp_path / "smoke", "ant/one")

    compile_pdf(tex)

    assert (tmp_path / "smoke" / "tmp-gre" / "chant" / "ant" / "one-6_1_0.gtex").is_file()


def test_a_toolchain_that_names_no_version_is_a_german_error(
    toolchain: FakeToolchain, tmp_path: Path
) -> None:
    """Without the version the .gtex filename is a guess, so stop rather than guess."""
    toolchain.version = ""
    tex = staged(tmp_path / "smoke", "ant/one")

    with pytest.raises(CompileError, match="Version"):
        compile_pdf(tex)


def test_the_default_runner_is_the_subprocess_one() -> None:
    """A host opts in to something else; nobody has to opt in to the shell."""
    import libellus.compile

    assert libellus.compile._runner is subprocess_runner


class FakeImposer:
    """An imposer that fabricates the two Montage files without any subprocess.

    Async because :data:`libellus.compile.Imposer` must be — see the module
    docstring's explanation of why imposition cannot share ``Runner``'s
    synchronous shape.
    """

    def __init__(self) -> None:
        self.calls: list[Path] = []

    async def __call__(self, pdf: Path) -> tuple[Path, Path]:
        self.calls.append(pdf)
        booklet = pdf.with_name(f"{pdf.stem}-montage.pdf")
        duplex = pdf.with_name(f"{pdf.stem}-montage-duplex.pdf")
        booklet.write_bytes(b"%PDF-booklet")
        duplex.write_bytes(b"%PDF-duplex")
        return booklet, duplex


@pytest.fixture
def imposer() -> Iterator[FakeImposer]:
    """A fake imposer, always uninstalled again — it is process-wide state."""
    fake = FakeImposer()
    set_imposer(fake)
    yield fake
    set_imposer(subprocess_impose)


def test_impose_awaits_whichever_imposer_is_set(imposer: FakeImposer, tmp_path: Path) -> None:
    pdf = tmp_path / "smoke.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    booklet, duplex = asyncio.run(impose(pdf))

    assert imposer.calls == [pdf]
    assert booklet.name == "smoke-montage.pdf"
    assert duplex.name == "smoke-montage-duplex.pdf"


def test_the_default_imposer_is_the_subprocess_one() -> None:
    """A host opts in to something else; nobody has to opt in to the shell."""
    import libellus.compile

    assert libellus.compile._imposer is subprocess_impose


def test_subprocess_impose_names_its_outputs_montage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Renamed from -pdfjam*/-pdfjam-duplex* — the tools are retired, not just relabeled."""
    calls: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path, **_kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        marker = "-o" if "-o" in command else "output"
        (cwd / command[command.index(marker) + 1]).write_bytes(b"%PDF-fake")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("libellus.compile.subprocess.run", fake_run)
    pdf = tmp_path / "smoke.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    booklet, duplex = asyncio.run(subprocess_impose(pdf))

    assert booklet == tmp_path / "smoke-montage.pdf"
    assert duplex == tmp_path / "smoke-montage-duplex.pdf"
    assert calls[0][0] == "pdfjam" and calls[1][0] == "pdftk"


def test_subprocess_impose_reports_a_failing_tool_in_german(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, command, stderr=b"pdfjam: command not found")

    monkeypatch.setattr("libellus.compile.subprocess.run", fake_run)
    pdf = tmp_path / "smoke.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    with pytest.raises(CompileError, match="Montage"):
        asyncio.run(subprocess_impose(pdf))

# Provenance

Every file in this folder (except this one) is an **unmodified, byte-for-byte
copy** from Ben Bloomfield's *jgabc* ("Chant Tools"):

| | |
|---|---|
| Upstream repository | <https://github.com/bbloomf/jgabc> |
| Author | Benjamin Bloomfield |
| Commit | `dff87490026adf21a97cac019a83b8611f0c2e71` |
| Fetched | 2026-07-21 (via `git clone`, files copied with `cp`) |
| License | **The Unlicense** (public-domain dedication) — full text in [`LICENSE`](LICENSE), itself copied from the upstream repo root |

## Files

| Here | Upstream path | What it is |
|---|---|---|
| `psalmtone.node.js` | `/psalmtone.node.js` | The psalm-tone pointing engine: Liber Usualis tone definitions, Latin syllabification, accent-to-note assignment. Ben's own Node entry point for the code behind <https://bbloomf.github.io/jgabc/psalmtone.html>. |
| `psalms/*.txt` (187 files) | `/psalms/*.txt` | The Clementine Vulgate psalter (all 150 psalms) and canticles, with acute accents and flex/mediant pointing (†/\*) as prepared by jgabc. The underlying text is public domain. |
| `LICENSE` | `/LICENSE` | The Unlicense. |

## Verifying

The files are never edited here — `generate.js` executes `psalmtone.node.js`
verbatim in a `vm` context and only stubs its (unused) jquery import from
the outside. To verify against upstream:

```
git clone https://github.com/bbloomf/jgabc /tmp/jgabc
git -C /tmp/jgabc checkout dff87490026adf21a97cac019a83b8611f0c2e71
diff /tmp/jgabc/psalmtone.node.js psalmtone.node.js
diff -r /tmp/jgabc/psalms psalms   # extra upstream files: index.html/js, NovaVulgata
```

Behavioral correctness is guarded separately by the golden fixtures in
`tests/data/golden/` (byte-exact engine output, see `tests/test_resolve.py`).

## When updating

Pick a new upstream commit deliberately, re-copy the files unmodified,
update the commit hash + date here, and rerun the test suite — the golden
fixtures will flag any behavior change for review.

## For the form's notation preview

`exsurge.min.js` (GABC→SVG rendering for the form's in-page notation
preview) is vendored from the **same pinned upstream commit** — but not
into this folder: per ADR-0003 the form is one self-contained HTML file,
so the byte-for-byte copy lives as the `id="vendor-exsurge"` script block
inside `form/formular.html`, recorded (URL, commit, SHA-256, license) in
that file's PROVENANCE comment. If the browser-side `psalmtone.js` (live
psalm-tone preview) is ever vendored too, use the same pinned commit and
the same in-form pattern.

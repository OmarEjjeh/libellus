# ADR-0049: The form is the editing surface — its shape, its save, and what the port deletes

Date: 2026-08-06
Status: accepted
Supersedes ADR-0047. Amends ADR-0048 (supersedes its decisions 1 and 3; keeps
decision 4 verbatim). Carries out ADR-0028 decisions 1 and 3.

## Context

ADR-0028 decided that the application absorbs the form, and #91 scheduled the
work. The first two slices built a Vite shell (ADR-0046) and a store over a
spec-shaped draft (ADR-0048), and then produced four editable text fields
against a hand-written `Field` component — while `form/formular.html` sat in the
same repository with a better one, `Feld`, carrying German labels, worked
examples, `typ`, `list`, warnings and the `.feld` class its stylesheet is built
around.

That was the wrong direction of travel, and the correction is the whole of this
record: **the form's Preact tree is not a reference for a rewrite, it is the
thing being moved.** Its components, element ids, German labels and state shape
come over intact. What gets replaced is everything underneath that existed only
because the form had no build step, no backend and no filesystem.

The file is 2171 lines, but only about 1440 are the form's own code. Three
vendored minified blobs, a Blob-URL module loader and a 400-line committed JSON
data island make up the rest, and every one of those exists solely to make a
single file work from `file://`.

## Decisions

1. **The Draft keeps the form's shape, not the spec's.** ADR-0048 decision 1
   held that the draft is `Document.toJS()` — plain data in the spec's own
   shape. It is instead the form's `leererZustand`: every antiphon slot
   allocated whether the ordo uses it or not, absent fields as `""` rather than
   missing, at least one versus always, `filler_tex` as one newline-joined
   string. The two translators that bridge it — file → form and form → file —
   come over with it.

   The gap they bridge is not an artefact of the form being old. A file omits
   optional fields; a controlled input needs a value that exists. A file carries
   the antiphons the ordo needs; an author needs somewhere to type the fifth one
   before deciding whether to keep it. That is a form/file impedance mismatch,
   and it survives any language.

   It is also where the domain knowledge lives: Simplex suppressing the choice
   of first or second Vespers (ADR-0015), the ordo determining the antiphon
   count, EUOUAE derived from the tone rather than typed (ADR-0016, ADR-0017),
   and the known-keys set that makes an unknown field survive editing and say so
   („Unbekanntes Feld … bleibt beim Speichern unverändert erhalten"). Rebuilding
   that against a spec-shaped draft would have reinvented it worse.

   **This does not expire with the TypeScript port (ADR-0027).** It gets typed.
   Zod names both sides — `z.input` and `z.output` — and `.transform()`,
   `.default()` and `.optional()` are the codec between them. The translators
   become a `FormSpec` schema plus a codec, and their hand-rolled coercion
   helpers and German-hint accumulation become `safeParse` with an error
   mapping.

2. **A save re-emits through the AST, and the round-trip guarantee is
   restated.** ADR-0047 put the bytes in the CST and the model in the AST, so
   that an edit was a splice and an untouched file was unchanged to the byte.
   That is abandoned. Saving now writes the changed values into the `Document`
   and stringifies the whole of it at width 76, which is what the form has
   always done.

   The measurement that decides it, taken on both shipped feast specs:

   | | Benedictus | Lambertus |
   |---|---|---|
   | lines differing after a no-op save | 182 / 333 | 184 / 289 |
   | values changed (`toJS()` deep-equal) | none | none |
   | comments preserved | 39 / 39 | 106 / 106 |
   | `\|` literal blocks preserved | 4 / 4 | 0 / 0 |

   The churn is `[a, b]` padded to `[ a, b ]`, two spaces before a trailing
   comment reduced to one, one trailing comment moved onto its own line, and
   `>-` folded prose re-wrapped. **`>-` declares its own line breaks
   insignificant — that is what the notation means.** GABC, where breaks do
   matter, lives in `|` literal blocks, and those come through untouched. So the
   re-emission reflows exactly the text the format says is reflowable.

   The guarantee therefore changes from *the file is unchanged to the byte* to
   **no value changes and no comment is lost**, which is `toJS()` deep-equality
   plus a comment count, and is cheap to assert.

   What this buys is disproportionate to what it costs. The CST path would have
   needed four token-level operations — set, create, remove, splice a sequence
   entry — where the AST needs one `setIn`. That is the single largest piece of
   invisible engineering in #91, and it was buying formatting stability in a
   file whose own review convention is to compare rendered PDFs with `diff-pdf`,
   never the source (`AGENTS.md`).

   A save still diffs rather than re-serialising from the draft, and that part is
   not negotiable: `setIn` over an unchanged subtree would replace its node and
   take the node's comments with it. The diff is what preserves comments; the
   re-emission is what costs formatting.

3. **ADR-0048 decision 4 stands, unchanged, and is still the sharpest edge
   here.** The YAML `Document` must never enter Immer state. Immer deep-freezes
   what it can draft, and a frozen document fails to accept an edit *while
   continuing to stringify successfully and return the unedited source* — a
   silent lost save, which is the one failure this whole design exists to
   prevent. The mechanism differs under decision 2 (a frozen `Document` rather
   than a frozen token array) but the trap and its remedy are identical, and the
   test that pins it stays.

   ADR-0048 decision 3 — re-parse the original source on every save — goes with
   the CST. It existed because `CST.setScalarValue` writes absolute values, so a
   field changed and changed back vanished from the second diff. Diffing against
   the live document has no such hazard.

4. **The vocabularies come from `libellus` at run time, through Pyodide.**
   ADR-0028 decision 3 dissolved the committed data island and paid for it with
   "the editor imports the real vocabularies" — but that assumed the TypeScript
   port had already landed, and it has not. For one round the editor asks the
   Pyodide worker the application already boots, adding one message type beside
   `boot`, `readFile` and `build`.

   This is not the island under another name, and the reason is in
   `formdata.py`: the vocabularies are read partly from the *working directory*
   — which images exist, which psalms have a German translation. A committed
   snapshot is stale the moment an author drops a picture into `images/`. Asking
   the real function is therefore better than the island ever was, not a
   stopgap for it.

   ADR-0027 decision 2 already ratified this seam and stated it is not
   throwaway: the interface designed for Pyodide is the one the TypeScript
   version keeps. At #92 the call becomes an import.

   Deliberately rejected: letting `app/serve.py` answer this over HTTP because
   it happens to be Python with `libellus` imported. Electron has no Python
   outside Pyodide and needs the worker path regardless, and a dev-server
   shortcut would mean the tests exercise a path production never takes.

5. **`boot()` is split, and the editor no longer waits for TeX.** The worker
   posts readiness twice: once when Pyodide, the wheels and the working
   directory are up — which is everything the editor, the vocabularies and
   validation need — and again when the toolchain, the engine pools and the
   busytex format are ready, which only the build button needs.

   Today a single `ready` follows all of it, so opening the application to fix a
   typo waits on roughly 80 MB of TeX that the correction will never touch. The
   change is a reordering rather than a redesign: the file map `fetchToolchain`
   returns feeds only `engines.load`, while Pyodide and the wheels are fetched
   by URL independently.

6. **exsurge is vendored, not depended on.** The notation and EUOUAE previews
   need it, and npm cannot supply it: the `exsurge` package is `0.0.0`,
   published 2016, last touched 2022. The byte-for-byte copy already in the
   repository — jgabc commit `dff87490…`, The Unlicense — moves out of the
   form's `<script>` block and into `app/pipeline/vendor/`, beside `pdf-lib`,
   with the same `PROVENANCE.md` discipline the psalm-tone engine's vendor
   folder established.

   Worth stating so it is not over-valued later: exsurge never renders the
   booklet. Gregorio does, in the TeX toolchain (ADR-0039). The preview is
   approximate by construction, so its job is not to agree with the output but
   to keep behaving the way the form's preview behaved.

7. **Two hosts write; the third declares that it cannot.** `app/serve.py` and
   the Electron shell both accept the write. The shipped browser host has no
   server and gets editing when the OPFS working directory lands (#94, ADR-0026
   decision 7). Until then `workdir.json` — already generated per host and
   fetched at boot — carries a `writable` flag, and the editor disables saving
   and says why rather than offering a button that returns 405.

   The write surface widens once, deliberately: creation is allowed, and
   `images/` joins `feasts/` behind an extension allowlist with no
   subdirectories and no traversal. The prior refusal to create was justified as
   "a PUT to a path that does not exist is a bug or an attack" — sound for feast
   specs, which are always opened before they are saved, and wrong for a new
   picture or a new feast, where creation is the entire point.

8. **A feast id is frozen when the file is first written.** It is derived from
   `date` and `title`, both of which stay editable afterwards, and it does not
   follow them. A file moving on disk because an author corrected a spelling is
   the kind of surprise that costs an editor its trust, and nothing else in the
   project refers to a feast by id, so no correctness argument forces a rename.
   The form is not a precedent here — it only ever named a download, so the
   question never arose.

9. **Validation runs on save and on demand, not on every keystroke.** The
   background problems panel #91 sketched is deferred, for a structural reason
   rather than an effort one: the application holds **one** worker, serving
   requests serially, and a build occupies it for minutes. A debounced validate
   would queue behind a running build or contend with it, and fixing that means
   a second Pyodide instance or a priority policy — work that has nothing to do
   with the port.

   The form's own local checks come over and cover the fast path: the German
   hints raised while reading a file, the psalm-without-German warning, and the
   restricted-path warning that mirrors `schema.py` (ADR-0033). At #92
   validation becomes an in-process `safeParse`, the contention disappears
   because validation stops needing the worker at all, and the debounced panel
   becomes a debounce.

## Consequences

The form's 40 Playwright tests are the port's regression suite. They drive the
UI by element id and assert on the YAML that comes out, which is behaviour
rather than markup — the property that lets a test survive a rewrite. Two
changes make them run against the application: the page they open, and the
extraction point, since the YAML preview pane is being cut down. The serialised
draft is exposed on `globalThis.libellus`, extending the harness contract
`tests/test_browser_build.py` already depends on, and the pane survives as a
collapsed `<details>` because reading the YAML you are producing is how an
author learns the format.

Those tests now need a served working directory and a booted Pyodide where they
used to need a `file://` URL, which decision 5 makes affordable and a
session-scoped browser context makes cheap.

`form/formular.html` is not deleted with this ADR. It is retired as a
maintained artefact, as ADR-0028 decision 1 said, but it keeps working for one
feast cycle — Lambertus is a real booklet with a real date, and the replacement
will be days old. The follow-up deletes it together with `export-form-data`,
the island half of `formdata.py` (`form_data` itself stays; decision 4 depends
on it), ADR-0004's mechanism and the README section. The island freshness
assertion is dropped now so a stale block cannot fail the suite in the
meantime.

`compact` and `draft` remain both fields of a feast spec and controls on the
build. That double life is deliberate and is recorded here so that a later
reader does not mistake it for an oversight and reconcile it.

The editor's state becomes describable in one sentence again, which the two
superseded decisions had made impossible: a draft in the form's shape, the
document it came from beside it, and a save that writes the difference between
them.

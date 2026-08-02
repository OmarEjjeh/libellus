# ADR-0033: Paths in a feast spec are restricted, not escaped

Date: 2026-08-02
Status: accepted

## Context

ADR-0002 gives every text field in a feast spec plain-text semantics: the `|tex`
filter escapes each LaTeX special, so an author's stray backslash prints as a
backslash and never breaks the build. `src/libellus/template/` has 134
interpolation sites and 80 of them carry that filter.

Of the 54 that do not, four take a value a *user* supplies:
`\VAR{back_cover_image}`, `\VAR{page.image}`, `\VAR{page.path}` and
`\VAR{drollery}`. Seventeen more take a `.gabc` path, which the same reasoning
covers — `gabc:` is a feast-spec field like any other. These reach
`\includegraphics{…}`, `\input{…}` and `\gregorioscore{…}` exactly as typed
(#42, and the measurement behind ADR-0027 decision 3).

The obvious fix — add `|tex` — is wrong, and this is the whole of the decision.
A path is not prose. `\includegraphics{Ss\_Petri\&Pauli.png}` does not open
`Ss_Petri&Pauli.png`; it looks for a file whose name contains a control
sequence, finds nothing, and fails in a way *less* comprehensible than the
unescaped version. Escaping neutralizes a character for the typesetter; a
filename has to reach the *filesystem* intact.

So the choice is between accepting these paths and rejecting them. Measuring
first, on TeX Live 2026, one character at a time:

| in a path | `\includegraphics` | `\input` | `\gregorioscore` | the staged `Makefile` |
|---|---|---|---|---|
| `\` | fails | fails | fails | breaks the recipe |
| `%` | fails | fails | fails | breaks `find`/`patsubst` |
| `#` | fails | ok | fails | breaks the recipe |
| `~` | ok | ok | fails | ok |
| space, `$` | ok | ok | ok | breaks `find`/`patsubst` |
| `&` `'` `,` `[` `]` `{}` `^` `ä` `è` | ok | ok | ok | ok |

Two things fall out of that table. The first is that #42's own example,
`Ss_Petri&Pauli.png`, builds fine today: modern LaTeX file-name parsing handles
`&`, and the underscore was never the problem it looks like. The second is that
no two consumers agree, and the disagreement is not principled — it is four
independent parsers, each with its own history, and a fifth (`stage.py`'s
Makefile) that is not TeX at all. The set that "works" is a property of TeX Live
2026 and of today's Makefile, and both will change; the WebAssembly toolchain of
ADR-0026 will be a sixth reading of the same filenames.

The form never produces any of this. `namensteil()` in `form/formular.html`
slugs the feast title to `[a-z0-9-]` and builds
`images/2026-09-18-sancti-lamberti.png`, so a path with a special character can
only arrive by hand-editing the YAML.

## Decision

1. **A path in a feast spec may contain only `A-Z a-z 0-9 . _ - /`.** Anything
   else is a validation error at schema level, in German, naming the offending
   characters. This is narrower than what any single consumer rejects today,
   deliberately: the rule is a property of the spec format, not a snapshot of
   one TeX release, and it costs nothing the form can produce.

   Spaces and umlauts are rejected too. A space breaks the staged folder's
   `find`/`patsubst` rules outright; an umlaut typesets cleanly, but macOS
   stores it decomposed (NFD) and Linux composed (NFC), so a staged folder that
   builds on the machine that made it can fail to find its own picture on the
   machine that prints it — the exact class of failure a self-contained staged
   folder exists to rule out.

2. **The rule applies to every path field, not only pictures.** `back_cover.image`,
   a filler page's `image`, a filler page's bare `.tex` path, every `gabc:` that
   is a path, `drollery` and `antiphona_bmv` (which resolves to
   `chant/ordinarium/<name>.gabc`). `gabc:` paths were listed as "legitimately
   raw" in the issue, which is right about escaping and wrong about safety: they
   are as user-supplied as the pictures and reach `\gregorioscore` the same way.

3. **An embedded image is exempt.** A `data:` URI is decoded into
   `images/inline/` under a name resolution invents, so its base64 — which uses
   `+` and `/` — never reaches the TeX. Inline GABC is exempt for the same
   reason. The rule is about paths, and neither of these is one.

4. **The audit is pinned rather than repeated.** `tests/test_render.py` walks
   `template/`, and every interpolation site without `|tex` must be listed in
   `RAW_INTERPOLATIONS` with the reason it may be raw. A new unescaped site
   fails the suite until somebody classifies it. This is a net under the
   convention, not a fix for it — ADR-0027 decision 3 removes the convention.

5. **A torture fixture is the proof.** A feast spec with every LaTeX special in
   every prose field, compiled end to end. It walks the schema rather than
   listing fields, so a text field added later is tortured by default and
   leaves the torture only by being named as non-prose. It compiles for real
   where the Toolchain exists and skips itself in CI, which has none: escaping
   that is merely plausible is worth little, and only LuaLaTeX can say.

## Consequences

- One file in the corpus violated the rule: `images/03-lambert/St-Lambert-Liège.jpg`,
  the Lambertus back cover. Renamed to `St-Lambert-Liege.jpg`. Both booklets
  rebuild **pixel-identical** to the shipped PDFs (36/36 and 28/28) — the name
  is not in the output — so nothing needs re-shipping.
- The filler union gets a discriminator. Without one, a rejected path inside a
  structured filler page reported the failure of *both* arms, under a location
  naming pydantic's internal validator chain — unreadable in the GitHub Actions
  summary that is the one place these messages have to work.
- A parish that wants `Rückseite.png` is told to rename the file. The message
  says which character is at fault and that the form does the renaming by
  itself. This is the cost of the decision and it is accepted knowingly.
- The rule ports unchanged: it is a property of the spec, so the TypeScript
  pipeline of ADR-0027 keeps it as-is, alongside the branded `Tex` type that
  makes decision 4's net unnecessary.

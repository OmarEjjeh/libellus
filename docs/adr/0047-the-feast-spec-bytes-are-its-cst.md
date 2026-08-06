# ADR-0047: A feast spec's bytes are its CST; the typed model is composed on top, and edits are spliced

Date: 2026-08-06
Status: **superseded 2026-08-06 by ADR-0049 decision 2** — a save re-emits
through the AST and the guarantee is restated as „no value changes and no
comment is lost", measured rather than asserted. The distinction this record
draws between the CST and the AST remains accurate and worth reading; only the
choice built on it is withdrawn.
Scopes: ADR-0003 (the surviving half), ADR-0028 decision 2.
Answers a question `docs/editor-state-management.md` did not know it was asking.

## Context

`eemeli/yaml` was chosen, and kept through ADR-0028's rewrite of everything
around it, for one stated reason: it is the only JS YAML library that
round-trips comments, "which is what keeps hand-edited `feasts/*.yaml`
readable after the application writes to them."

That reason is sound and the library delivers on it. What nobody checked is
that *comments* are not the only thing a maintainer would notice losing.
Parsing both shipped feast specs and stringifying them straight back, with no
edit in between, rewrites 298 lines of `2026-07-10-benedictus.yaml` and 135 of
`2026-09-18-lambertus.yaml`. Three distinct losses, none of them a bug:

- a trailing comment's alignment — `source: …  # as the printed booklet sets it`
  loses a space, because the AST records the comment's text and not its offset;
- flow-collection style — `psalter_de: [eu1980, eu2016]` becomes
  `[ eu1980, eu2016 ]`;
- **hand folding** — every `>-` block scalar is re-wrapped to the stringifier's
  own line width, which no author's line breaks will ever coincide with. Setting
  `lineWidth: 0` does not help, it only makes each paragraph one enormous line.

These files are read by a priest, annotated on paper, and reviewed line by
line; `2026-09-18-lambertus.yaml` carries his corrections of 30–31 July. A
booklet whose only change is that the editor was opened, and whose diff is 300
lines of re-wrapping, is unreviewable — and unreviewable is the specific
failure mode ADR-0001's whole structured-YAML premise exists to avoid.

The saving fact is that `eemeli/yaml` has two layers, not one. `Parser` emits a
**CST** — a token stream in which every space, comment and line break is itself
a token, so stringifying it back is the identity function. `Composer` builds
the **AST** `Document` on top of those same tokens, and with
`keepSourceTokens: true` every parsed node keeps a `srcToken` pointing back at
where it came from.

## Decisions

1. **The CST is the feast spec's representation; the AST is its model.** A
   loaded feast spec is both at once (`FeastDocument` in
   `app/src/feast/document.ts`): the tokens are what gets written back, the
   `Document` is what the editor reads fields out of and, in due course, what
   the store's typed draft is shaped like. Serialising is
   `tokens.map(CST.stringify).join("")` and is byte-exact by construction —
   not by care, and not by a list of stringifier options that has to be kept
   correct as the library evolves.

2. **An edit is a splice, not a re-emission.** Changing a field is
   `CST.setScalarValue(node.srcToken, value, { afterKey: true })`, which
   rewrites that scalar's tokens and leaves every other byte of the file where
   it was. This is what makes an edited feast spec's diff show the edit and
   nothing else.

   `afterKey` is load-bearing and fails quietly without it: a block scalar's
   content belongs one indent level deeper than the key it hangs off, and
   omitting the flag writes it at the key's own indent instead — which still
   stringifies, still looks plausible in a diff, and reparses to an empty
   string with a YAML error nobody is reading by then. Pinned by a test.

3. **This does not make the editor a text editor.** The typed model is still
   the thing being edited, still validated as a whole (slice 4), still the
   basis of undo (slice 2). The CST is a persistence detail underneath it, in
   the same position `eemeli/yaml` already occupied — the change is that
   untouched bytes are *preserved* rather than *regenerated*, which is what the
   ADR-0028 justification actually promised and what the AST alone cannot give.

## Consequences

- The acceptance criterion "both shipped feasts round-trip byte-for-byte
  through the editor, comments preserved" is met, and is a test rather than a
  hope, at two levels: `app/src/feast/document.test.ts` reads the two real
  files under `node`, where a stringifier bug would surface first, and
  `tests/test_editor_round_trip.py` gets the same verdict out of a real browser
  running the built bundle, served by a real host.
- **The write itself is not part of this.** Both hosts serve the Working
  directory read-only, so what is proven is the bytes the editor *would* write.
  A save is only meaningful once there is an edit to save, and it is then
  testable against something better than any assertion — a clean `git status`
  on `feasts/`. That is #91 slice 2's, along with the store that will drive it.
- YAML remains the file format, the git-tracked artifact and layer 4 of the
  fallback ladder. Nothing about the persistence model changes; what changes is
  that it can now be believed.
- Adding a field the file does not already have needs a token *created* rather
  than *set*, which `setScalar` refuses outright rather than approximating.
  That is the field tree's problem (#91 slice 3) and is deliberately left
  unsolved here.
- The store (slice 2) has to keep the loaded `FeastDocument` beside the draft,
  so a save can find the `srcToken` for each changed field. That is a real
  constraint on its design, and cheaper than the alternative it replaces.
- ADR-0028's reason for keeping `eemeli/yaml` is not weakened by any of this —
  it is the only JS YAML library that has a usable CST *at all*, so the choice
  survives a second, stronger test than the one it was made on.

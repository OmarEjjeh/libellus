# ADR-0048: The editor's state — a draft of plain data beside the file it came from

Date: 2026-08-06
Status: accepted — **amended 2026-08-06 by ADR-0049**: decision 1 is superseded
(the draft keeps the form's shape, not the spec's) and decision 3 is superseded
with ADR-0047 (no re-parse, because saving no longer splices tokens).
Decisions 2 and 4–8 stand; decision 4 in particular is restated there verbatim
and is still the sharpest edge in this area. Note that the implementation this
record describes in the past tense (`changedScalars`, `LoadedFeast`,
`overview.ts`, and the slice numbering) was **never merged** — it was written on
a branch the re-plan abandoned. The decisions are kept because they were paid
for, several of them by tests rather than by thinking; #96 rebuilds the store
and is where 2 and 4–8 become true of the code again.
Scopes: ADR-0028 decision 2; builds on ADR-0047.

## Context

ADR-0028 decision 2 chose the stack — Zustand, Immer, zundo, in that nesting —
and `docs/editor-state-management.md` recorded why. Neither says what the store
actually holds, and that turns out to be the whole question, because ADR-0047
put a constraint on it that the design record only noticed in passing:

> One constraint they did not anticipate, from ADR-0047: the store has to keep
> the loaded `FeastDocument` beside the draft, because a save finds each changed
> field's `srcToken` through it.

A feast spec is a hand-written, comment-carrying, priest-reviewed file. ADR-0047
guarantees the editor can put it back down without moving a byte it did not
mean to move, by keeping the bytes in the CST and the model in the AST. An
editor needs a third thing on top: something a UI can bind inputs to and Immer
can mutate. Getting those three to coexist is what this decides.

## Decisions

1. **The draft is plain data, not a YAML document.** The store holds a
   `FeastSpec` — the generated projection of the Pydantic model — obtained once
   with `Document.toJS()`. Components read and write it as ordinary JavaScript;
   nothing above the store sees a `Document`, a `Scalar` or a token. This is
   what makes the editing surface ordinary, and it is the only reason Immer buys
   anything: Immer cannot help with a YAML AST, only with plain objects.

2. **Saving is a diff, not a re-emission.** `changedScalars(original, draft)`
   walks the loaded spec against the draft and yields the scalars that moved;
   only those are applied to the CST. Untouched fields are therefore untouched
   *by construction* rather than by the round-trip happening to hold — the
   difference matters because the round-trip is a property of a library we do
   not own.

   A shape change (a field added or removed, a list that grew) throws
   `UnwritableChange` rather than being silently dropped. Slice 2 can only write
   a token that already exists; creating one is the field tree's problem (#91
   slice 3). A lost edit is the one failure this design exists to prevent, so it
   is loud.

3. **Every save re-parses the original source.** Keeping one token stream and
   editing it in place is cheaper and wrong: `CST.setScalarValue` writes
   absolute values, so a field changed in one save and changed *back* before the
   next is absent from the second diff and would keep the first save's value.
   Parsing four hundred lines costs well under a millisecond.

   After a successful write the store re-parses the bytes it just sent, making
   *those* the new fixed point. It does not re-read the file: what came back
   from disk could only differ if something else had written it, and silently
   adopting that would lose the user's edit rather than report the collision.

4. **The loaded feast is a class instance, and that is load-bearing.** Immer
   drafts and deep-freezes plain objects and arrays. A `FeastDocument` is a
   plain object over an array of thousands of tokens; put one in the store bare
   and Immer freezes it, after which `CST.setScalarValue` throws `Cannot assign
   to read only property 'type'` — while `serialiseFeastDocument` goes on
   working and returns the *unedited* source. A swallowed error there writes a
   file with nothing changed in it.

   A class instance is not draftable, so Immer treats it as an atomic value and
   never reaches inside. `LoadedFeast` earns its existence independently — it is
   ADR-0047's boundary expressed as an object, owning `bytesFor(draft)` — but
   the Immer property is why it may never quietly become an interface. A test
   asserts the tokens are unfrozen.

5. **Only the draft is undoable, and only when it moves.** zundo's `partialize`
   tracks `draft` and nothing else. `loaded` must not be, or undoing past an
   open would leave a draft with no document to save it through; `status` and
   `problem` report on now, which the past has no business restoring.

   An `equality` on `draft`'s identity is what stops the rest of the store from
   entering the history sideways. Without it every `set` pushes an entry,
   including the ones that only move `status` — so a failed save leaves a ⌘Z
   that looks available and does nothing, and *arms the throttle below*, which
   then drops the user's next keystroke from the history. Immer's structural
   sharing is what makes an identity check exact enough to rely on.

6. **Loading is not an edit; saving is not a boundary.** Both replace the draft
   wholesale and both run inside `untracked()`, which pauses zundo — checked
   before the throttle, so a paused change cannot arm the window either.

   Opening additionally *forgets* the history: undo must not walk from this
   feast into the previous one's draft and then write it out under this one's
   name. Saving deliberately does **not**. Undoing across a save is legitimate
   and useful — it lands on an older draft, which then simply reads as changed
   against the file just written, and can be saved again.

   Two things were found by tests rather than by thinking. An open fires `set`
   twice, which opened the throttle window, and the user's first real keystroke
   landed inside it and was dropped from the history entirely — hence the
   throttle is reset whenever the history is cleared, not only when it fires.
   And an open is asynchronous, so two feasts chosen in quick succession are two
   fetches that can land out of order; a generation counter discards the stale
   one, without which the editor shows one feast while the select names another,
   and then saves it under that name.

7. **The undo throttle is leading-edge, at 500 ms.** zundo is handed the state
   *before* an edit, so firing on the first keystroke of a burst records where
   the burst started, which is where ⌘Z should land. This is
   `docs/editor-state-management.md`'s `handleSet` throttle and is deliberately
   distinct from the exsurge render debounce (~150–300 ms) that slice 5 adds.

8. **`zustand/vanilla`, with `react` aliased to `preact/compat`.** The default
   `zustand` entry imports React, which this application does not have. The
   store itself uses the vanilla entry; `zundo`, however, imports `zustand`'s
   React entry internally, so the alias is required regardless and is stated
   outright in `vite.config.mts` rather than left to `@preact/preset-vite` —
   which sets it for a browser build but not for Vitest's Node-side resolution,
   where the two packages must also be `inline`d.

## Consequences

- The UI never sees YAML, so a component is testable without one.
- `overview.ts` moved from reading the `Document` to reading the draft. It had
  to: a summary read from the loaded document shows what was on disk when the
  feast was opened, not what the user has typed.
- Saving is offered only when the diff is non-empty, so "save" and "there is
  something to save" cannot disagree.
- Non-string scalars (`psalmus: 109`, `draft: false`) are readable and not yet
  editable. They round-trip untouched; typing into them is slice 3's, once the
  field tree knows what control each one deserves.
- The transport is the seam and not the design: `saveFeastSpec()` is one
  function with a `PUT` behind it on both hosts today, and an OPFS write behind
  it in the shipped browser host (#94, ADR-0026 decision 7).
- **Switching feasts discards unsaved edits without warning, and undo cannot
  reach them** — opening forgets the history by decision 6. Acceptable while the
  editable surface is four identity fields; it stops being acceptable with the
  field tree, which is where the guard belongs (#91 slice 3), together with
  whatever the browser host needs for the same reason (#94).

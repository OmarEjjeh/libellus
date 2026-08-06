# Editor state management — design record

The design of an editor UI over the `FeastSpec` model for the JS/TS side of the
port (ADR-0027): the Pydantic model translated to Zod, undo/redo, and GABC chant
rendering via exsurge.js.

**Partly decided, partly still a record.** The stack below was ratified by
ADR-0028 decision 2; #91 slice 1 has built the shell on it and turned two
further questions into ADR-0046 (the application is a build, and both hosts
serve it) and ADR-0047 (a feast spec's bytes are its CST). The store, the
validation split and the GABC rendering discipline are still records rather
than decisions, and are #91's slices 2, 4 and 5.

One correction the experiment forced, before reading further: **the Zod split
below is not what slice 4 builds.** ADR-0028 decision 3 assumed the schema was
already Zod in `core`; it is not, and the TypeScript port (ADR-0027, #92)
follows this work rather than preceding it. So the strict tier calls the real
`libellus.schema` through the Pyodide worker for one round, and the two-tier
shape below is what it will grow into afterwards.

## Decisions made

### State management stack
- **Zustand** for the editor's global state (the in-progress `FeastSpec` draft).
- **Immer** middleware (`zustand/middleware/immer`) so nested field updates
  (`state.spec.antiphonae[i].de = value`) can be written as direct mutation instead
  of manual spread chains through `FeastSpec`'s nesting (antiphons → capitulum →
  versus, etc.). Also gives structural sharing — untouched branches keep their
  object reference, which matters for both render performance and cheap undo
  snapshots.
- **zundo** for undo/redo, wrapping the Immer-wrapped store: `temporal(immer(...))`
  — middleware order matters, Immer must be innermost so zundo snapshots the
  already-immutable post-Immer state.
- Middleware composition pattern is directly analogous to Python decorators
  stacking, or WSGI middleware — each layer adds a concern without the core store
  logic knowing it's there.

### Zod: draft vs. strict schema split
Two-tier validation, not two independent models:
- **Draft/shape schema** — permissive, no cross-field refinements, no format
  validation. This is what Zustand holds as live editor state. Prevents legitimate
  mid-edit states (e.g. a required German field temporarily null) from throwing.
- **Strict schema** — the draft schema plus `.superRefine(...)` layering in all the
  Pydantic-equivalent validators (`_german_present_unless_latin_only`,
  `_antiphonae_count_matches_rite`, GABC source format checks, etc.). Only run
  on-demand: save/export, or a debounced background "problems" panel — never as a
  precondition for `set()` calls.
- One schema definition, not two maintained in parallel — the strict schema is
  literally `DraftSchema.superRefine(...)`, so there's nothing to keep in sync by
  hand.
- `superRefine` (not `refine`) is the right primitive because it supports emitting
  multiple named issues via `ctx.addIssue`, matching Pydantic's "report every
  violation at once" behavior rather than failing on the first one.

### Pydantic → Zod translation notes
- Most fields map directly (`z.string()`, `z.number().min().max()`, literal unions
  for `Rank`/`Rite`).
- `FillerEntry`: Pydantic discriminates by `isinstance`/shape, not a literal tag
  field. Zod's `z.discriminatedUnion` needs a literal discriminator key, which
  doesn't exist here — use `z.union([FillerPageSchema, TexPagePathSchema])`
  instead. Zod tries both arms and reports both failures on mismatch — slightly
  noisier error output than the Python `_filler_kind` approach, but functionally
  equivalent for a 2-arm union.
- `GabcSource` has the same "two shapes, no explicit tag" pattern (inline GABC
  string vs. `.gabc` repo path) — validated the same way, as a strict-tier
  refinement (`isInlineGabc` / path-safety checks) layered onto a plain
  `z.string()` shape.

### GABC rendering (exsurge.js) — kept out of the store entirely
- The store holds only the GABC source string. Rendered SVG is derived, ephemeral
  output computed in the component (`useEffect` keyed on a debounced value), not
  app state.
- Reasoning: GABC is invalid constantly mid-edit (expected, not exceptional —
  handle via try/catch around the parse, not validation gating), and exsurge
  parsing/layout isn't free enough to run on every keystroke or every store
  `set()`.
- **Two independent debounce/throttle points, different purposes, don't conflate:**
  - zundo's `handleSet` throttle (~500ms) — controls undo-step granularity.
  - A separate debounce on the render trigger (~150–300ms) — controls how often
    exsurge actually re-parses/re-lays-out.
- **Render cache**, keyed by GABC string content, so undo/redo replay of
  previously-seen strings doesn't re-run exsurge. Cap size or use LRU; undo
  history itself is already capped (e.g. `limit: 100`), so a lazy cache bounds
  naturally.
- Consider offloading exsurge to a Web Worker if editing longer scores (full
  hymns, multi-verse) — not needed for short antiphon incipits.

## Open question — not yet resolved
`GabcSource`'s dual nature (inline string vs. `.gabc` file path reference): when a
user opens the editor on an antiphon that currently references a file path, does
opening the editor fetch the file content and silently convert the field to inline
on first keystroke? This is a state transition (path → inline) that changes what
gets serialized back out, and should be an explicit store action, not implicit UI
behavior. **Needs a decision before implementation.**

## What this still needs

- The open question above answered. It is the one item here that blocks
  implementation rather than merely wanting to be written down, and #91 answers
  it: conversion on first edit rather than on open, as a named store action
  (`detachGabcToInline`) so undo restores the path in one step, and visible in
  the field. It is slice 5's to build.
- The state-management decisions above turned into ADRs as they are built
  (slice 2), and any new terms they introduce added to `CONTEXT.md`.
- One constraint they did not anticipate, from ADR-0047: the store has to keep
  the loaded `FeastDocument` beside the draft, because a save finds each
  changed field's `srcToken` through it.

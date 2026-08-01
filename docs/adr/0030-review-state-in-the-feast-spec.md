# ADR-0030: Review state lives in the feast spec — `todo:`, a fingerprint-bound `reviewed:`, and a booklet-level checklist

Date: 2026-08-01
Status: accepted

## Context

The review-and-correct loop is the only part of producing a booklet that has no
home in the repository. It lives in `HANDOFF.md` — proofreading passes,
"assumptions to confirm with Omar", the German review, per-feast TODOs — and in
correspondence. `HANDOFF.md` is untracked by design and will not survive the
maintainer's departure in January 2027. ADR-0021's **Entwurf** is the one piece of
this that reached the data model.

The all-in-one (ADR-0026) makes the gap conspicuous: once the application lists
the feasts in a Working directory, the obvious next question is which of them are
finished, and nothing in the repository can answer it.

The temptation is to build a workflow engine. The scoping constraint is that this
must be small enough that its *content* is the work and its code is trivial.

## Decisions

1. **`todo:`** — a plain-text marker allowed on any element and as a top-level
   list. The build logs a German `WARNING` per open item; the editor shows a badge
   and jumps to the field. Already the recorded intent in `IDEAS.md` ("add TODO
   option in the form and in the yaml, libellus should log WARNINGS when such
   lines are found").

   A `todo:` is a *negative, sparse, freeform* marker — added only where something
   is known to be wrong. Its absence means nothing. It answers: **is anything known
   to be broken?**

2. **`reviewed:`** — a per-element marker, *positive, dense and binary*, so the
   editor can say "9 of 12 reviewed". It answers a different question: **has
   everything been looked at?** The two are complementary, not alternatives.

   Two durable states only: absent means not reviewed, present means reviewed.
   "In review" is a property of the *booklet* (some elements reviewed, some not),
   which the list view derives, or transient UI state while looking at something —
   neither needs storing.

   The reason to have this at all: the review loop is not per-pass in practice,
   whatever `HANDOFF.md`'s "proofread the whole booklet end-to-end" suggests.
   That item has stayed open for weeks precisely *because* it is one
   undifferentiated task with no way to stop halfway. Per-element markers make
   review resumable.

3. **`reviewed:` is bound to the content by a fingerprint, not to the element by
   name.** The value is a hash of the element's canonical serialisation. On load
   the hash is recomputed; if it differs, the element silently drops back to
   unreviewed.

   This is part of the definition of the feature, not a refinement. Without it,
   marking the Magnificat antiphon reviewed and then editing its German leaves a
   flag that is lying — and a review tracker you cannot trust is worse than none,
   because it manufactures confidence at exactly the moment it matters. The
   alternative — letting the editor clear the flag when it sees an edit — breaks
   the moment a spec is hand-edited in a text editor or through the GitHub web
   editor, both of which are supported paths. The repository already has the
   pattern: `build/.cache/` keys generated psalm notation by content.

4. **A booklet-level checklist**, scoped to the cross-cutting checks that have no
   element to attach to: page count divisible by four, proof printed and read on
   paper, whole-booklet reflow after a late edit. Three or four items, not ten —
   per-element `reviewed:` absorbs everything element-shaped.

   Each item carries an optional German `hint:`, and this is the part that matters
   most. The checklist template encodes *what a review consists of*, which is
   precisely the tacit knowledge that leaves with the maintainer. It also gives
   `IDEAS.md`'s "i need to leave a crash course on how to use the liber usualis
   and other sources" a home where it will actually be read: not a document
   nobody opens, but text the application puts in front of you at the moment you
   need it. The code is trivial; the hint text is the work.

5. **No `status:` enum.** A completed checklist *is* the status, so an independent
   enum is a second source of truth that can disagree with the first. Worse, it
   would overlap `draft:` by most of its range, and ADR-0021 is careful about
   that: `draft:` is a typographic fact about a copy in circulation, settable from
   anywhere and clearable only in the spec. The list-view badge is derived, not
   stored.

6. **No per-element review of *elements the schema does not have*.** Rejected a
   design where review state lived in a sidecar file
   (`feasts/<feast>.review.yaml`). It has the better purity argument — the spec
   stays purely about the booklet, which protects layer 4, where the spec is what
   "still documents intent" after all tooling has rotted. It loses on the
   precedent ADR-0021 set: `draft:` is stored in the spec *specifically so it
   travels*, so "a spec passed on stays a draft in the recipient's hands". The
   same logic applies here, and a sidecar is a file that gets separated from its
   spec exactly once and is then worthless.

7. **`draft: true` suppresses the unreviewed warning.** An Entwurf is *supposed*
   to be unreviewed — that is what it is for. A non-draft build with unreviewed
   elements is exactly the thing the tool should be shouting about. The existing
   draft concept therefore gains a second, coherent meaning instead of being
   duplicated by a new one, which is the same reason decision 5 rejects the status
   enum.

## Consequences

- The feast spec now carries a third kind of field. It held properties of **the
  celebration** (title, rank, propers) and properties of **a copy** (`draft:`,
  `compact:`); review state is a property of *the work of producing the booklet*,
  and it never prints. Worth watching: this is the category most likely to accrete
  fields, and the checklist is the pressure valve — cross-cutting concerns go
  there, not into new top-level keys.
- A completed review is invalidated by any edit, including a trivial one. That is
  the intended behaviour and will occasionally be annoying.
- The liturgical-calendar feature (ADR-0012's "calendar-aware picker", still
  future work) is deliberately not touched here and is not blocked by it.

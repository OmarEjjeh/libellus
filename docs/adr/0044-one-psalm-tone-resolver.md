# ADR-0044: One psalm-tone resolver — measurement and inference behind one contract, and it never fills `tonus:`

Date: 2026-08-06
Status: accepted

## Context

Two open issues described the same goal by different routes and neither
referenced the other. #21 wanted the tone preselected from an antiphon's
transcribed EUOUAE; #24 wanted the differentia derived from the antiphon's
opening note. Issue #46 merged them, and the merge is the interesting part:
they are **not** two implementations of one function.

|  | question answered | availability | ambiguity |
|---|---|---|---|
| Measurement (#21) | what does this transcription *say*? | only where a EUOUAE was written | none — every ending's EUOUAE is distinct (ADR-0042) |
| Inference (#24) | what tone *should* this antiphon take? | always — needs the mode and one note | ties are possible |

They cover each other's blind spots exactly. Mode 1's `D` and `D-` both close
on `d`, so the connection rule cannot separate them — "no derivable rule was
found", as #24 put it. But their EUOUAEs differ at the fifth neume, inside the
five leading neumes `differentia_candidates` compares:

```
1D   -> h h g f gh gvFED.
1D-  -> h h g f g  gvFED.
```

So measurement resolves precisely the tie inference cannot, and inference
answers precisely the antiphons measurement is silent about. Measurement was
already built and live (`gabc.differentia_candidates`, `resolve._verify_tonus`
— issue #33); inference was entirely unbuilt.

The corpus is small enough to state the result rather than estimate it. Over
the eleven antiphons the two shipped booklets sing, the resolver's strongest
candidate names the tone the spec actually sets in nine cases. The two it gets
wrong are both scores that print no cue at all, where only the convention can
speak — and both are caught, not hidden, because the `euouae:` assertion in
the feast spec then contradicts it.

## Decision

**One pure function, `tonus.resolve_tonus(gabc, euouae_per_tonus)`, returning
ranked `TonusCandidate`s**, each tagged with the `Provenance` that earned it:
`euouae`, `euouae-leading`, `connection`, `mode-only`. Measurement ranks
before inference. Six things follow, and each was chosen against a plausible
alternative.

**1. Candidates are not deduplicated.** A label both operations propose
appears twice, once per provenance. Collapsing them to "the strongest" reads
tidier and is wrong: it makes *agreement* indistinguishable from *inference
having stayed silent*, and it breaks the only honest definition of a
disagreement — measured and inferred sets both non-empty and disjoint. With a
tie on one side (`1D` measured, `1D`/`1D-`/`1D2` inferred) a collapsed list
would leave two lonely `connection` entries and report a contradiction that is
not there.

**2. Disagreement is reported, never resolved, and never fails a build.** The
connection rule is a convention, not a law, and three of the antiphons the two
shipped booklets sing contradict it — once each score is read together with the
``euouae:`` assertion the feast spec supplies for it, which is how the build
reads them:

| antiphon | notated cue says | connection rule says |
|---|---|---|
| Vir Domini Benedictus | `1f` (its own EUOUAE) | `1D`, `1D-`, `1D2` |
| Corpora Sanctorum in pace | `1f` (the `euouae:` assertion) | `1D`, `1D-`, `1D2` |
| Cum palma ad regna | `8G` (the `euouae:` assertion) | `8G*` |

Only the first is a contradiction the score alone shows; the other two print no
cue, so from the score alone the rule is simply the only voice — and it is
wrong, which is exactly why it may not be authoritative. Each is sung as its
`tonus:` says, so making the rule decide would break three correct booklets.
Making it a *warning* would cry wolf on every build of both. So `_verify_tonus`
still fails only on measurement, logs a disagreement at DEBUG, and the German
sentence that says a contradiction has been found — as opposed to nothing
having matched — is `tonus_message`, for the surface that asks a human. The
disagreements double as the feature's validation set: they are where either a
transcription or a convention is worth a second look.

**3. `tonus:` is never auto-filled.** The field stays human-authored.
ADR-0016/ADR-0017 make the EUOUAE *derived* from the tone and the `euouae:`
field an *assertion* about it. Running that arrow backwards to preselect a
value for a person is legitimate; running it backwards into the spec would
close the loop on itself, and the printed cue would then be derived from a
tone that was derived from the printed cue.

**4. A tie is returned whole.** No candidate set is ever narrowed to one
invented label. Where mode 1 offers three `d`-closing endings, all three come
back: the difference between them is an ornamental note count that — per the
upstream jgabc source — follows no derivable text or syllable rule and is a
fixed editorial choice of a particular printed antiphonale.

**5. The connection rule compares *pitch classes*.** `gabc.opening_pitch_class`
and `gabc.final_pitch_class` transpose into `CANONICAL_CLEF` and then reduce
modulo the octave. The clef half is ADR-0042's, and mandatory: pitch letters
are staff positions. The octave half is needed because the engine's own table
is not written in one register — mode 2's row sits a whole octave above the
staff. Nothing is lost by the reduction, and that is asserted rather than
assumed: within every mode the endings' closing notes span less than an octave
(`test_no_mode_has_two_endings_an_octave_apart`), so no two endings the rule
could otherwise separate are merged. Mode 4 is the tight case, spanning six
positions of seven.

**6. A mode's endings come from the engine's own labels.** `endings_of_mode`
is a prefix match against `euouae_per_tonus` — `8G` for `mode:8`,
`peregrinus` for `mode:p` — not a table on this side listing which endings
belong to which mode. Same reasoning as the EUOUAE table itself (#33): a
second copy is a second thing to keep true.

**The tone table is a parameter, not a call.** `resolve_tonus` takes
`euouae_per_tonus` the way `differentia_candidates` already does. That keeps
it pure and testable without a JavaScript runtime, and leaves the German for a
missing runtime with the caller that knows what it was doing.

**It is a function over a gabc body, not a stamp in the chant index.** #21's
premise was that the tone is precomputed into the index when the bundled data
is built. Per ADR-0005, „Übernehmen" writes notation *inline* into the field
and discards the index reference — so at the moment the author needs the
suggestion, the stamp is unreachable. An antiphon hand-transcribed in jgabc
(#25) has no index entry at all, ever. Any index stamp is therefore a
precomputed cache of this same function, which is #47.

## Consequences

- **`_verify_tonus` is the resolver's only caller today**, at both of its call
  sites — the antiphon's own EUOUAE and the `euouae:` assertion — so the
  build's check and the editor's suggestion will share one matcher and cannot
  drift. The third caller the issue counts on is #47's surface, which does not
  exist yet. `_verify_tonus` passes the EUOUAE it is checking explicitly,
  because that may be the `euouae:` field rather than anything in the score.
- **Reading a candidate list back apart is `labels_with`, and public.** A
  caller writing its own comprehension over `.provenance` would be the third
  copy of a rule this module exists to hold once.
- **Both booklets stage byte-for-byte unchanged.** The refactor is
  behaviour-preserving: `exact == [tonus]` became `tonus in exact`, which is
  the same test given that every ending's EUOUAE is distinct.
- **`gabc.read_headers` now delegates to a text-based `_headers`**, because a
  resolver over a gabc *body* cannot open a file. `find_mode` reads the
  declared `mode:` header rather than guessing from the melody — every corpus
  antiphon carries one, and no reading of the notes would be as reliable.
- **`opening_pitch_class` drops accidentals before looking for a note.** gabc
  spells an accidental with the pitch letter it applies to — tone I's B-flat
  is `ixi`, accidental on `i` then the note `i` — so the naïve "first pitch
  letter" would name the wrong note wherever a score opens under a flat. No
  corpus antiphon does, but the spelling is in the corpus.
- **The German cue is called *notiert*, not "the antiphon's".** A measured
  candidate may equally have come from the `euouae:` assertion, and the
  message layer cannot tell which.
- **The `mode-only` fallback names the mode, not an ending** —
  „Modus 8 — Endung bitte wählen: „8G", „8G*" oder „8c"". The tonus peregrinus
  is its own label and names no number, so it gets the sentence without the
  „Modus" clause rather than a nonsense „Modus p".
- **The editor surface and the index precompute are not here** — #47.
  `tonus_message` is the German the AC asks for and the whole of the
  presentation this issue owns; nothing in the application calls the resolver
  yet except the build's own check.
- **Clef normalisation of the printed cue is still open** (#80). This resolver
  *reads* under any clef; what gregorio prints after an antiphon is still
  written in `c4` regardless, which ADR-0042 left open for want of a register
  rule.

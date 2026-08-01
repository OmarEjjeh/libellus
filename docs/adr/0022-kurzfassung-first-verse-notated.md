# A Kurzfassung notates only the first verse

Date: 2026-07-30
Status: accepted

Lambert and Benedict are both 36 pages, and 61 of the staged `.tex`'s 79
`\gregorioscore` calls are single psalm or Magnificat verses; the hymn adds six
more, one per stanza. A schola that sings this office every month does not need
any of them printed. `libellus build --compact`, or `compact: true` in the feast
spec, prints the **first** verse of every psalm and of the Magnificat as a score
and every following verse as pointed Latin text with its German beneath, and
the hymn as one notated stanza followed by its remaining stanzas as text.
Everything else in the booklet is untouched.

**Amended 2026-07-31 for the canticles.** „Magníficat" is a single word and
cannot carry the tone's mediant cadence, so jgabc shortens the formula for that
verse — and a booklet notating verse 1 alone therefore never shows the cadence
the other eleven verses use. Competence cannot supply an unseen cadence, which
is a different matter from knowing that later verses start on the tenor. Across
all 33 tone/ending pairs exactly two first half-verses lack their accent, and
both are the Magnificat; the cause is structural and will recur at „Benedíctus"
and „Nunc dimíttis". So **a canticle prints its first two verses under one
system**, the way the Liber Usualis prints this canticle: the notes of the
complete verse, verse 1's syllables where they fall, verse 2's beneath them, the
reciting notes hollow, and the notes verse 1 has no words for simply standing
there. See the section at the end for how that is built. Psalms are unaffected —
every psalm's verse 1 realizes its cadence.

**The reader of a Kurzfassung is assumed to be a competent singer.** That premise
decides the two questions the feature otherwise cannot answer. It is why exactly
one verse is notated even though verse 1 is the one verse whose melody nobody
else follows — it alone carries the intonation (`Di(g)xit(h) Dó(j)…`), while
verses 2 and following start flat on the tenor. Notating verses 1 *and* 2, so
that both the intoned and the ordinary shape appear, was considered and rejected:
a singer who reaches for this booklet knows that later verses begin on the tenor,
and the extra score per psalm buys that singer nothing. It is also why the text
verses keep their pointing rather than reading as clean prose.

Design decisions worth recording:

- **The pointing is derived, not authored.** Psalm and Magnificat verses are
  generated per tone (`chant/psalmi/109/toni/8g/v02.gabc`) and already carry the
  full Liber apparatus — the verse number, `<b>` on the accented cadence
  syllable, `<i>` on the preparatory ones, `*` at the mediant. A text verse is
  therefore that gabc with the neumes stripped and the markup kept, which is why
  `gabc.py` grows a sibling to `_plain_text()` instead of a new text source.
  Dropping the markup for a cleaner page was rejected: it is the only thing
  telling the singer where the cadence falls, and it costs nothing to keep.
- **Half-verses stay broken.** The first half-verse ends at the red `*`, the
  second is indented on its own line, the German follows beneath in `\pstrans`
  as everywhere else. A text verse then presents the same landmarks in the same
  places as the notated verse it replaces. Run-on prose would save more paper
  and two columns of Latin against German more still, but both abandon the
  interlinear principle the rest of the book follows.
- **The pointing is the same bold and italic the score already prints.**
  Gregorio sets `<b>`/`<i>` in the lyrics under the neumes too, so a text verse
  and a notated verse mark the cadence identically — the compact page is not a
  different notation, it is the same words with the staff taken away.
- **A hymn's closing Amen is not a stanza.** It stands behind its own divisio
  finalis, so a naive split counts it as one and every real hymn then fails the
  count check against `hymnus.de`. It is sung with the doxology, has no German
  of its own, and therefore joins the last stanza's lines. Its notes are lost
  in a Kurzfassung — the truncated score stops after stanza one — which is
  accepted: the reader is a singer who knows the hymn's Amen.
- **Hymn stanzas are split on `(::)`, and a mismatch is a hard error.** The hymn
  is hand-transcribed, one stanza per body line, so the split is mechanical —
  but nothing guarantees the next transcription cooperates. If the Latin stanza
  count does not equal the number of entries in `hymnus.de`, the build fails
  with a German message naming both counts, rather than quietly falling back to
  the fully notated hymn and handing you a Kurzfassung that isn't one. The
  mismatch is worth failing on anyway: it means the German stanza numbering in
  the *ordinary* booklet is already wrong. An explicit `hymnus.la:` list in the
  spec was rejected as a second copy of text the gabc already holds, and against
  the precedent of every other derived value here (ADR-0017, ADR-0020).
- **`--no-compact` clears the spec field, unlike `--draft`.** ADR-0021 made a
  draft unclearable from the command line because clearing it produces a
  printable PDF of unreviewed text. Nothing is unsafe about a full booklet, and
  a full and a compact print of the same celebration are both wanted on the same
  evening — visitors get the one, the schola the other. So one spec must yield
  both variants without being edited.
- **A Kurzfassung declares itself on the cover** with `Editio brevior` beneath
  „Ad usum amicorum", and the instructions page gains one sentence: „Nur der
  erste Vers ist in Noten gesetzt; die folgenden Verse werden auf denselben Ton
  gesungen." Without the cover line the two PDFs differ only from page five on,
  and whoever hands out booklets before Vespers has nothing to go by but
  thickness — the same problem ADR-0021's watermark solves for drafts. Dropping
  the instructions page entirely, on the grounds that a competent singer does
  not need it, was rejected: that turns a rendering option into a separate
  edition, and a Kurzfassung must still be handable to a visitor who turns up
  wanting to sing.
- **One switch, no per-element granularity.** Not `compact: [psalmi, hymnus]`.
  The three long elements are the whole feature; the day someone wants a fully
  notated hymn in a short booklet is the day to add it.

Antiphons stay fully notated in every case — each carries the EUOUAE that
pitches the psalm following it (ADR-0017), so they are the last thing that could
ever be cut. Initium, Responsorium breve, Versiculus, Antiphona ad Magnificat,
Pater noster, Oratio, Conclusio, the marian antiphon and the Ordo page are
likewise unchanged.

Consequences: a compact build gets its own stem `<feast>-kurzfassung`, hence its
own staged folder and PDF names, so it cannot wipe the full build (`stage()`
wipes its target folder); combined with a draft the stem is
`<feast>-kurzfassung-entwurf-<yyyy-mm-dd-hhmm>`, since a compact draft is the
likeliest thing to send a reviewing priest. The field travels inside a `Bündel`
(ADR-0019) like `draft:` does, and is off by default, so `compact: false` is
never written to a file. Measured on St. Lambert: **28 pages against 36**, the
imposition unaffected — the booklet already pads with ornament pages to a
multiple of four. Less than the halving one might expect from dropping 56 of 79
scores, because a text verse still costs two lines plus its German.

## The canticle's two-verse system

The systems are **generated once and committed** to
`chant/magnificat/kurzfassung/<tonus>.gabc` by `libellus magnificat-systems`,
mirroring how `export-form-data` maintains the form's data island. The two
verses' text never varies, so the placement is decided once and can be read off
the page instead of recomputed per build — ADR-0010's reasoning for a hand-kept
incipit table, applied again. `--check` compares the committed files against
freshly built ones, and one tone in live use is checked by the test suite.

- **The layout uses gabc's translation slot for verse 2.** `Ma[Et](f)` sets „Et"
  under „Ma"; a syllable may have notes and no lyric, and `r` after a pitch is a
  hollow note (punctum cavum). The line is set upright rather than in gregorio's
  italic translation style, because it is sung Latin and not a translation.
- **`\GreWriteTranslation` is patched to reserve the second line's width.**
  Gregorio typesets a translation in an `\hbox to 0pt` (gregoriotex-main.tex), so
  it claims no width at all, while the spacing engine budgets each syllable from
  `\wd\gre@box@syllabletext` — the *lyric's* width. A second line wider than the
  lyric above it therefore prints straight into its neighbour: „sul-" over „tá-",
  „De-" over „o", in every tone. The preamble redefinition pads the syllable by
  the overhang, using the width the same macro's centering branch already reads.
  Only scores carrying a translation are affected, which here means this one.
  Four other routes were tried and measured first, all failing because none of
  them touches that zero-width box: padding the lyric with `\hphantom` or an
  `\hspace`/`\makebox` in a `<v>` verbatim (emitted but never measured), widening
  `intersyllablespacenotes` (moves the notes, not the text — and made the
  overlaps worse), setting the line a size down (2.8pt → 2.0pt, still colliding),
  and swapping the verses so the longer one governed the lyric line (collided the
  other way round, 5.1pt).
- **Verified at glyph level, not by eye.** `pdftotext` merges glyphs that touch
  into one word, so a word-level overlap check reports nothing and a 4pt collision
  passes as clean — which it did here, twice. The check that works reads character
  boxes (`pdfplumber`), ignores the chant font (neumes legitimately share space)
  and allows 1.2pt for real kerning pairs like „Te". It reports **0 collisions
  across all 33 tones**; before the patch, 29 of 29 systems collided.
- **`useOpenNotes` comes from jgabc.** The engine already draws the reciting
  notes a verse puts no syllable on as hollow, with the Liber's brace over them;
  our wrapper had it switched off. `verses --open-notes` turns it on, used only
  here — ordinary booklet verses stay closed, because a reciting note somebody
  sings is not hollow.
- **Placement is a longest-common-subsequence over the note pitches**, since
  both verses realize one formula and verse 1's notes are a subsequence of the
  complete verse's. Ties resolve towards the earlier slot, so verse 1's
  syllables sit at the head of a reciting run as the Liber prints them. A
  syllable that finds no place is a hard error rather than a guess.
- **`\gwiden` (preamble) adds the width a wider second line needs**, because
  gregorio sizes a syllable by its lyric alone. Word spacing is per line: a
  space outside the syllable is what gregorio reads to end a word above, while
  the line beneath is typeset from the bracket and carries its own — the two
  verses do not break their words in the same places („á-ni-ma" against
  „in De-o").
- **Four of the 33 tones get no system, deliberately** (2D, 8G, 8G\*, 8c). In
  every one of the ten tones whose shortened mediant differs at all, the
  *termination* is identical; the divergence is confined to the mediant, and it
  comes in two kinds. For six of them — tone 7's five endings and peregrinus —
  only the mediant's **final note** differs (verse 1 ends „cat" on `i.` where
  verse 2 has `j.`); those two notes stand side by side at the end of the line,
  each under its own verse's last syllable, and the tone collapses like any
  other. For the remaining four the **intonation** itself differs: 8G's
  `g hg gj j j.` against `g h j j…`, 2D's `e fe eh h h.` against `e f h h…` —
  compound neumes where the complete verse has plain ones. A merged line would
  there alternate between the verses note by note and read as neither, so those
  notate both verses in full; the absence of the file is that decision, and the
  defect is fixed either way. („Festive first verse" was the first explanation
  offered for all ten and is right only for these four.)

Consequence: the committed system files call `\gwiden`, so they compile inside
this booklet (or any file defining it) rather than standalone — they are
feature-specific assets, not library chants, and the form's data island
deliberately does not offer them as choosable chant paths.

# ADR-0012: Public, multi-parish, multi-locale expansion — scope, hosting, and copyright approach

Date: 2026-07-23
Status: accepted

## Context

Prompted by comparing vesper against two similar-looking projects during a
grilling session: **Breviarium Gregorianum**
(breviariumgregorianum.com/about.php — an aggregation/display project
covering the complete 1962 Divine Office by rendering others' existing GABC
transcriptions, no PDF/LaTeX output) and **Vespero Generator /
gregorian-booklets** (gitlab.io/vespers — PDF Vespers booklets for one
French parish, Temporal + Sanctoral cycles, built with MkDocs).

Before this session, vesper was implicitly single-tenant (Bremen only),
German-only, and permanently private (Non-goals: "Making the repo public...
they derive from the copyrighted Einheitsübersetzung"), with the
Non-goals list also ruling out any "Hosted web service / server GUI".
"Eventually public" was already noted as the stated intent as of
2026-07-22, but blocked and undesigned.

This session established that the intent is broader than "eventually
public": Omar wants other parishes able to use vesper for their own
Vespers, English/French alongside German, and — longer-term, undesigned,
but explicitly *inside this same project* — Old Rite Mass booklets after
the Office roadmap.

## Decisions

1. **Commons stay a form-level convenience, not a schema/pipeline
   concept.** Selecting a Common (e.g. "of Martyrs") autofills known
   fields into an otherwise still-flat, self-contained feast YAML, which
   the author reviews/edits normally — no commons/include mechanism in
   the schema, resolver, or skeletons. This reactivates the existing
   "calendar-aware picker" future idea (HANDOFF.md, 2026-07-21) rather
   than introducing a new mechanism; the Non-goals line "Commons
   include/inheritance mechanism in the feast YAML" still holds exactly
   as scoped (no mechanism in the *data model*) and is not reversed by
   this.

2. **Tenancy: not single-tenant.** Priority order for 2026: (1)
   public-facing hosting, (2) multi-locale support (English, French), (3)
   accommodating other parishes' own liturgical/ordo quirks (e.g.
   romanum-cum-precibus-style local accommodations) — priority 3 is real
   but explicitly low/non-urgent, not designed now.

3. **German-copyright blocker resolved by splitting the default.** The
   public-facing default German psalter switches to a public-domain
   translation (candidate: Allioli-Arndt); the existing Einheitsübersetzung
   variants (`de-eu1980`, `de-eu2016`, ADR-0008) remain available only
   behind a private/authenticated path (e.g. for Bremen specifically). The
   existing `de-<versio>.yaml` variant mechanism already supports this
   without schema changes — it is a question of which variant is
   public-servable vs. gated, decided per deployment, not a new format.
   English/French translations are not expected to hit this problem
   (candidates: Douay-Rheims for English, a public-domain French
   translation such as Crampon — both plausibly public domain, unlike
   every EÜ revision).

4. **Public hosting: publish the tool itself** (form + templates + schema
   + Docker image) as an open-source artifact, with a **tiered,
   permanently-coexisting build-trigger backend** — not one tier
   replacing another:
   - **Tier B (default):** a small serverless function holding one shared
     credential triggers the pinned GitHub Actions build on behalf of
     anonymous visitors — "fill the form, hit enter, get a PDF," no login
     required. Ships from day one with basic abuse protection (per-IP/
     session rate limiting), since unlike tiers A/C nothing else polices
     abuse on this credential.
   - **Tier A (fallback, always available):** GitHub OAuth device-flow
     login; the visitor's own token fires `workflow_dispatch` directly —
     zero shared secret, GitHub's own per-user quota applies. This tier
     alone never violated the old "no hosted service" stance (see
     Non-goals reversal below) — it uses GitHub's infrastructure, not a
     service vesper operates.
   - **Tier C (optional):** on-demand serverless containers (e.g. Cloud
     Run, Fly.io) running the same pinned LaTeX/Gregorio image, streaming
     the PDF back directly — pursued only if a genuinely free tier covers
     it.
   - **Reversal, scoped precisely:** ADR-0006 rejected "a proxy/worker we
     run" for the form's data-fetching problem, citing "hosted services...
     die with their first unattended failure," and the Non-goals list
     accordingly named "Hosted web service / server GUI" outright. That
     reasoning still holds for the data-fetching problem (a
     zero-infrastructure equivalent existed there: public static files via
     raw.githubusercontent.com). No such equivalent exists for triggering
     builds on behalf of anonymous public users, so Tier B is a deliberate,
     narrower reversal — scoped to exactly the one function that needs a
     standing credential — not a general "we run servers now" stance.
     Tier A's permanent availability means the project is never
     *dependent* on the hosted piece: if B or C's infrastructure ever
     dies or bit-rots, A still works with zero standing infrastructure.

5. **Public credits/sources page at launch.** The existing internal
   provenance tracking (`PROVENANCE.md`, per-source credit notes in
   HANDOFF.md) gets restated as a public "Sources & Credits" page —
   GregoBase attribution, jgabc's Unlicense notice, and the chosen
   public-domain psalter's credit — mirroring the practice of both
   comparison projects (Breviarium Gregorianum's About page, Vespero
   Generator's References section).

## Considered / rejected

- **Aggregation-only model** (à la Breviarium Gregorianum — rendering
  others' transcriptions rather than generating any content): not
  adopted as a general strategy. Vesper already sources antiphons/hymns/
  responsories externally (GregoBase) the same way; the one place it
  generates content (psalm/canticle tone pointing via the vendored jgabc
  engine) is already hardened (sha-verified vendoring, golden fixtures
  checked against hand transcriptions and sung ground truth). No
  architecture change follows from this comparison.
- **Designing Mass support now:** rejected as premature/speculative;
  revisit once the Hours roadmap (Compline → Little Hours → Lauds) is
  done. Mass stays *inside this project* when it happens, not a separate
  one.
- **Designing for other parishes' idiosyncratic ordo variants now:**
  rejected given its explicit priority-3/low-urgency status; revisit only
  if/when parishes actually request it.

## Consequences

- Schema/resolver/skeletons are unchanged by this ADR — commons and
  locale expansion are UI/content/hosting concerns here, not pipeline
  redesigns. Follow-on ADRs are needed once EN/FR translation file
  conventions and the specific public-domain German psalter are chosen
  and implemented.
- The project's privacy stance splits in two: the tool/code + public-
  domain content becomes publishable; EÜ-derived content stays gated.
  Implementation specifics (which repo(s), what "authenticated path"
  means concretely) are left to a follow-on ADR once this work starts.
- A new operational responsibility appears for the first time: abuse
  monitoring/credential rotation for the Tier B serverless function —
  previously the project had zero standing infrastructure. This is a
  deliberate, scoped exception, not a reversal of the general
  no-server-to-babysit philosophy (Tier A remains the infrastructure-free
  fallback).
- `HANDOFF.md`'s Non-goals section and Hours-expansion roadmap are updated
  alongside this ADR to reflect the corrected priority order and the two
  reversed items.

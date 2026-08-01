# ADR-0007: Psalter German from the Einheitsübersetzung 1980, re-cut to Vulgate verses

Date: 2026-07-22
Status: accepted
Amended: 2026-07-22 — the hand-made Pss 109–112 + Magnificat turned out
to be EÜ **2016**, not 1980; the fidelity gate below is therefore a
documented version-difference report, and translations became selectable
per-psalm variant files (see ADR-0008).

## Context

Every psalm the booklets render needs interlinear German per Vulgate
verse (`chant/psalmi/<n>/de.yaml`); only Pss 109–112 + Magnificat exist
(hand-made). The full psalter (all 150) unblocks any feast. The EÜ
numbers psalms and verses the Hebrew way, counts superscriptions as
verses, and divides verses differently from the Clementine text the
schola sings.

## Decision

Source: the **Einheitsübersetzung 1980** (the ecumenical psalter the
German Stundenbuch uses — deliberately not the 2016 revision), scraped
from the Quadro-Bibel 5.0 mirror (bibel.github.io/EUe). Pipeline: a
one-off provenance-documented script maps Hebrew→Vulgate psalm numbers,
drops superscription verses, and aligns verses **by count** against the
vendored Clementine psalter; count-mismatched psalms are re-cut
editorially (agent work, reviewed, following the 109–112 style); the
fidelity gate is reproducing the existing hand-made files. Output stays
committed, hand-fixable per-psalm `de.yaml`, Vulgate numbering. Psalms
only — canticles are added per-Hour when the beyond-Vespers roadmap
item needs them.

## Consequences

- ~2,500 more EÜ-derived verses in the repo: the private-repo/licensing
  constraint (see ADR-0006's license boundary) becomes permanent unless
  the German is ever relicensed or replaced.
- The re-cut convention (Vulgate boundaries, no superscriptions) is now
  load-bearing data format, not just a habit of four psalms.

# ADR-0006: Chant/Bible data as a public static-API repo; no live GregoBase, no servers

Date: 2026-07-22
Status: accepted
Amended: 2026-08-01 — the "only public-domain/CC0 content ever enters the public
repo" rule below has exactly one recorded exception: the gilded back-cover border
tiles (`src/libellus/images/borders/`, ADR-0014) are derived crops of a
commercial product photograph of a gold gallery frame, and they ship in the
public repository and the published wheel. Omar's call, made knowingly rather
than overlooked, treating it as stock imagery. Recorded in `CREDITS.md`, which
also names the `pgfornament` vector border (ADR-0013) as the drop-in alternative
that bundles no pixels at all. The rule otherwise stands, and is what keeps the
Einheitsübersetzung out (ADR-0023/0024).

## Context

The form needs two vocabulary-heavy data sources: the Clementine Bible
(capitulum picker) and the GregoBase antiphon database (search + preview +
tone preselection). Neither fits ADR-0003's single self-contained HTML file
(~5 MB + ~5–10 MB). Querying gregobase.selapa.net live from the form is
impossible: its responses carry no `Access-Control-Allow-Origin` header, so
browsers block reading them from any web page (verified 2026-07-22); only a
server-side proxy could bridge that, and hosted services are a documented
non-goal (they die with their first unattended failure). This repo is
private (Einheitsübersetzung-derived German), so its own raw URLs cannot
serve the form either.

## Decision

A **second, public repo** (`OmarEjjeh/vesper-chant-data`) holds the data,
structured as a **static API** so the form never downloads the whole
database:

- a compact search index (chant id, incipit, mode, office-part, derived
  tonus) fetched once per session, and
- one small file per chant (its GABC), fetched only on selection;
- Clementine Bible sharded per book/chapter the same way.

`raw.githubusercontent.com` is the "server": it sends
`Access-Control-Allow-Origin: *` and a 5-minute cache, and a `file://`-
opened form can fetch from it (both verified 2026-07-22). A libellus
command regenerates the data files; publishing is a push to the public
repo. The same files under `form/daten/` beside the form act as the
offline fallback, loaded via classic `<script src>` (CORS-free over
`file://`); missing data degrades the affected panels with a German hint,
never the core form.

**License boundary, hard rule: only public-domain/CC0 content ever enters
the public repo** (GregoBase is CC0, the Clementine text is public
domain). The Einheitsübersetzung German — the reason this repo is
private — stays in the private repo and the embedded data island.

## Considered options

- Live GregoBase queries (rejected: CORS, see Context; also
  `usage.php?id=an` is a multi-megabyte list — a local index is needed for
  search-as-you-type regardless).
- Upstream PR adding CORS to GregoBase (rejected by the maintainer of
  this repo: no upstream work).
- A proxy/worker we run (rejected: hosted-service non-goal, two failure
  points, undebuggable by successors).
- Embedding everything in the form HTML (rejected: 15+ MB form, giant
  diffs, slow `export-form-data` rewrites).

## Consequences

- A second repo to keep in sync (one refresh command + push); bus-factor
  handling joins the existing repo-succession roadmap item.
- The form gains network behavior: online = fresh hosted data, offline =
  `form/daten/` fallback, neither = graceful German degradation.
- GregoBase freshness is a rerun of the refresh command, not a live view.

# ADR-0023: Public release — three repositories, 0BSD, and a deliberate PyPI release

Date: 2026-08-01
Status: accepted

## Context

ADR-0012 established that the tool itself should become public while the
Einheitsübersetzung-derived German stays gated, and named a Docker image as the
distributable. It left the mechanics undesigned: which repository, under what
licence, published how.

Three facts settled the shape of the answer.

**The repository could not simply be made public.** 16 of its 111 commits touch
the 155 Einheitsübersetzung files, so flipping visibility would expose them in
history even after deletion at HEAD. Publishing this repository would have meant
a `git filter-repo` pass over the whole history, an irreversible rewrite of the
only working copy, weeks before the St. Lambert booklet was due.

**A wheel built from the repository as it stood was empty of content.** Every
asset — `template/`, `chant/`, the psalm-tone engine — lived outside
`src/libellus/`, and every path resolved against `Path.cwd()`. `pip install
libellus` produced a command that could not build anything outside a checkout.
See ADR-0024.

**Not everything in the tree is publishable.** Besides the psalter,
`scripts/psalter-german/fidelity-report.md` quoted the Einheitsübersetzung
verbatim across 127 lines, and the working notes named people and quoted their
correspondence.

## Decisions

1. **Three repositories, and this one starts fresh.**

   | repository | visibility | contents |
   |---|---|---|
   | `libellus` | public | the tool, its bundled assets, `feasts/`, `images/`, `docs/` |
   | `psalter-eu` | private | the 155 Einheitsübersetzung files and the tooling that made them |
   | `vesper` | private, retained | the 111-commit archive and the working notes |

   The public repository begins with a single commit rather than carrying
   history, which is what makes the copyright problem disappear without a
   rewrite: there is no history to purge. Nothing is lost, because the old
   repository is kept private forever as the archive. What the discarded commit
   messages recorded survives in `CHANGELOG.md`, generated from them before the
   move.

   The private psalter is checked out into `psalter/`, which the public
   repository gitignores. Its tooling lives in `psalter/tools/` — including the
   fidelity report and the scrape tests, which quote the Einheitsübersetzung and
   therefore belong with it rather than with the tool.

2. **Jujutsu is dropped in the same move.** The colocated `.git` already held
   everything, so this cost nothing but documentation. One tool, one mental
   model, and `cz bump` makes an ordinary git commit and tag with no
   reconciliation step.

3. **0BSD.** The most permissive OSI-approved licence: do anything, no
   attribution, no notice to carry. Deliberately *not* MIT, which obliges every
   copy to reproduce a copyright notice; and deliberately a licence grant rather
   than a public-domain dedication, because German law does not permit an author
   to waive copyright, which makes CC0 or the Unlicense shakier here than a
   licence that simply demands nothing.

   A licence covers only what is the author's to license, so `CREDITS.md`
   states, per asset class, what 0BSD does and does not reach: GregoBase's CC0
   chant, the public-domain Clementine text, jgabc's Unlicense engine, the
   gilded border tiles, the hymn translations, and the Einheitsübersetzung that
   is absent entirely. This also discharges ADR-0012's decision 5.

4. **Versioning: one repository, one version.** `commitizen` derives the version
   and changelog from the Conventional Commit messages already in use
   (`version_provider = "pep621"`, so `project.version` is the single copy).
   Content-only commits under `feasts/`, `images/` or `psalter/` bump the
   version like any other; filtering by scope would need a custom provider to
   buy nothing, since at `0.x` no bump is expensive.

   `major_version_zero = true` while the feast-spec format settles: a breaking
   change bumps the minor rather than reaching 1.0.0. Graduating to v1.0.0 is
   itself a breaking-change commit that removes this setting, as commitizen's
   own documentation prescribes.

5. **Releasing is local and deliberate; CI only publishes.** `cz bump` is run by
   hand — it writes the version, regenerates the changelog, commits and tags —
   and pushing the tag is what triggers `release.yml`. No release can happen by
   merging.

   This is the only one of the three plausible designs needing no standing
   secret. A tag created by CI's own `GITHUB_TOKEN` does not trigger other
   workflows, so any design where CI tags and a second workflow publishes
   requires a PAT or deploy key; and a bump commit pushed back to a protected
   `main` requires the same. Here the tag is pushed by a person, so the
   tag-triggered workflow fires, and every mistake is recoverable locally before
   anything reaches PyPI — which matters, because a published release cannot be
   retracted, only yanked.

   Publication uses PyPI Trusted Publishing (OIDC), so no API token is stored
   anywhere. The publisher is registered against this repository *and*
   `release.yml`'s filename; renaming that file breaks publishing.

6. **The release gate is a booklet built from the installed wheel.** `ci.yml`
   runs the suite and asserts the artifacts carry no `de-eu*` and no `psalter/`.
   `release.yml` additionally installs the built wheel into a clean environment,
   in a directory that is not a checkout, and sets a complete booklet from it.
   That is the only check that can catch a wheel missing package data — the
   precise risk ADR-0024 introduces, and one that a green test suite run inside
   a checkout cannot see.

   The gate uses a `latin_only` feast, because no Psalter ships with libellus and
   none is available in CI. That is what ADR-0025 exists for.

## Considered / rejected

- **Rewriting history and publishing this repository** (`git filter-repo` over
  15 commits, then flip visibility): rejected. An irreversible rewrite of the
  only working copy, on the critical path to a booklet due in seven weeks, to
  gain a commit history that the changelog preserves in readable form anyway.
- **Keeping the repository private and publishing only the package:** viable —
  Trusted Publishing works from a private repository and the sdist *is* the
  source — but a 0BSD package whose users cannot see, fork or file issues
  against its source defeats the point of the licence.
- **Publishing the tool only, with all Bremen content private:** rejected. The
  worked feast specs are the single most useful thing for someone starting out,
  and they carry no copyright problem once the psalter is external.
- **MIT:** rejected as less permissive; see decision 3.
- **CI bumping the version** (on dispatch or on every push to `main`): rejected;
  see decision 5. Continuous releasing would also ship a release for every
  liturgical text correction, since decision 4 makes content commits bump.

## Consequences

- Bremen's working copy needs two clones: `libellus`, and `psalter-eu` into
  `psalter/`. A checkout without the psalter builds nothing but `latin_only`
  feasts — which is the same position a stranger is in, so the limitation is
  visible rather than latent.
- The committed feast specs cannot be built by anyone without a German psalter.
  The README says so. The real fix is a public-domain German psalter, tracked as
  an issue and the intended long-term default (ADR-0012 names Allioli-Arndt).
- The data island's `psalmi_cum_de` records which psalms have German, which now
  depends on the Psalter a working copy happens to have. Its freshness gate
  therefore skips where no Psalter exists, and protects whoever regenerates the
  island — the person who has one.
- The gilded border tiles ship in the wheel. They are derived crops of a
  commercial product photograph, treated as stock imagery: a deliberate,
  recorded exception to ADR-0006's rule that only public-domain or CC0 content
  enters the public repository. See that ADR's amendment and `CREDITS.md`.
- `HANDOFF.md`, the correspondence and the spotcheck HTML are gitignored and
  stay in the archive. Where a thread settled something load-bearing, the
  decision is restated in `docs/adr/` or `CREDITS.md`, attributed by role.

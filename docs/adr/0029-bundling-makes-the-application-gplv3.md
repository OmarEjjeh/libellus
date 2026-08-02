# ADR-0029: Bundling the toolchain makes the distributed application GPLv3; the sources stay 0BSD

Date: 2026-08-01
Status: superseded in part by ADR-0031 (2026-08-02)
Scopes: ADR-0023 decision 3.

> **Superseded:** decision 2 below is reversed. The application is built on
> **TeXlyre-BusyTeX** and the distributed artifact is **AGPL-3.0-or-later**, not
> GPLv3. Decisions 1 and 3 stand — the sources stay 0BSD, and `CREDITS.md`
> carries the bundle section — with "GPLv3" read as "AGPL-3.0-or-later"
> throughout.
>
> Note what did *not* happen: upstream `busytex` was never compared. ADR-0031
> sets this argument aside rather than refuting it, and records the experiment
> that would reopen it.

## Context

ADR-0023 chose 0BSD deliberately and for a stated reason: the most permissive
OSI-approved licence, no attribution, **no notice to carry** — explicitly not
MIT, because MIT obliges every copy to reproduce a copyright notice.

That works today because of a licensing fact that is easy to miss: libellus
merely *invokes* `lualatex` and `gregorio`, which the user installed themselves.
That is use, not distribution, so no copyleft obligation attaches to anything.

ADR-0026 changes it. The moment the toolchain ships inside the application, the
application distributes:

- **`gregorio` and GregorioTeX — GPLv3**, per the project's own statement.
- **LuaTeX — GPLv2 or later.**

A distributed artifact containing those is a combined work, so the artifact must
be GPL-compatible. This is a consequence of *bundling*, not of WebAssembly and
not of TypeScript — the same obligation would arise from shipping native binaries
in an installer.

## Decisions

1. **The libellus sources stay 0BSD; the distributed application is GPLv3.**
   0BSD is one-way compatible with the GPL, so nothing in ADR-0023 needs
   reversing — it needs **scoping**. 0BSD covers what is ours to license; GPLv3
   covers the bundle. Anyone may still take a component out of the source tree
   under 0BSD with no notice to carry, which is what ADR-0023 was actually
   protecting.

2. **The copyleft ceiling is GPLv3, so build on upstream `busytex` or our own
   wrapper — not on TeXlyre-BusyTeX.** TeXlyre-BusyTeX is **AGPL-3.0**, whose §13
   adds a Corresponding Source offer to anyone *interacting with the software over
   a network* — which a browser-served application does by definition. Upstream
   `busytex`'s own scripts are MIT (its binaries carry TeX Live's own licences,
   which are GPL but without §13).

   This is not free to choose. TeXlyre is the maintained fork and the one that
   actually ships TeX Live 2026 with LuaTeX; upstream busytex is the older,
   quieter base. Accepting AGPL for the application would be defensible — it
   would cost a source offer we would honour anyway, since the repository is
   public. The reason to prefer GPLv3 is narrower: §13 attaches obligations to
   *anyone who hosts the browser build*, including a parish that puts it on their
   own web space, and this project's whole ethos is not handing successors
   obligations they cannot evaluate.

3. **`CREDITS.md` gains a section for the bundle**, stating per component what
   licence reaches it: gregorio/GregorioTeX (GPLv3), LuaTeX and the texmf tree
   (GPL and various), EB Garamond / Charis SIL / XITS (OFL), greciliae, `pdf-lib`
   (MIT), Preact (MIT), and the Bundled data — GregoBase (CC0), the Clementine
   text (public domain), the public-domain Psalter. ADR-0023 already established
   that a licence covers only what is the author's to license and that
   `CREDITS.md` is where the boundary is drawn per asset class; this extends the
   same discipline to the toolchain.

## Consequences

- If a proprietary or non-copyleft distribution of the *application* is ever
  wanted, it cannot be done by relicensing our code — the toolchain would have to
  come back out of the bundle and be installed by the user, i.e. the pre-ADR-0026
  arrangement. Worth knowing before someone proposes it.
- The choice of WASM TeX base is now a licensing decision, not only a technical
  one, and TeXlyre is the more capable option. If the spike (ADR-0026) shows
  upstream busytex cannot produce a working LuaTeX + custom texmf build, the
  honest fallback is TeXlyre under AGPL-3.0 with the hosting consequence stated
  in `CREDITS.md` and the README — not a quiet reinterpretation of this ADR.
- This is not legal advice and no lawyer has looked at it. It is the conservative
  reading, chosen deliberately over the aggressive one (that a WASM module invoked
  at arm's length is mere aggregation).

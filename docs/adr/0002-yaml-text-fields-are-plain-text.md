# ADR-0002: YAML text fields are pure plain text — escape all LaTeX specials

Date: 2026-07-21
Status: accepted

## Context

The `|tex` Jinja2 filter escapes `&%#$_` but passes `\`, `{}`, `~` through
— the hole through which LaTeX entered the feast YAML, and the only
power-user escape hatch inside it. With ADR-0001's structured fields the
four legitimate uses of that hole are gone.

## Decision

All feast-YAML text fields get **plain-text semantics**: every LaTeX
special character (`\ { } ~ & % # $ _ ^`) is escaped or neutralized by the
rendering filter. A stray backslash from an author can never break the
build or inject LaTeX.

Typography the pass-through used to carry moves into the filter: literal
`℣.`/`℟.` marks are bound to their following word with a non-breaking
space automatically — authors type a plain space, as printed in the chant
books (same principle as ADR-0001's pause marks).

The power-user escape hatch moves **outside the YAML**: hand-authored
filler `.tex` pages, or editing the partials themselves.

Rejected: keeping the pass-through (preserves cryptic build failures for
successors); per-field `*_tex:` override variants (doubles the schema
surface, the form would have to preserve fields it can't render).

## Consequences

- `|tex` filter tightens; a migration pass over existing YAML fixtures.
- The static form can treat every text field as an ordinary
  input/textarea with no escaping logic at all.

// Loading and writing a feast spec without disturbing a byte the editor did
// not mean to change (#91 slice 1, ADR-0047).
//
// `eemeli/yaml` is used through its two layers at once, and the distinction is
// the whole design (ADR-0047). The **CST** — the token stream `Parser` emits — is lossless
// by construction: every space, comment and hand-made line break is a token, so
// stringifying it back is the identity function. The **AST** — the `Document`
// that `Composer` builds on top of those same tokens — is the typed view the
// editor reasons about, and is *not* lossless: its stringifier emits one space
// before a trailing comment, pads `[a, b]` to `[ a, b ]`, and re-folds every
// `>-` block scalar to its own line width. Measured against both shipped feast
// specs, a parse-and-restringify through the AST alone rewrites 135 and 298
// lines respectively while changing nothing anyone typed.
//
// So the bytes belong to the CST and the model belongs to the AST, and
// `keepSourceTokens` is what joins them: every parsed node carries a `srcToken`
// pointing back at the tokens it came from, which is what lets an edit be
// applied as a splice rather than as a re-emission of the whole file.

import { CST, Composer, Document, Parser, isScalar } from "yaml";

/** A feast spec as the editor holds it: its exact bytes, and its typed view. */
export interface FeastDocument {
  /**
   * The lossless token stream. Mutated in place by `setScalar` and written
   * back by `serialiseFeastDocument`.
   */
  readonly tokens: CST.Token[];
  /** The composed typed view. Its nodes carry `srcToken` links into `tokens`. */
  readonly spec: Document;
}

/**
 * Parse one feast spec.
 *
 * @throws if the source is not a single well-formed YAML document. A feast spec
 *   is always exactly one (`CONTEXT.md`, „Feast spec“), so a stream of several
 *   is a mistake worth naming rather than a first document worth guessing at.
 */
export function parseFeastDocument(source: string): FeastDocument {
  const tokens = Array.from(new Parser().parse(source));
  const composed = Array.from(new Composer({ keepSourceTokens: true }).compose(tokens));

  if (composed.length !== 1) {
    throw new Error(
      `Die Fest-Datei muss genau ein YAML-Dokument enthalten, gefunden: ${composed.length}`,
    );
  }
  const [spec] = composed;
  if (spec.errors.length > 0) {
    throw new Error(`Die Fest-Datei ist kein gültiges YAML: ${spec.errors[0].message}`);
  }

  return { tokens, spec };
}

/** The feast spec's bytes — identical to the source until something is set. */
export function serialiseFeastDocument(feast: FeastDocument): string {
  return feast.tokens.map((token) => CST.stringify(token)).join("");
}

/**
 * Replace the scalar at `path` with `value`, in the tokens and in the typed
 * view alike, leaving every other byte of the file where it was.
 *
 * @throws if `path` names no scalar that was actually parsed from the source.
 *   Adding a field the file does not have needs a token to be created rather
 *   than set, which is the field tree's problem (#91 slice 3), not this one.
 */
export function setScalar(
  feast: FeastDocument,
  path: readonly (string | number)[],
  value: string,
): void {
  const node = feast.spec.getIn(path, true);
  if (!isScalar(node) || !node.srcToken) {
    throw new Error(`In der Fest-Datei gibt es kein Feld ${path.join(".")}`);
  }

  // `afterKey` is load-bearing and fails quietly without: a block scalar's
  // content belongs one indent level deeper than the key it hangs off, and
  // omitting the flag writes it at the key's own indent instead — which still
  // stringifies, still looks plausible in a diff, and reparses to an empty
  // string with a YAML error nobody is reading at that point.
  CST.setScalarValue(node.srcToken, value, { afterKey: true });
  node.value = value;
}

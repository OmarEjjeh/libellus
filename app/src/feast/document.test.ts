import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { parseFeastDocument, serialiseFeastDocument, setScalar } from "./document";

const REPOSITORY_ROOT = new URL("../../../", import.meta.url);

const SHIPPED = ["2026-07-10-benedictus", "2026-09-18-lambertus"];

function shippedSpec(feast: string): string {
  return readFileSync(fileURLToPath(new URL(`feasts/${feast}.yaml`, REPOSITORY_ROOT)), "utf8");
}

/** Every formatting choice the AST stringifier is known to discard, in ten lines. */
const AWKWARD = `# a leading comment
titulus: Sanctus Lambertus  # two spaces before this one
psalter_de: [eu1980, eu2016]
antiphonae:
  - gabc: chant/ant/example.gabc
    de: >-  # a comment on the block scalar header
      Ein gefalteter Absatz, den der Verfasser von Hand an einer Stelle
      umgebrochen hat, die keine Zeilenbreite je wieder trifft.
    tonus: 8G
`;

describe("round-trip", () => {
  it.each(SHIPPED)("%s comes back byte for byte", (feast) => {
    const source = shippedSpec(feast);

    expect(serialiseFeastDocument(parseFeastDocument(source))).toBe(source);
  });

  it("keeps comments, comment spacing, flow style and hand folding", () => {
    // Each of these is a real loss in the AST stringifier: it emits one space
    // before a trailing comment, pads flow collections to `[ a, b ]`, and
    // re-folds block scalars to its own line width. Hence ADR-0047.
    expect(serialiseFeastDocument(parseFeastDocument(AWKWARD))).toBe(AWKWARD);
  });

  it("refuses a source that is not one YAML document", () => {
    expect(() => parseFeastDocument("titulus: [unclosed\n")).toThrow(/kein gültiges YAML/);
    expect(() => parseFeastDocument("a: 1\n---\nb: 2\n")).toThrow(/genau ein YAML-Dokument/);
  });
});

describe("setScalar", () => {
  it("rewrites one folded scalar and leaves every other byte alone", () => {
    const source = shippedSpec("2026-07-10-benedictus");
    const feast = parseFeastDocument(source);

    setScalar(feast, ["antiphonae", 0, "de"], "Ein kurzer, geänderter Text.");
    const written = serialiseFeastDocument(feast);

    expect(written).not.toBe(source);
    // The block scalar's header survives and its content is indented under it
    // — the failure mode `afterKey` exists to prevent produces a valid-looking
    // but under-indented line here, and an empty value on reparse.
    expect(written).toContain("    de: >-\n      Ein kurzer, geänderter Text.\n");
    expect(parseFeastDocument(written).spec.getIn(["antiphonae", 0, "de"])).toBe(
      "Ein kurzer, geänderter Text.",
    );

    // Everything before and after the edited antiphon is untouched.
    const [beforeOriginal] = source.split("antiphonae:");
    const [beforeWritten] = written.split("antiphonae:");
    expect(beforeWritten).toBe(beforeOriginal);
    expect(written.slice(written.indexOf("    psalmus: 109"))).toBe(
      source.slice(source.indexOf("    psalmus: 109")),
    );
  });

  it("rewrites a plain scalar in place", () => {
    const feast = parseFeastDocument(AWKWARD);

    setScalar(feast, ["antiphonae", 0, "tonus"], "1D");

    expect(serialiseFeastDocument(feast)).toBe(AWKWARD.replace("tonus: 8G", "tonus: 1D"));
  });

  it("refuses a path that names nothing in the parsed source", () => {
    const feast = parseFeastDocument(AWKWARD);

    expect(() => setScalar(feast, ["antiphonae", 0, "latin"], "x")).toThrow(/kein Feld/);
  });
});

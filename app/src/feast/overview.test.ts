import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { parseFeastDocument } from "./document";
import { overview } from "./overview";

function shipped(feast: string) {
  const path = fileURLToPath(new URL(`../../../feasts/${feast}.yaml`, import.meta.url));
  return parseFeastDocument(readFileSync(path, "utf8"));
}

describe("overview", () => {
  it("names the celebration", () => {
    expect(overview(shipped("2026-09-18-lambertus")).identity).toEqual([
      ["title", "Sancti Lamberti"],
      ["subtitle", "Episcopi et Martyris"],
      ["rank", "Semiduplex"],
      ["rite", "romanum-cum-precibus"],
      ["date", "2026-09-18"],
      ["vesperae", "I"],
    ]);
  });

  it("counts the repeating sections", () => {
    // A `YAMLSeq` is not an array, and answering 0 for every section looks
    // entirely believable on screen. Both shipped feasts, so a wrong answer
    // cannot hide behind an empty one.
    expect(overview(shipped("2026-09-18-lambertus")).sections).toEqual([
      ["antiphonae", 5],
      ["filler", 0],
    ]);
    expect(overview(shipped("2026-07-10-benedictus")).sections).toEqual([
      ["antiphonae", 4],
      ["filler", 2],
    ]);
  });

  it("omits an identifying field the spec does not carry", () => {
    const feast = parseFeastDocument("title: Sanctus Lambertus\nrank: Semiduplex\n");

    expect(overview(feast).identity).toEqual([
      ["title", "Sanctus Lambertus"],
      ["rank", "Semiduplex"],
    ]);
  });
});

// What can be said about a feast spec without editing it (#91 slice 1).
//
// A reader over the typed view rather than over the file: the panel renders
// this and knows nothing about YAML. It is deliberately thin — the field tree
// (slice 3) replaces it with real fields, and nothing here should grow to meet
// it halfway.

import { isSeq } from "yaml";

import type { FeastDocument } from "./document";

/** The top-level scalars that identify a celebration, per `CONTEXT.md`. */
const IDENTIFYING_FIELDS = ["title", "subtitle", "rank", "rite", "date", "vesperae"];

/** The repeating sections, counted rather than shown until there is a field tree. */
const COUNTED_FIELDS = ["antiphonae", "filler"];

export interface FeastOverview {
  /** The identifying scalars the spec actually carries, in the order above. */
  identity: [field: string, value: string][];
  /** How many entries each repeating section has. */
  sections: [field: string, entries: number][];
}

export function overview(feast: FeastDocument): FeastOverview {
  return {
    identity: IDENTIFYING_FIELDS.filter((field) => feast.spec.get(field) != null).map((field) => [
      field,
      String(feast.spec.get(field)),
    ]),
    // `Document.get` hands back a `YAMLSeq`, not an array — it is the typed
    // view's own node type, and `Array.isArray` says false to every one of
    // them. Counting them as zero is exactly the kind of plausible-looking
    // wrong answer that survives a glance at the screen.
    sections: COUNTED_FIELDS.map((field) => {
      const entries = feast.spec.get(field);
      return [field, isSeq(entries) ? entries.items.length : 0];
    }),
  };
}

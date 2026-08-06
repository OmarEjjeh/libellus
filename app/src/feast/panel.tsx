import { useEffect, useState } from "preact/hooks";

import { parseFeastDocument, serialiseFeastDocument } from "./document";
import { overview, type FeastOverview } from "./overview";
import { fetchFeastSpec } from "../workdir";

interface Inspection {
  overview: FeastOverview;
  /** Whether writing the spec back would reproduce the file exactly. */
  faithful: boolean;
}

function inspect(source: string): Inspection {
  const feast = parseFeastDocument(source);
  return { overview: overview(feast), faithful: serialiseFeastDocument(feast) === source };
}

/**
 * The feast spec, read-only (#91 slice 1).
 *
 * Deliberately no fields to type in yet: what this panel exists to prove is
 * that the application can take a hand-written, comment-carrying, priest-
 * reviewed YAML file apart into a typed model and put it back down without
 * moving a byte. Editing arrives once there is a store to hold the changes
 * (slice 2) and a field tree to make them in (slice 3).
 */
export function FeastPanel({ feast }: { feast: string }) {
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setInspection(null);
    setProblem(null);
    fetchFeastSpec(feast)
      .then((source) => current && setInspection(inspect(source)))
      .catch((error: Error) => current && setProblem(error.message));
    return () => {
      current = false;
    };
  }, [feast]);

  if (problem) return <p class="problem">{problem}</p>;
  if (!inspection) return <p class="quiet">Fest-Datei wird gelesen…</p>;

  return (
    <div class="feast">
      <dl>
        {inspection.overview.identity.map(([field, value]) => (
          <div key={field}>
            <dt>{field}</dt>
            <dd>{value}</dd>
          </div>
        ))}
        {inspection.overview.sections.map(([field, entries]) => (
          <div key={field}>
            <dt>{field}</dt>
            <dd class="quiet">{entries}</dd>
          </div>
        ))}
      </dl>
      <p class={inspection.faithful ? "faithful" : "problem"}>
        {inspection.faithful
          ? "Rückschreibprobe bestanden: Kommentare, Umbrüche und Schreibweise bleiben zeichengleich erhalten."
          : "Rückschreibprobe fehlgeschlagen: Zurückschreiben würde die Datei verändern."}
      </p>
    </div>
  );
}

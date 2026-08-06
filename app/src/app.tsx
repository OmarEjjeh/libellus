import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { FeastPanel } from "./feast/panel";
import { booted, build, onLog, readFile, type BuiltBooklet } from "./pipeline";
import { listFeasts } from "./workdir";

function Log({ lines }: { lines: string[] }) {
  const element = useRef<HTMLDivElement>(null);

  // Scroll on every message, as the plain-DOM page did — a build is minutes
  // long and the last line is the only one anyone is watching.
  useEffect(() => {
    if (element.current) element.current.scrollTop = element.current.scrollHeight;
  }, [lines]);

  return (
    <div id="log" ref={element}>
      {lines.map((line, index) => (
        <div key={index}>{line}</div>
      ))}
    </div>
  );
}

/** One finished PDF, with the object URL its link needs, made once. */
interface Download {
  stem: string;
  href: string;
}

function downloads(built: BuiltBooklet): Download[] {
  return [built, built.montage, built.montageDuplex].map((part) => ({
    stem: part.stem,
    href: URL.createObjectURL(new Blob([part.bytes as BlobPart], { type: "application/pdf" })),
  }));
}

export function App() {
  const [feasts, setFeasts] = useState<string[] | null>(null);
  const [selected, setSelected] = useState("");
  const [compact, setCompact] = useState(false);
  const [pipelineReady, setPipelineReady] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [results, setResults] = useState<Download[]>([]);
  const [building, setBuilding] = useState(false);

  useEffect(() => onLog((message) => setLines((previous) => [...previous, message])), []);

  useEffect(() => {
    listFeasts()
      .then((found) => {
        setFeasts(found);
        setSelected(found[0] ?? "");
      })
      .catch((error: Error) => setLines((previous) => [...previous, `FEHLER: ${error.message}`]));
  }, []);

  /** Build, and offer the three PDFs. The one path both the button and the
   *  harness go through, so neither can drift from the other. */
  const runBuild = useCallback(async (feast: string, wantsCompact: boolean) => {
    const built = await build(feast, wantsCompact);
    setResults((previous) => {
      for (const stale of previous) URL.revokeObjectURL(stale.href);
      return downloads(built);
    });
    return built;
  }, []);

  useEffect(() => {
    let current = true;
    booted.then(() => {
      if (!current) return;
      setPipelineReady(true);

      // Exposed so the verification harness can drive the page and take the
      // bytes back out without a download dialog — #57's definition of done
      // compares them against a native build, page by page. Plain arrays
      // because that is what survives Playwright's serialisation.
      globalThis.libellus = {
        build: async (feast, wantsCompact) => {
          const built = await runBuild(feast, wantsCompact);
          return {
            stem: built.stem,
            bytes: Array.from(built.bytes),
            montage: { stem: built.montage.stem, bytes: Array.from(built.montage.bytes) },
            montageDuplex: {
              stem: built.montageDuplex.stem,
              bytes: Array.from(built.montageDuplex.bytes),
            },
          };
        },
        readFile,
        ready: true,
      };
    });
    return () => {
      current = false;
    };
  }, [runBuild]);

  const hasFeasts = feasts !== null && feasts.length > 0;

  async function onBuild() {
    setBuilding(true);
    try {
      await runBuild(selected, compact);
    } catch (error) {
      setLines((previous) => [...previous, `FEHLER: ${error}`]);
      console.error(error);
    }
    setBuilding(false);
  }

  return (
    <>
      <h1>Libellus — das Heft entsteht in diesem Tab</h1>

      <p class="lead">
        Die vollständige Pipeline läuft hier im Browser: Fest-Datei einlesen, Noten setzen,
        Heft übersetzen. Keine TeX-Installation, kein Node, kein Server, der rechnet. Der
        erste Aufruf lädt rund 80 MB Werkzeugkette und legt sie ab; danach beginnt der Satz
        sofort.
      </p>

      {/* Only Electron exposes this bridge (`electron/preload.cjs`) — the browser
          host always serves its checkout's Working directory straight off disk,
          with no picker to offer (ADR-0035). */}
      {globalThis.libellusHost && (
        <p>
          <button
            onClick={async () => {
              const chosen = await globalThis.libellusHost?.openWorkingDirectory();
              // A full reload reboots the worker against the new Working
              // directory — simpler and safer than re-staging Pyodide's
              // filesystem mid-session.
              if (chosen) location.reload();
            }}
          >
            Arbeitsverzeichnis öffnen…
          </button>
        </p>
      )}

      {feasts !== null && !hasFeasts && <p>Kein Fest im Arbeitsverzeichnis.</p>}

      <p>
        <select
          id="feast"
          disabled={!hasFeasts}
          value={selected}
          onChange={(event) => setSelected((event.target as HTMLSelectElement).value)}
        >
          {(feasts ?? []).map((feast) => (
            <option key={feast} value={feast}>
              {feast}
            </option>
          ))}
        </select>
        <label>
          <input
            type="checkbox"
            id="compact"
            disabled={!hasFeasts}
            checked={compact}
            onChange={(event) => setCompact((event.target as HTMLInputElement).checked)}
          />{" "}
          Kurzfassung
        </label>
        <button id="build" disabled={!(pipelineReady && hasFeasts) || building} onClick={onBuild}>
          Heft bauen
        </button>
      </p>

      {selected && <FeastPanel feast={selected} />}

      <div id="results">
        {results.map((part) => (
          <a key={part.stem} href={part.href} download={`${part.stem}.pdf`}>
            {part.stem}.pdf herunterladen
          </a>
        ))}
      </div>

      <Log lines={lines} />
    </>
  );
}

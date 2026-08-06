// The Working directory as the page reaches it: over `fetch`, at the root-
// relative paths both hosts agree on — `app/serve.py` serves them from the
// checkout, `electron/main.mjs` maps them onto whatever folder the user opened
// (ADR-0035 decision 5). Nothing here can tell which host it is running on,
// which is the point.
//
// The two URLs below are deliberately built differently. `workdir.json` is the
// application's own manifest, generated per host and served beside it, so it
// hangs off the base the application was mounted under; a feast spec is the
// user's content and lives at `/feasts/…` on both hosts, whatever that base is.

/**
 * The feast ids in the Working directory, from the same `workdir.json` the
 * worker stages into Pyodide.
 */
export async function listFeasts(): Promise<string[]> {
  const response = await fetch(`${import.meta.env.BASE_URL}workdir.json`);
  if (!response.ok) {
    throw new Error(`Arbeitsverzeichnis nicht lesbar (${response.status})`);
  }
  const files: string[] = await response.json();
  return [
    ...new Set(
      files
        .filter((file) => file.startsWith("feasts/") && file.endsWith(".yaml"))
        .map((file) => file.slice("feasts/".length, -".yaml".length)),
    ),
  ].sort();
}

/** One feast spec, exactly as it sits on disk. */
export async function fetchFeastSpec(feast: string): Promise<string> {
  const response = await fetch(`/feasts/${feast}.yaml`);
  if (!response.ok) {
    throw new Error(`Fest-Datei nicht lesbar: feasts/${feast}.yaml (${response.status})`);
  }
  return response.text();
}

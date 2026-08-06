/** One finished PDF as it survives Playwright's serialisation: bytes as a plain array. */
interface SerialisedPart {
  stem: string;
  bytes: number[];
}

declare global {
  /**
   * The harness hook. `tests/test_browser_build.py` waits for `ready`, calls
   * `build`, and compares the bytes against a native build page by page (#57);
   * `readFile` is how the LaTeX log is fetched out for diagnosis. Its shape is
   * a contract with that test — do not change it without changing the test.
   */
  var libellus:
    | {
        build(
          feast: string,
          compact: boolean,
        ): Promise<SerialisedPart & { montage: SerialisedPart; montageDuplex: SerialisedPart }>;
        readFile(path: string): Promise<string>;
        ready: boolean;
      }
    | undefined;

  /**
   * The Electron shell's bridge (`electron/preload.cjs`), absent in a browser.
   * Its presence is what the Working-directory picker keys off (#70).
   */
  var libellusHost: { openWorkingDirectory(): Promise<string | null> } | undefined;
}

export {};

// Booklet imposition via pdf-lib, replacing `pdfjam` + `pdftk` (ADR-0026
// decision 4). Reimplements exactly what `compile.py`'s `subprocess_impose`
// does: 2-up landscape a4paper booklet imposition, then every second page
// rotated 180° for duplex printers without a binding-edge option.
//
// The booklet is already padded to a multiple of four (ADR-0018), so the
// signature math below has no partial-sheet case to handle.
//
// A4 landscape is *almost* exactly two A5 portraits side by side, but not
// quite: `preamble.tex.j2` sets a5paper, and LaTeX's built-in a5paper is
// 148mm wide — a rounding of true ISO A5 (148.5mm, exactly half of A4's
// 297mm). Stretching each source page to exactly fill its half therefore
// distorts it by ~0.3%, invisible side by side but not to a pixel diff. Fit
// and center instead, the same non-distorting choice `pdfpages` (what
// `pdfjam` wraps) makes.
//
// This is not called through `compile.py`'s synchronous `Runner` seam.
// pdf-lib returns a promise from every call, including ones that do no real
// I/O, and there is no way to unwrap that synchronously without
// `SharedArrayBuffer` (ADR-0034). It is instead the JS side of the separate,
// `async` `Imposer` seam (`set_imposer`), which Python awaits directly —
// `impose()` is a single top-level call, not something nested inside
// gregorio/LuaTeX's retry loop, so `pyodide.runPythonAsync` is all the
// bridging it needs.

import { PDFDocument, degrees } from "./vendor/pdf-lib.esm.min.js";

//: Points — 1/72": a4 landscape is a4 portrait's [width, height] swapped.
const A4_LANDSCAPE = [841.89, 595.28];

/**
 * The four page numbers (1-indexed) each physical sheet of a saddle-stitch
 * booklet carries, in the order a duplex-printed output PDF lists them: one
 * montage page per side, front sides and back sides alternating sheet by
 * sheet. Standard signature imposition — the same pairing `pdfjam --booklet`
 * produces.
 */
function signaturePairs(pageCount) {
  const sheets = pageCount / 4;
  const pairs = [];
  for (let sheet = 0; sheet < sheets; sheet++) {
    pairs.push([pageCount - 2 * sheet, 1 + 2 * sheet]); // front: outer, then inner-left
    pairs.push([2 + 2 * sheet, pageCount - 1 - 2 * sheet]); // back: inner-right, then outer
  }
  return pairs;
}

/** Draw `embeddedPage` scaled to fit and centered within one half-sheet box. */
function drawFitted(page, embeddedPage, boxX, boxWidth, boxHeight) {
  const scale = Math.min(boxWidth / embeddedPage.width, boxHeight / embeddedPage.height);
  const width = embeddedPage.width * scale;
  const height = embeddedPage.height * scale;
  page.drawPage(embeddedPage, {
    x: boxX + (boxWidth - width) / 2,
    y: (boxHeight - height) / 2,
    width,
    height,
  });
}

/**
 * 2-up landscape booklet imposition of a compiled booklet PDF, plus the
 * duplex-rotated variant.
 *
 * @param {Uint8Array} pdfBytes The compiled, un-imposed booklet.
 * @returns {Promise<{bookletBytes: Uint8Array, duplexBytes: Uint8Array}>}
 */
export async function imposeBooklet(pdfBytes) {
  const source = await PDFDocument.load(pdfBytes);
  const pageCount = source.getPageCount();
  if (pageCount % 4 !== 0) {
    // The template pads to a multiple of four (ADR-0018); compile.py checks
    // this too, so reaching here with a bad count means the two disagree.
    throw new Error(
      `Montage braucht eine durch 4 teilbare Seitenzahl, hat aber ${pageCount}.`
    );
  }

  const montage = await PDFDocument.create();
  const embedded = await montage.embedPages(source.getPages());
  const [width, height] = A4_LANDSCAPE;
  const half = width / 2;

  for (const [left, right] of signaturePairs(pageCount)) {
    const page = montage.addPage(A4_LANDSCAPE);
    drawFitted(page, embedded[left - 1], 0, half, height);
    drawFitted(page, embedded[right - 1], half, half, height);
  }
  const bookletBytes = await montage.save();

  // Rebuilt from the montage document's own pages rather than reusing its
  // bytes, because pdf-lib mutates page rotation on the PDFPage object, not
  // on already-saved bytes.
  const duplex = await PDFDocument.create();
  const copied = await duplex.copyPages(montage, montage.getPageIndices());
  copied.forEach((page, index) => {
    duplex.addPage(page);
    // Every second page is a sheet's back side; duplex printers without a
    // binding-edge option flip it upside down, so rotate to compensate.
    if (index % 2 === 1) page.setRotation(degrees(180));
  });
  const duplexBytes = await duplex.save();

  return { bookletBytes, duplexBytes };
}

/**
 * The JS side of `compile.py`'s `Imposer` seam: reads the compiled PDF out of
 * Pyodide's filesystem, imposes it, and writes both Montage outputs back —
 * from Python's side nothing has changed about where files are, exactly as
 * `engines.mjs`'s `runner` works for gregorio/LuaTeX.
 *
 * @param {*} pyodideFS Pyodide's `FS`, i.e. `pyodide.FS`.
 * @returns {(pdfPath: string) => Promise<[string, string]>} booklet and
 *   duplex paths, both siblings of `pdfPath` inside the staged folder.
 */
export function imposer(pyodideFS) {
  return async (pdfPath) => {
    const bytes = pyodideFS.readFile(pdfPath);
    const { bookletBytes, duplexBytes } = await imposeBooklet(bytes);
    const stem = pdfPath.replace(/\.pdf$/, "");
    const bookletPath = `${stem}-montage.pdf`;
    const duplexPath = `${stem}-montage-duplex.pdf`;
    pyodideFS.writeFile(bookletPath, bookletBytes);
    pyodideFS.writeFile(duplexPath, duplexBytes);
    return [bookletPath, duplexPath];
  };
}

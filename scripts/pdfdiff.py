#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdfium2", "pillow"]
# ///
"""Render two PDFs page by page and report pixel differences.

    uv run scripts/pdfdiff.py a.pdf b.pdf

Text comparison is not enough for this booklet: the chant is drawn from font
glyphs positioned by GregorioTeX, and a placement bug would leave the extracted
text identical.

Written for the WebAssembly spike (#43) to compare a ported build against a
native one; kept because #56 needs the same measurement to tell a cold rebuild
from the PDF that shipped.
"""

import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops

DPI = 150


def render(path: Path, page: int) -> Image.Image:
    doc = pdfium.PdfDocument(str(path))
    bitmap = doc[page].render(scale=DPI / 72)
    return bitmap.to_pil().convert("RGB")


def main() -> None:
    a_path, b_path = Path(sys.argv[1]), Path(sys.argv[2])
    a_doc, b_doc = pdfium.PdfDocument(str(a_path)), pdfium.PdfDocument(str(b_path))
    if len(a_doc) != len(b_doc):
        print(f"PAGE COUNT DIFFERS: {len(a_doc)} vs {len(b_doc)}")
        raise SystemExit(1)

    identical = 0
    worst: list[tuple[int, int, float]] = []
    for i in range(len(a_doc)):
        a, b = render(a_path, i), render(b_path, i)
        if a.size != b.size:
            print(f"page {i + 1}: SIZE DIFFERS {a.size} vs {b.size}")
            continue
        diff = ImageChops.difference(a, b)
        box = diff.getbbox()
        if box is None:
            identical += 1
        else:
            changed = sum(1 for px in diff.convert("L").getdata() if px > 8)
            total = a.size[0] * a.size[1]
            worst.append((i + 1, changed, 100 * changed / total))

    print(f"pages: {len(a_doc)}")
    print(f"pixel-identical pages: {identical}")
    if worst:
        print("pages with differences (page, changed px, % of page):")
        for page, changed, pct in sorted(worst, key=lambda t: -t[1])[:10]:
            print(f"  p{page:<3d} {changed:>9d}  {pct:6.3f}%")
        raise SystemExit(1)
    print("ALL PAGES PIXEL-IDENTICAL")


if __name__ == "__main__":
    main()

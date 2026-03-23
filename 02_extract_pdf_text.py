#!/usr/bin/env python3
"""
02_extract_pdf_text.py
Extract full text from every PDF in papers.json using PyMuPDF (fitz).
Updates the "pdf_text" field in-place (preserves all other data).

Re-runnable: skips papers that already have pdf_text (use --force to re-extract all).
"""

import json
import sys
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run:  pip install pymupdf")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "data" / "papers.json"


def extract_pdf_text(pdf_path: str) -> list[dict] | None:
    """
    Extract text per page from a PDF.
    Returns list of {"page": N, "text": "..."} or None on failure.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"    ✗ Could not open: {e}")
        return None

    pages = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        text = text.strip()
        if text:
            pages.append({"page": page_num, "text": text})
    doc.close()
    return pages if pages else None


def main():
    parser = argparse.ArgumentParser(description="Extract PDF text for papers.json")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-extract even if pdf_text already populated"
    )
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run 01_extract_zotero.py first.")
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        papers = json.load(f)

    total       = len(papers)
    has_pdf     = sum(1 for p in papers if p.get("has_pdf"))
    already_done = sum(1 for p in papers if p.get("pdf_text") is not None)

    print(f"Loaded {total} papers ({has_pdf} with PDF, {already_done} already extracted)")
    if args.force:
        print("  --force: re-extracting all PDFs")

    extracted = 0
    skipped   = 0
    failed    = 0

    for i, paper in enumerate(papers, start=1):
        citekey = paper.get("citekey") or paper.get("title", "")[:40]

        if not paper.get("has_pdf") or not paper.get("pdf_path"):
            continue

        if paper.get("pdf_text") is not None and not args.force:
            skipped += 1
            continue

        pdf_path = paper["pdf_path"]
        if not Path(pdf_path).exists():
            print(f"  [{i}/{total}] MISSING PDF: {citekey}")
            paper["has_pdf"] = False
            failed += 1
            continue

        print(f"  [{i}/{total}] Extracting: {citekey}", end=" ... ", flush=True)
        pages = extract_pdf_text(pdf_path)
        if pages:
            paper["pdf_text"] = pages
            n_pages = len(pages)
            n_chars = sum(len(p["text"]) for p in pages)
            print(f"✓ {n_pages} pages, {n_chars:,} chars")
            extracted += 1
        else:
            print("✗ no text extracted")
            paper["pdf_text"] = []
            failed += 1

    # Write back
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Done → {DATA_PATH}")
    print(f"  Extracted: {extracted}  |  Skipped (already done): {skipped}  |  Failed: {failed}")


if __name__ == "__main__":
    main()

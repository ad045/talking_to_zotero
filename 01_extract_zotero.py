#!/usr/bin/env python3
"""
01_extract_zotero.py
Extract all paper metadata, annotations, and notes from Zotero SQLite
for items in the 09_0_neuro_ai_thesis collection (and sub-collections).

Output: data/papers.json
Re-runnable: overwrites output cleanly each time.
"""

import sqlite3
import json
import re
import html
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ZOTERO_DB   = Path.home() / "Zotero" / "zotero.sqlite"
ROOT_COLLECTION_NAME = "09_0_neuro_ai_thesis"
OUTPUT_PATH = Path(__file__).parent / "data" / "papers.json"

# Annotation type IDs → human-readable names
ANNOTATION_TYPES = {
    1: "highlight",
    2: "note",
    3: "image",
    4: "ink",
    5: "underline",
    6: "freetext",
}

# Zotero item types we want as "papers" (not attachments, annotations, etc.)
PAPER_TYPES = {
    "journalArticle", "conferencePaper", "preprint",
    "bookSection", "book", "thesis", "report",
    "dataset", "computerProgram", "webpage", "document",
    "encyclopediaArticle", "magazineArticle",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from Zotero note HTML."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_descendant_collections(cur, root_name: str) -> list[int]:
    """Return IDs of root collection and all its sub-collections, recursively."""
    cur.execute("SELECT collectionID, collectionName, parentCollectionID FROM collections")
    all_cols = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    # find root
    root_id = next(
        (cid for cid, (name, _) in all_cols.items() if name == root_name), None
    )
    if root_id is None:
        raise ValueError(f"Collection '{root_name}' not found in Zotero database.")

    def _recurse(parent_id):
        result = [parent_id]
        for cid, (_, pid) in all_cols.items():
            if pid == parent_id:
                result.extend(_recurse(cid))
        return result

    ids = _recurse(root_id)
    print(f"  Collections in scope ({len(ids)}):")
    for cid in ids:
        print(f"    [{cid}] {all_cols[cid][0]}")
    return ids


def get_pdf_path(cur, item_key: str, raw_path: str, link_mode: int) -> str | None:
    """Resolve Zotero attachment path to an absolute filesystem path."""
    if link_mode in (0, 1):
        # Stored file: path is "storage:filename.pdf"
        filename = raw_path.replace("storage:", "")
        return str(Path.home() / "Zotero" / "storage" / item_key / filename)
    elif link_mode == 2:
        # Linked file: path is absolute (may start with "attachments:" on some setups)
        raw_path = raw_path.replace("attachments:", "")
        return raw_path
    # link_mode 3 = URL, not a local file
    return None


# ── Main extraction ───────────────────────────────────────────────────────────

def extract(db_path: Path, root_collection: str) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    collection_ids = get_descendant_collections(cur, root_collection)
    placeholders = ",".join("?" * len(collection_ids))

    # ── 1. Get all paper-type itemIDs in scope ────────────────────────────────
    cur.execute(f"""
        SELECT DISTINCT ci.itemID
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
        WHERE ci.collectionID IN ({placeholders})
          AND it.typeName IN ({",".join("?" * len(PAPER_TYPES))})
    """, collection_ids + list(PAPER_TYPES))
    paper_ids = [r[0] for r in cur.fetchall()]
    print(f"\n  Found {len(paper_ids)} papers.")

    # ── Helper: fetch a single scalar field for an item ──────────────────────
    def field_value(item_id, field_name):
        cur.execute("""
            SELECT idv.value
            FROM itemData id
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ? AND f.fieldName = ?
        """, (item_id, field_name))
        row = cur.fetchone()
        return row[0] if row else None

    papers = []
    for item_id in paper_ids:
        # ── Basic fields ──────────────────────────────────────────────────────
        cur.execute("""
            SELECT i.key, it.typeName
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE i.itemID = ?
        """, (item_id,))
        row = cur.fetchone()
        if not row:
            continue
        zotero_key, item_type = row["key"], row["typeName"]

        title    = field_value(item_id, "title") or ""
        abstract = field_value(item_id, "abstractNote") or ""
        doi      = field_value(item_id, "DOI") or ""
        url      = field_value(item_id, "url") or ""
        date     = field_value(item_id, "date") or ""
        citekey  = field_value(item_id, "citationKey") or ""
        pages    = field_value(item_id, "pages") or ""
        volume   = field_value(item_id, "volume") or ""
        issue    = field_value(item_id, "issue") or ""
        journal  = (field_value(item_id, "publicationTitle")
                    or field_value(item_id, "bookTitle")
                    or field_value(item_id, "proceedingsTitle")
                    or field_value(item_id, "university")
                    or "")
        journal_abbrev = field_value(item_id, "journalAbbreviation") or ""

        year = None
        if date:
            m = re.search(r"\b(19|20)\d{2}\b", date)
            if m:
                year = int(m.group())

        # ── Authors ───────────────────────────────────────────────────────────
        cur.execute("""
            SELECT c.firstName, c.lastName, ct.creatorType
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
        """, (item_id,))
        authors = [
            {"first": r["firstName"] or "", "last": r["lastName"] or "", "role": r["creatorType"]}
            for r in cur.fetchall()
        ]

        # ── Tags ──────────────────────────────────────────────────────────────
        cur.execute("""
            SELECT t.name FROM itemTags it2
            JOIN tags t ON it2.tagID = t.tagID
            WHERE it2.itemID = ?
        """, (item_id,))
        tags = [r[0] for r in cur.fetchall()]

        # ── Collections (names) this item belongs to ──────────────────────────
        cur.execute("""
            SELECT col.collectionName
            FROM collectionItems ci
            JOIN collections col ON ci.collectionID = col.collectionID
            WHERE ci.itemID = ?
        """, (item_id,))
        collections = [r[0] for r in cur.fetchall()]

        # ── Zotero notes ──────────────────────────────────────────────────────
        cur.execute("""
            SELECT n.note FROM itemNotes n
            JOIN items i ON n.itemID = i.itemID
            WHERE n.parentItemID = ?
        """, (item_id,))
        notes = [strip_html(r[0]) for r in cur.fetchall() if r[0]]

        # ── Attachments + annotations ─────────────────────────────────────────
        cur.execute("""
            SELECT i.itemID, i.key, att.path, att.linkMode, att.contentType
            FROM itemAttachments att
            JOIN items i ON att.itemID = i.itemID
            WHERE att.parentItemID = ? AND att.contentType = 'application/pdf'
            ORDER BY i.itemID
        """, (item_id,))
        attachments = cur.fetchall()

        pdf_path = None
        annotations = []
        for att in attachments:
            att_id, att_key, raw_path, link_mode, _ = (
                att["itemID"], att["key"], att["path"], att["linkMode"], att["contentType"]
            )
            resolved = get_pdf_path(cur, att_key, raw_path or "", link_mode)
            if resolved and pdf_path is None:
                pdf_path = resolved  # use first found PDF

            # Get annotations for this attachment
            cur.execute("""
                SELECT type, text, comment, color, pageLabel
                FROM itemAnnotations
                WHERE parentItemID = ?
                ORDER BY sortIndex
            """, (att_id,))
            for ann in cur.fetchall():
                ann_type, text, comment, color, page = (
                    ann["type"], ann["text"], ann["comment"],
                    ann["color"], ann["pageLabel"]
                )
                if text or comment:  # skip empty annotations
                    annotations.append({
                        "type_id":   ann_type,
                        "type_name": ANNOTATION_TYPES.get(ann_type, "unknown"),
                        "text":      text or "",
                        "comment":   comment or "",
                        "color":     color or "",
                        "page":      page or "",
                    })

        # ── Assemble paper record ─────────────────────────────────────────────
        paper = {
            "item_id":          item_id,
            "zotero_key":       zotero_key,
            "citekey":          citekey,
            "item_type":        item_type,
            "title":            title,
            "authors":          authors,
            "year":             year,
            "publication":      journal,
            "journal_abbrev":   journal_abbrev,
            "volume":           volume,
            "issue":            issue,
            "pages":            pages,
            "doi":              doi,
            "url":              url,
            "abstract":         abstract,
            "tags":             tags,
            "collections":      collections,
            "has_pdf":          pdf_path is not None,
            "pdf_path":         pdf_path,
            "annotation_count": len(annotations),
            "annotations":      annotations,
            "notes":            notes,
            # Populated by 02_extract_pdf_text.py
            "pdf_text":         None,
            # Populated by a future LLM enrichment script
            "llm_enrichment":   None,
        }
        papers.append(paper)

    conn.close()
    return papers


def main():
    print(f"Reading Zotero database: {ZOTERO_DB}")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    papers = extract(ZOTERO_DB, ROOT_COLLECTION_NAME)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    annotated   = sum(1 for p in papers if p["annotation_count"] > 0)
    has_pdf     = sum(1 for p in papers if p["has_pdf"])
    has_citekey = sum(1 for p in papers if p["citekey"])

    print(f"\n✓ Extracted {len(papers)} papers → {OUTPUT_PATH}")
    print(f"  With PDF:     {has_pdf}/{len(papers)}")
    print(f"  Annotated:    {annotated}/{len(papers)}")
    print(f"  Has citekey:  {has_citekey}/{len(papers)}")
    total_ann = sum(p["annotation_count"] for p in papers)
    print(f"  Total annotations: {total_ann}")


if __name__ == "__main__":
    main()

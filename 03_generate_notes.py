#!/usr/bin/env python3
"""
03_generate_notes.py
Generate Obsidian markdown notes from papers.json.

Creates:
  - One note per paper:   {VAULT}/papers/{citekey}.md
  - Index by title:       {VAULT}/_index/00_all_papers.md
  - Index by tag:         {VAULT}/_index/00_by_tag.md
  - Index by author:      {VAULT}/_index/00_by_author.md
  - Index by year:        {VAULT}/_index/00_by_year.md

Re-runnable: overwrites existing notes. Use --dry-run to preview without writing.

LLM enrichment hook: each note has a <!-- LLM_ENRICHMENT --> section that a future
script (04_enrich_llm.py) can populate with summary, key concepts, and connections.
The JSON field paper["llm_enrichment"] will hold that data once generated.
"""

import json
import re
import argparse
import textwrap
from pathlib import Path
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH  = Path(__file__).parent / "data" / "papers.json"
VAULT_PATH = Path.home() / "Documents/02_books/02_obsidian_neuroai_claude"
PAPERS_DIR = VAULT_PATH / "papers"
INDEX_DIR  = VAULT_PATH / "_index"

# Annotation color → short label (Zotero defaults; edit if you use a custom scheme)
COLOR_LABELS = {
    "#ffd400": "yellow",
    "#ff6666": "red",
    "#5fb236": "green",
    "#2ea8e5": "blue",
    "#a28ae5": "purple",
    "#e56eee": "magenta",
    "#f19837": "orange",
    "#aaaaaa": "gray",
}

# Minimum shared tags to create a wiki-link connection
MIN_SHARED_TAGS = 2

# Maximum characters of PDF text to embed in note (keeps files manageable)
# Set to None for unlimited
MAX_PDF_CHARS = 60_000


# ── Utilities ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Make a safe filename from arbitrary text."""
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:120]


def yaml_str(s: str) -> str:
    """Wrap a string in YAML double-quotes, escaping internal quotes."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def author_short(author: dict) -> str:
    last = author.get("last", "").strip()
    first = author.get("first", "").strip()
    if last and first:
        return f"{last}, {first[0]}."
    return last or first or "Unknown"


def author_full(author: dict) -> str:
    parts = [author.get("first", ""), author.get("last", "")]
    return " ".join(p for p in parts if p).strip()


def note_filename(paper: dict) -> str:
    """Return the .md filename for this paper (without directory)."""
    if paper.get("citekey"):
        return paper["citekey"] + ".md"
    # Fallback: sanitize title
    title = paper.get("title", f"item_{paper['item_id']}")
    return slugify(title) + ".md"


def wikilink(paper: dict) -> str:
    return "[[" + note_filename(paper).removesuffix(".md") + "]]"


def clean_tag(tag: str) -> str:
    """Convert a Zotero tag to a valid Obsidian tag (no spaces, no special chars)."""
    tag = tag.strip()
    # Remove emoji and other non-ASCII symbols before processing
    tag = re.sub(r"[^\x00-\x7F]+", "", tag).strip()
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"[^\w\-]", "", tag)
    tag = tag.strip("-")  # remove leading/trailing dashes left by emoji removal
    return tag.lower()


# ── Connection graph ──────────────────────────────────────────────────────────

def build_connections(papers: list[dict]) -> dict[int, list[dict]]:
    """
    For each paper, find related papers by:
    - shared tags (MIN_SHARED_TAGS or more)
    - shared authors (same last name)
    Returns dict: item_id → list of {paper, reason}
    """
    by_tag    = defaultdict(list)
    by_author = defaultdict(list)

    for p in papers:
        for tag in p.get("tags", []):
            by_tag[tag.lower()].append(p)
        for author in p.get("authors", []):
            key = author.get("last", "").lower().strip()
            if key:
                by_author[key].append(p)

    connections: dict[int, list[dict]] = defaultdict(list)
    already_added: set[tuple] = set()

    for p in papers:
        pid = p["item_id"]
        candidate_scores: dict[int, dict] = {}

        # Tag-based
        for tag in p.get("tags", []):
            for other in by_tag[tag.lower()]:
                oid = other["item_id"]
                if oid == pid:
                    continue
                if oid not in candidate_scores:
                    candidate_scores[oid] = {"paper": other, "shared_tags": [], "shared_authors": []}
                candidate_scores[oid]["shared_tags"].append(tag)

        # Author-based
        for author in p.get("authors", []):
            key = author.get("last", "").lower().strip()
            if not key:
                continue
            for other in by_author[key]:
                oid = other["item_id"]
                if oid == pid:
                    continue
                if oid not in candidate_scores:
                    candidate_scores[oid] = {"paper": other, "shared_tags": [], "shared_authors": []}
                author_name = author_full(author)
                if author_name not in candidate_scores[oid]["shared_authors"]:
                    candidate_scores[oid]["shared_authors"].append(author_name)

        for oid, info in candidate_scores.items():
            shared_tags    = info["shared_tags"]
            shared_authors = info["shared_authors"]
            if len(shared_tags) >= MIN_SHARED_TAGS or shared_authors:
                pair = (min(pid, oid), max(pid, oid))
                if pair not in already_added:
                    already_added.add(pair)
                    reasons = []
                    if shared_authors:
                        reasons.append(f"shared author(s): {', '.join(shared_authors)}")
                    if len(shared_tags) >= MIN_SHARED_TAGS:
                        reasons.append(f"shared tags: {', '.join(shared_tags[:5])}")
                    conn_entry = {"paper": info["paper"], "reason": "; ".join(reasons)}
                    connections[pid].append(conn_entry)
                    connections[oid].append({"paper": p, "reason": "; ".join(reasons)})

    return connections


# ── Note renderer ─────────────────────────────────────────────────────────────

def render_paper_note(paper: dict, connections: list[dict]) -> str:
    lines = []

    # ── YAML frontmatter ──────────────────────────────────────────────────────
    lines.append("---")
    lines.append(f"title: {yaml_str(paper.get('title', ''))}")

    authors_list = paper.get("authors", [])
    if authors_list:
        author_strs = [yaml_str(author_full(a)) for a in authors_list if a.get("last") or a.get("first")]
        lines.append(f"authors: [{', '.join(author_strs)}]")
    else:
        lines.append("authors: []")

    if paper.get("year"):
        lines.append(f"year: {paper['year']}")

    if paper.get("publication"):
        lines.append(f"journal: {yaml_str(paper['publication'])}")

    if paper.get("doi"):
        lines.append(f"doi: {yaml_str(paper['doi'])}")

    if paper.get("url"):
        lines.append(f"url: {yaml_str(paper['url'])}")

    if paper.get("citekey"):
        lines.append(f"citekey: {paper['citekey']}")

    tags_raw = [clean_tag(t) for t in paper.get("tags", []) if t.strip()]
    tags_raw = [t for t in tags_raw if t]
    if tags_raw:
        lines.append(f"tags: [{', '.join(tags_raw)}]")
    else:
        lines.append("tags: []")

    lines.append(f"item_type: {paper.get('item_type', '')}")
    lines.append(f"has_pdf: {str(paper.get('has_pdf', False)).lower()}")
    lines.append(f"annotation_count: {paper.get('annotation_count', 0)}")
    lines.append(f"zotero_key: {paper.get('zotero_key', '')}")

    if paper.get("collections"):
        cols = [yaml_str(c) for c in paper["collections"]]
        lines.append(f"collections: [{', '.join(cols)}]")

    lines.append("---")
    lines.append("")

    # ── Title ─────────────────────────────────────────────────────────────────
    title = paper.get("title") or "Untitled"
    lines.append(f"# {title}")
    lines.append("")

    # Author / year / journal line
    meta_parts = []
    if authors_list:
        if len(authors_list) == 1:
            meta_parts.append(author_short(authors_list[0]))
        elif len(authors_list) == 2:
            meta_parts.append(f"{author_short(authors_list[0])} & {author_short(authors_list[1])}")
        else:
            meta_parts.append(f"{author_short(authors_list[0])} et al.")
    if paper.get("year"):
        meta_parts.append(str(paper["year"]))
    if paper.get("publication"):
        meta_parts.append(f"*{paper['publication']}*")
    if meta_parts:
        lines.append(" · ".join(meta_parts))
        lines.append("")

    # DOI / URL
    links = []
    if paper.get("doi"):
        links.append(f"[DOI](https://doi.org/{paper['doi']})")
    if paper.get("url") and not paper.get("doi"):
        links.append(f"[URL]({paper['url']})")
    if links:
        lines.append(" | ".join(links))
        lines.append("")

    # ── Abstract ──────────────────────────────────────────────────────────────
    abstract = paper.get("abstract", "").strip()
    if abstract:
        lines.append("## Abstract")
        lines.append("")
        lines.append("> [!abstract]")
        for line in textwrap.wrap(abstract, width=100):
            lines.append(f"> {line}")
        lines.append("")

    # ── LLM enrichment block (placeholder for future 04_enrich_llm.py) ────────
    llm = paper.get("llm_enrichment")
    lines.append("## Summary")
    lines.append("")
    if llm and llm.get("summary"):
        lines.append(llm["summary"])
    else:
        lines.append("<!-- LLM_ENRICHMENT:summary -->")
        lines.append("*Not yet generated. Run `04_enrich_llm.py` to populate.*")
    lines.append("")

    if llm and llm.get("key_concepts"):
        lines.append("**Key concepts:** " + " · ".join(
            f"[[{c}]]" for c in llm["key_concepts"]
        ))
        lines.append("")

    # ── Annotations / Highlights ──────────────────────────────────────────────
    annotations = paper.get("annotations", [])
    if annotations:
        lines.append("## Highlights & Annotations")
        lines.append("")

        # Group by page for readability
        pages_seen = []
        page_anns: dict[str, list] = defaultdict(list)
        for ann in annotations:
            pg = ann.get("page", "?")
            page_anns[pg].append(ann)
            if pg not in pages_seen:
                pages_seen.append(pg)

        for pg in pages_seen:
            for ann in page_anns[pg]:
                ann_type = ann.get("type_name", "highlight")
                color    = ann.get("color", "")
                color_label = COLOR_LABELS.get(color, "")

                # Skip empty image/ink annotations without comment
                if ann_type in ("image", "ink") and not ann.get("comment"):
                    continue

                # Page + color badge
                badge = f"p.{pg}"
                if color_label:
                    badge += f" · {color_label}"

                text    = ann.get("text", "").strip()
                comment = ann.get("comment", "").strip()

                if ann_type == "highlight" and text:
                    lines.append(f"> [!quote] {badge}")
                    lines.append(f"> {text}")
                    if comment:
                        lines.append(f"> ")
                        lines.append(f"> **Note:** {comment}")
                    lines.append("")
                elif ann_type == "note" or (not text and comment):
                    lines.append(f"> [!note] {badge}")
                    lines.append(f"> {comment}")
                    lines.append("")
                elif ann_type == "image":
                    lines.append(f"> [!example] {badge} · *[image/screenshot]*")
                    if comment:
                        lines.append(f"> {comment}")
                    lines.append("")
                elif text:
                    lines.append(f"> [!info] {badge}")
                    lines.append(f"> {text}")
                    if comment:
                        lines.append(f"> **Note:** {comment}")
                    lines.append("")

    # ── Zotero notes ──────────────────────────────────────────────────────────
    notes = [n for n in paper.get("notes", []) if n.strip()]
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append(note)
            lines.append("")

    # ── Related papers ────────────────────────────────────────────────────────
    if connections:
        lines.append("## Related Papers")
        lines.append("")
        # Sort by reason type (authors first, then tags)
        sorted_conns = sorted(connections, key=lambda c: (
            "shared author" not in c["reason"],
            c["paper"].get("year") or 0
        ))
        for conn in sorted_conns:
            other   = conn["paper"]
            link    = wikilink(other)
            reason  = conn["reason"]
            year    = other.get("year", "")
            authors = other.get("authors", [])
            auth_str = author_short(authors[0]) if authors else ""
            lines.append(f"- {link} ({auth_str}{', ' + str(year) if year else ''}) — *{reason}*")
        lines.append("")

    # LLM connections placeholder
    if llm and llm.get("connections"):
        lines.append("### LLM-Suggested Connections")
        lines.append("")
        for conn in llm["connections"]:
            lines.append(f"- [[{conn['citekey']}]] — {conn['reason']}")
        lines.append("")
    else:
        lines.append("<!-- LLM_ENRICHMENT:connections -->")
        lines.append("")

    # ── PDF full text (collapsed, for Obsidian search) ────────────────────────
    pdf_pages = paper.get("pdf_text")
    if pdf_pages:
        lines.append("## PDF Text")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Full extracted text (for search)</summary>")
        lines.append("")
        lines.append("```")

        all_text = "\n\n".join(
            f"--- Page {p['page']} ---\n{p['text']}"
            for p in pdf_pages
        )
        if MAX_PDF_CHARS and len(all_text) > MAX_PDF_CHARS:
            all_text = all_text[:MAX_PDF_CHARS] + f"\n\n[... truncated at {MAX_PDF_CHARS:,} chars ...]"

        lines.append(all_text)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


# ── Index renderers ───────────────────────────────────────────────────────────

def render_all_papers_index(papers: list[dict]) -> str:
    lines = [
        "# All Papers",
        "",
        f"*{len(papers)} papers · auto-generated from Zotero `09_0_neuro_ai_thesis`*",
        "",
        "| Paper | Authors | Year | Journal | Tags | Ann. |",
        "| ----- | ------- | ---- | ------- | ---- | ---- |",
    ]
    sorted_papers = sorted(papers, key=lambda p: (-(p.get("year") or 0), p.get("title", "")))
    for p in sorted_papers:
        link    = wikilink(p)
        authors = p.get("authors", [])
        auth    = author_short(authors[0]) if authors else ""
        if len(authors) > 1:
            auth += " et al."
        year  = str(p.get("year", "")) if p.get("year") else ""
        jour  = (p.get("publication") or "")[:40]
        tags  = ", ".join(p.get("tags", [])[:3])
        ann   = str(p.get("annotation_count", 0))
        lines.append(f"| {link} | {auth} | {year} | {jour} | {tags} | {ann} |")
    return "\n".join(lines)


def render_by_tag_index(papers: list[dict]) -> str:
    by_tag: dict[str, list] = defaultdict(list)
    for p in papers:
        for tag in p.get("tags", []):
            by_tag[tag].append(p)

    lines = [
        "# Papers by Tag",
        "",
        f"*{len(by_tag)} tags · auto-generated*",
        "",
    ]
    for tag in sorted(by_tag, key=lambda t: (-len(by_tag[t]), t)):
        tag_papers = sorted(by_tag[tag], key=lambda p: -(p.get("year") or 0))
        lines.append(f"## {tag} ({len(tag_papers)})")
        lines.append("")
        for p in tag_papers:
            year = f" ({p['year']})" if p.get("year") else ""
            lines.append(f"- {wikilink(p)}{year}")
        lines.append("")
    return "\n".join(lines)


def render_by_author_index(papers: list[dict]) -> str:
    by_author: dict[str, list] = defaultdict(list)
    for p in papers:
        for a in p.get("authors", []):
            key = a.get("last", "").strip()
            if key:
                by_author[key].append(p)

    lines = [
        "# Papers by Author",
        "",
        f"*{len(by_author)} authors · auto-generated*",
        "",
    ]
    for author in sorted(by_author):
        author_papers = sorted(by_author[author], key=lambda p: -(p.get("year") or 0))
        lines.append(f"## {author} ({len(author_papers)})")
        lines.append("")
        for p in author_papers:
            year = f" ({p['year']})" if p.get("year") else ""
            lines.append(f"- {wikilink(p)}{year}")
        lines.append("")
    return "\n".join(lines)


def render_by_year_index(papers: list[dict]) -> str:
    by_year: dict[int, list] = defaultdict(list)
    no_year = []
    for p in papers:
        if p.get("year"):
            by_year[p["year"]].append(p)
        else:
            no_year.append(p)

    lines = [
        "# Papers by Year",
        "",
        f"*{len(papers)} papers · auto-generated*",
        "",
    ]
    for year in sorted(by_year, reverse=True):
        year_papers = sorted(by_year[year], key=lambda p: p.get("title", ""))
        lines.append(f"## {year} ({len(year_papers)})")
        lines.append("")
        for p in year_papers:
            lines.append(f"- {wikilink(p)}")
        lines.append("")

    if no_year:
        lines.append(f"## Unknown Year ({len(no_year)})")
        lines.append("")
        for p in no_year:
            lines.append(f"- {wikilink(p)}")
        lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Obsidian notes from papers.json")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just preview counts")
    parser.add_argument("--only-citekey", help="Only regenerate this one citekey (for testing)")
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run 01_extract_zotero.py first.")
        return

    with open(DATA_PATH, encoding="utf-8") as f:
        papers = json.load(f)

    if args.only_citekey:
        papers = [p for p in papers if p.get("citekey") == args.only_citekey]
        if not papers:
            print(f"No paper with citekey '{args.only_citekey}' found.")
            return

    print(f"Loaded {len(papers)} papers")

    # Build connections across all papers
    print("Building connection graph...")
    connections = build_connections(papers)
    total_connections = sum(len(v) for v in connections.values()) // 2
    print(f"  {total_connections} bidirectional connections found")

    if not args.dry_run:
        PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_no_title = 0

    for paper in papers:
        if not paper.get("title"):
            skipped_no_title += 1
            continue

        fname   = note_filename(paper)
        outpath = PAPERS_DIR / fname
        conns   = connections.get(paper["item_id"], [])
        content = render_paper_note(paper, conns)

        if args.dry_run:
            print(f"  [dry-run] Would write: {outpath} ({len(content)} chars)")
        else:
            outpath.write_text(content, encoding="utf-8")
        written += 1

    # Index notes
    index_notes = [
        ("00_all_papers.md",  render_all_papers_index(papers)),
        ("00_by_tag.md",      render_by_tag_index(papers)),
        ("00_by_author.md",   render_by_author_index(papers)),
        ("00_by_year.md",     render_by_year_index(papers)),
    ]
    for fname, content in index_notes:
        outpath = INDEX_DIR / fname
        if args.dry_run:
            print(f"  [dry-run] Would write index: {outpath}")
        else:
            outpath.write_text(content, encoding="utf-8")

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}✓ Done")
    print(f"  Paper notes: {written}  |  Skipped (no title): {skipped_no_title}")
    print(f"  Index notes: {len(index_notes)}")
    if not args.dry_run:
        print(f"  Vault: {VAULT_PATH}")


if __name__ == "__main__":
    main()

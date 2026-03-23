#!/usr/bin/env bash
# run_pipeline.sh
# Run the full Zotero → Obsidian pipeline.
# Re-run anytime: Step 2 skips already-extracted PDFs.
#
# Usage:
#   ./run_pipeline.sh            # normal run (incremental)
#   ./run_pipeline.sh --force    # re-extract all PDFs from scratch
#   ./run_pipeline.sh --dry-run  # preview note generation without writing

set -e
cd "$(dirname "$0")"

FORCE=""
DRY_RUN=""
for arg in "$@"; do
    case $arg in
        --force)   FORCE="--force"   ;;
        --dry-run) DRY_RUN="--dry-run" ;;
    esac
done

echo "════════════════════════════════════════════"
echo " Zotero → Obsidian Pipeline"
echo "════════════════════════════════════════════"
echo ""

echo "► Step 1: Extract Zotero database"
python3 01_extract_zotero.py
echo ""

echo "► Step 2: Extract PDF text $FORCE"
python3 02_extract_pdf_text.py $FORCE
echo ""

echo "► Step 3: Generate Obsidian notes $DRY_RUN"
python3 03_generate_notes.py $DRY_RUN
echo ""

echo "════════════════════════════════════════════"
echo " Done!"
echo "════════════════════════════════════════════"

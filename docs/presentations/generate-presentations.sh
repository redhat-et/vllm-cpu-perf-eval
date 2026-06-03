#!/bin/bash
#
# Generate presentation files from Marp markdown
#
# Usage:
#   ./generate-presentations.sh [format]
#
# Formats: html, pdf, pptx, all (default: all)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if marp-cli is installed
if ! command -v marp &> /dev/null; then
    echo "Error: marp-cli is not installed"
    echo ""
    echo "Install with:"
    echo "  npm install -g @marp-team/marp-cli"
    echo ""
    exit 1
fi

FORMAT="${1:-all}"
SOURCE_FILE="embedding-models-methodology-results.md"
OUTPUT_PREFIX="embedding-models-methodology-results"

# Create output directory
mkdir -p output

echo "========================================="
echo "Generating Presentations"
echo "========================================="
echo "Source: $SOURCE_FILE"
echo "Format: $FORMAT"
echo ""

generate_html() {
    echo "Generating HTML presentation..."
    marp "$SOURCE_FILE" \
        --html \
        --allow-local-files \
        -o "output/${OUTPUT_PREFIX}.html"
    echo "✅ HTML: output/${OUTPUT_PREFIX}.html"
}

generate_pdf() {
    echo "Generating PDF presentation..."
    marp "$SOURCE_FILE" \
        --allow-local-files \
        --pdf \
        -o "output/${OUTPUT_PREFIX}.pdf"
    echo "✅ PDF: output/${OUTPUT_PREFIX}.pdf"
}

generate_pptx() {
    echo "Generating PowerPoint presentation..."
    marp "$SOURCE_FILE" \
        --allow-local-files \
        --pptx \
        -o "output/${OUTPUT_PREFIX}.pptx"
    echo "✅ PPTX: output/${OUTPUT_PREFIX}.pptx"
}

case "$FORMAT" in
    html)
        generate_html
        ;;
    pdf)
        generate_pdf
        ;;
    pptx)
        generate_pptx
        ;;
    all)
        generate_html
        generate_pdf
        generate_pptx
        ;;
    *)
        echo "Error: Unknown format '$FORMAT'"
        echo "Valid formats: html, pdf, pptx, all"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Done!"
echo "========================================="
echo "Output files in: output/"
ls -lh output/

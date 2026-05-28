#!/usr/bin/env bash
# Render the three JORS submission documents to PDF.
#
# Two-pass workaround for a Typst rendering bug where citeproc-formatted
# inline citations come out as empty parens "()". The first pass resolves
# @-citations to plain "(Author Year)" markdown; the second pass renders
# that markdown to PDF via Typst. See bead lab_archives_mcp for context.
#
# Requires: pandoc (>= 3.0), typst.
# Output:   jors_metapaper.pdf, jors_cover_letter.pdf,
#           jors_response_to_reviewers.pdf in the repo root.

set -euo pipefail

cd "$(dirname "$0")/.."

FONT="Helvetica"
TMP_META=$(mktemp -t jors_metapaper.XXXXXX.md)
TMP_RESP=$(mktemp -t jors_response.XXXXXX.md)
trap 'rm -f "$TMP_META" "$TMP_RESP"' EXIT

# Metapaper: citations + bibliography
pandoc jors_metapaper.md --citeproc --bibliography=paper.bib -t markdown -o "$TMP_META"
pandoc "$TMP_META" --pdf-engine=typst -V mainfont="$FONT" -o jors_metapaper.pdf

# Response to reviewers: citations + bibliography
pandoc jors_response_to_reviewers.md --citeproc --bibliography=paper.bib -t markdown -o "$TMP_RESP"
pandoc "$TMP_RESP" --pdf-engine=typst -V mainfont="$FONT" -o jors_response_to_reviewers.pdf

# Cover letter: no citations
pandoc jors_cover_letter.md --pdf-engine=typst -V mainfont="$FONT" -o jors_cover_letter.pdf

ls -la jors_metapaper.pdf jors_cover_letter.pdf jors_response_to_reviewers.pdf

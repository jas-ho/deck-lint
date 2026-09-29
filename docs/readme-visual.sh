#!/usr/bin/env bash
# Regenerate docs/img/readme-visual.png from docs/demo.typ. Needs typst and deck-lint on PATH.
set -euo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d)
width=560
typst compile demo.typ "$tmp/demo.pdf"
deck-lint sheet "$tmp/demo.pdf" --output "$tmp/sheet.png" --columns 3 --width "$width" >/dev/null
check=$(deck-lint check --typ demo.typ || true)
typst compile --root / --ppi 144 \
  --input sheet="$tmp/sheet.png" --input width="$width" \
  --input cellh="$(( (width * 9 + 15) / 16 + 22 ))" --input check="$check" \
  readme-visual.typ img/readme-visual.png
echo img/readme-visual.png

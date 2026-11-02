#!/usr/bin/env bash
# Download the Google Fonts catalogue (open licences only: OFL, Apache, UFL) as candidates for font_search.py.
# Usage: bash get_fonts.sh [dest_dir]   (default: ~/.cache/reverse-motion/google-fonts, about 1 GB for ofl/)
set -euo pipefail
DEST="${1:-$HOME/.cache/reverse-motion/google-fonts}"
if [[ -d "$DEST/.git" ]]; then (cd "$DEST" && git pull --depth 1 -q); else
  git clone --depth 1 --filter=blob:none --sparse https://github.com/google/fonts.git "$DEST"
  (cd "$DEST" && git sparse-checkout set ofl apache ufl)
fi
echo "Polices candidates dans : $DEST   (font_search.py <targets.json> $DEST <out.json>)"

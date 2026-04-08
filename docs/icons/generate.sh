#!/bin/bash
# ctxray icon generator — produces all standard sizes from SVG sources
# Requires: rsvg-convert (from librsvg, brew install librsvg)
set -euo pipefail
cd "$(dirname "$0")"

SIZES=(512 256 128 96 48 32 16)

echo "Generating production PNGs..."

# Brand + CLI: use main SVG for large sizes, dedicated 48px SVG for ≤48
for icon in brand-icon cli-icon; do
  for size in "${SIZES[@]}"; do
    if [ "$size" -le 48 ] && [ -f "${icon}-48.svg" ]; then
      rsvg-convert -w "$size" -h "$size" "${icon}-48.svg" -o "${icon}-${size}.png"
    else
      rsvg-convert -w "$size" -h "$size" "${icon}.svg" -o "${icon}-${size}.png"
    fi
    echo "  ${icon}-${size}.png"
  done
done

# Favicon: main SVG for large, 48px SVG for mid, 16px SVG for tiny
for size in "${SIZES[@]}"; do
  if [ "$size" -le 16 ] && [ -f "favicon-16.svg" ]; then
    rsvg-convert -w "$size" -h "$size" "favicon-16.svg" -o "favicon-${size}.png"
  elif [ "$size" -le 48 ] && [ -f "favicon-48.svg" ]; then
    rsvg-convert -w "$size" -h "$size" "favicon-48.svg" -o "favicon-${size}.png"
  else
    rsvg-convert -w "$size" -h "$size" "favicon.svg" -o "favicon-${size}.png"
  fi
  echo "  favicon-${size}.png"
done

# Wordmark (single size, wide format)
rsvg-convert -w 1200 -h 256 "wordmark.svg" -o "wordmark.png"
echo "  wordmark.png"

echo ""
echo "Generated $(ls -1 *.png 2>/dev/null | wc -l | tr -d ' ') PNG files."
echo ""
echo "Icon selection guide:"
echo ""
echo "  BRAND (teal/blue panels on gradient):"
echo "    Chrome Extension store:  brand-icon-128.png"
echo "    PyPI / GitHub / npm:     brand-icon-512.png or brand-icon-128.png"
echo "    macOS/iOS (maskable):    brand-icon-512.png (platform applies mask)"
echo "    Browser toolbar (48px):  brand-icon-48.png (pixel-aligned)"
echo "    Browser tab (≤32px):     favicon-32.png or favicon-16.png"
echo ""
echo "  CLI (teal/blue panels on dark):"
echo "    CLI package icon:        cli-icon-512.png or cli-icon-128.png"
echo "    Terminal/toolbar (48px): cli-icon-48.png (pixel-aligned)"
echo "    Browser tab (≤32px):     favicon-32.png or favicon-16.png"
echo ""
echo "  WORDMARK (icon + ctxray text):"
echo "    README header:           wordmark.svg (inline) or wordmark.png"
echo "    Social sharing:          wordmark.svg (1200x256)"

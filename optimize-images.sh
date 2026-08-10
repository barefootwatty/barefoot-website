#!/bin/bash
# Barefoot image optimiser — modern standard, using macOS sips (no extra installs).
# Produces responsive AVIF (primary) + JPEG (fallback) at 3 widths for <picture>/srcset.
#
# Usage:
#   1. Drop source photos (jpg/jpeg/png) into  assets/raw/
#   2. Run:  bash optimize-images.sh
#   3. Optimised files land in  assets/img/  as  {name}-{1600|1000|640}.{avif|jpg}
#
# Then reference in HTML, e.g.:
#   <picture>
#     <source type="image/avif" srcset="assets/img/hero-640.avif 640w, assets/img/hero-1000.avif 1000w, assets/img/hero-1600.avif 1600w" sizes="100vw">
#     <img class="resp" src="assets/img/hero-1000.jpg" srcset="assets/img/hero-640.jpg 640w, assets/img/hero-1000.jpg 1000w, assets/img/hero-1600.jpg 1600w" sizes="100vw" width="1600" height="900" alt="..." loading="lazy" decoding="async">
#   </picture>

set -e
cd "$(dirname "$0")"
RAW="assets/raw"
OUT="assets/img"
WIDTHS=(1600 1000 640)
AVIF_Q=58      # AVIF quality (visually excellent, tiny files)
JPEG_Q=80      # JPEG fallback quality

mkdir -p "$OUT"
shopt -s nullglob nocaseglob
count=0
for src in "$RAW"/*.jpg "$RAW"/*.jpeg "$RAW"/*.png; do
  [ -e "$src" ] || continue
  base=$(basename "$src"); base="${base%.*}"
  # SEO-friendly filename: lowercase, spaces/underscores -> hyphens
  slug=$(echo "$base" | tr '[:upper:] _' '[:lower:]--' | tr -cd '[:alnum:]-')
  for w in "${WIDTHS[@]}"; do
    sips --resampleWidth "$w" -s format jpeg -s formatOptions "$JPEG_Q" "$src" --out "$OUT/${slug}-${w}.jpg" >/dev/null
    sips --resampleWidth "$w" -s format avif -s formatOptions "$AVIF_Q" "$src" --out "$OUT/${slug}-${w}.avif" >/dev/null
  done
  echo "  ✓ $slug  ->  ${slug}-{1600,1000,640}.{avif,jpg}"
  count=$((count+1))
done
echo "Done. Optimised $count source image(s) into $OUT/"
[ "$count" -eq 0 ] && echo "(No sources found — drop photos into $RAW/ first.)"

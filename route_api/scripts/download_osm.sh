#!/usr/bin/env bash
# Download the Korea extract once and clip it to Busan + buffer area.
# `osmium` is needed to keep the graph small enough for an ordinary machine.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/engine
OUT=data/engine/busan.osm.pbf
SOURCE=data/engine/south-korea-latest.osm.pbf
if [[ -s "$OUT" ]]; then
  echo "File exists: $OUT. Not re-downloading."
  exit 0
fi
if ! command -v osmium >/dev/null 2>&1; then
  echo "ERROR: osmium-tool is required; run: conda install -c conda-forge osmium-tool" >&2
  exit 2
fi
if [[ ! -s "$SOURCE" ]]; then
  echo 'Downloading Geofabrik South Korea OSM (large file) ...'
  curl --fail --location --retry 3 --connect-timeout 30 \
    'https://download.geofabrik.de/asia/south-korea-latest.osm.pbf' -o "${SOURCE}.part"
  mv "${SOURCE}.part" "$SOURCE"
fi
# Conservative bounding box around Busan and neighboring transfer corridors.
# NOT a precise official Busan administrative boundary; includes extra region.
BBOX='128.65,34.80,129.55,35.55'
echo "Clipping ${SOURCE} to Busan extended bbox ${BBOX}"
osmium extract --bbox "$BBOX" --strategy complete_ways "$SOURCE" --output "$OUT" --overwrite
[[ -s "$OUT" ]] || { echo 'Extract produced empty OSM file' >&2; exit 1; }
echo "Busan-area OSM ready: $OUT"

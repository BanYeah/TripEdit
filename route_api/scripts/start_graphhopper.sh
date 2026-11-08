#!/usr/bin/env bash
# Start the REAL GraphHopper routing engine (separate from FastAPI).
# Auto mode: WALK if no GTFS, BOTH if GTFS is present. Override --walk-only/--transit.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -s data/engine/busan.osm.pbf ]]; then
  echo "ERROR: Missing OSM. Run: bash scripts/download_osm.sh" >&2
  exit 2
fi
MODE=auto
case "${1:-}" in
  '') ;;
  --walk-only) MODE=walk ;;
  --transit) MODE=pt ;;
  *) echo 'Usage: bash scripts/start_graphhopper.sh [--walk-only|--transit]' >&2; exit 2 ;;
esac
if [[ "$MODE" == auto ]]; then
  if [[ -s data/engine/busan.gtfs.zip ]]; then MODE=pt; else MODE=walk; fi
fi
if [[ "$MODE" == pt && ! -s data/engine/busan.gtfs.zip ]]; then
  echo "ERROR: Missing data/engine/busan.gtfs.zip. Get valid GTFS first, or use --walk-only." >&2
  exit 2
fi
if [[ "$MODE" == pt ]]; then
  python -m scripts.validate_gtfs data/engine/busan.gtfs.zip
fi
VERSION="${GRAPH_HOPPER_VERSION:-11.0}"
JAR="third_party/graphhopper-web-${VERSION}.jar"
if [[ ! -s "$JAR" ]]; then
  shopt -s nullglob
  jars=(third_party/graphhopper/web/target/graphhopper-web-*.jar)
  if (( ${#jars[@]} > 0 )); then JAR="${jars[0]}"; fi
fi
if [[ ! -s "$JAR" ]]; then
  echo 'ERROR: No GraphHopper JAR; run bash scripts/fetch_graphhopper_jar.sh' >&2
  exit 2
fi
if [[ "$MODE" == pt ]]; then CONFIG=graphhopper/config.yml; else CONFIG=graphhopper/config-walk.yml; fi
echo "Starting GraphHopper mode=$MODE with $CONFIG..."
echo 'Do NOT assume transit works on requested dates without checking GTFS calendar.'
exec java -Xmx"${GRAPH_HOPPER_HEAP_GB:-8}"g -jar "$JAR" server "$CONFIG"

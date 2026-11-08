#!/usr/bin/env bash
# Needs git, Maven, and Java 21 on YOUR machine. Does not download OSM / GTFS.
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${GRAPH_HOPPER_TAG:-11.0}"
if [[ ! -d third_party/graphhopper/.git ]]; then
  mkdir -p third_party
  git clone --depth 1 --branch "$TAG" https://github.com/graphhopper/graphhopper.git third_party/graphhopper
fi
(cd third_party/graphhopper && mvn -DskipTests package)
printf '\nBuilt GraphHopper %s. Add data/engine/busan.osm.pbf and busan.gtfs.zip.\n' "$TAG"

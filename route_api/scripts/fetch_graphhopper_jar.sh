#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${GRAPH_HOPPER_VERSION:-11.0}"
TARGET="third_party/graphhopper-web-${VERSION}.jar"
mkdir -p third_party
if [[ -s "$TARGET" ]]; then
  echo "Already exists: $TARGET"
  exit 0
fi
URL="https://repo.maven.apache.org/maven2/com/graphhopper/graphhopper-web/${VERSION}/graphhopper-web-${VERSION}.jar"
echo "Downloading official GraphHopper JAR ${VERSION}..."
curl --fail --location --retry 3 --connect-timeout 20 "$URL" -o "${TARGET}.part"
mv "${TARGET}.part" "$TARGET"
echo "Ready: $TARGET"

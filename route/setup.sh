#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .runtime

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt

version=10.2
jar=".runtime/graphhopper-web-${version}.jar"
if [[ ! -s "$jar" ]]; then
  curl -fL --retry 3 "https://github.com/graphhopper/graphhopper/releases/download/${version}/graphhopper-web-${version}.jar" -o "${jar}.tmp"
  mv "${jar}.tmp" "$jar"
fi
if [[ ! -x .runtime/jdk/bin/java ]] && ! command -v java >/dev/null; then
  if [[ "$(uname -s)/$(uname -m)" != Linux/x86_64 ]]; then
    echo 'Java 17 이상을 설치한 뒤 다시 실행하세요.' >&2
    exit 1
  fi
  curl -fL --retry 3 'https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse' -o .runtime/jdk.tar.gz
  mkdir -p .runtime/jdk
  tar -xzf .runtime/jdk.tar.gz -C .runtime/jdk --strip-components=1
  rm .runtime/jdk.tar.gz
fi

.venv/bin/python prepare.py

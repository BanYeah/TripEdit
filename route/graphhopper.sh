#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 prepare.py

java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
if [[ -x .runtime/jdk/bin/java ]]; then java_bin=.runtime/jdk/bin/java; fi
if [[ ! -f .runtime/graphhopper-web-10.2.jar ]]; then
  echo './setup.sh를 실행한 뒤 다시 실행하세요.' >&2
  exit 1
fi

# 최초 실행은 그래프를 생성하며, 이후에는 저장된 그래프를 불러옵니다.
exec "$java_bin" "-Xmx${GH_HEAP:-8g}" -jar .runtime/graphhopper-web-10.2.jar server config.yml

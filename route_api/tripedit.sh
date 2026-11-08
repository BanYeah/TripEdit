#!/usr/bin/env bash
# TripEdit one-command launcher for Ubuntu/Miniforge.
# Usage: ./tripedit.sh start|stop|restart|status|logs [graphhopper|api]|test
# Place this file in /home/doojinyang/workspace/busan_tripedit_route_api.
set -Eeuo pipefail

PROJECT_DIR="${TRIPEDIT_PROJECT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)}"
if [[ ! -f "$PROJECT_DIR/scripts/start_graphhopper.sh" && -f /home/doojinyang/workspace/busan_tripedit_route_api/scripts/start_graphhopper.sh ]]; then
  PROJECT_DIR=/home/doojinyang/workspace/busan_tripedit_route_api
fi
if [[ ! -f "$PROJECT_DIR/scripts/start_graphhopper.sh" || ! -f "$PROJECT_DIR/app/main.py" ]]; then
  echo "오류: TripEdit 프로젝트를 찾지 못했습니다: $PROJECT_DIR" >&2
  echo "tripedit.sh를 프로젝트 최상위 폴더에 복사하세요." >&2
  exit 2
fi
cd "$PROJECT_DIR"

RUN_DIR="$PROJECT_DIR/.tripedit_run"
LOG_DIR="$PROJECT_DIR/logs"
GH_PID="$RUN_DIR/graphhopper.pid"
API_PID="$RUN_DIR/fastapi.pid"
GH_LOG="$LOG_DIR/graphhopper.log"
API_LOG="$LOG_DIR/fastapi.log"
CONDA_ENV="${TRIPEDIT_CONDA_ENV:-tripedit}"
GRAPH_HOPPER_HEAP_GB="${GRAPH_HOPPER_HEAP_GB:-32}"
mkdir -p "$RUN_DIR" "$LOG_DIR"

err() { printf '오류: %s\n' "$*" >&2; }
note() { printf '%s\n' "$*"; }

activate_conda() {
  local conda_sh=''
  local root
  for root in "${TRIPEDIT_CONDA_ROOT:-}" "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3"; do
    [[ -n "$root" && -f "$root/etc/profile.d/conda.sh" ]] || continue
    conda_sh="$root/etc/profile.d/conda.sh"
    break
  done
  if [[ -z "$conda_sh" ]]; then
    err "Conda 초기화 파일을 못 찾았습니다. TRIPEDIT_CONDA_ROOT에 Miniforge 경로를 지정하세요."
    return 1
  fi
  # Some conda versions reference unset variables during activation.
  set +u
  # shellcheck disable=SC1090
  source "$conda_sh"
  conda activate "$CONDA_ENV" || { set -u; err "Conda 환경 '$CONDA_ENV' 활성화 실패"; return 1; }
  set -u
  export PYTHONUNBUFFERED=1
}

http_ok() {
  # Test the requested endpoint, not just an open socket.
  [[ "$(curl --noproxy '*' -sS -o /dev/null -m 2 -w '%{http_code}' "$1" 2>/dev/null || true)" == '200' ]]
}

port_busy() {
  # Returns true even if the process listening on the port isn't HTTP.
  python - "$1" <<'PY'
import socket,sys
s=socket.socket(); s.settimeout(1)
try:
    sys.exit(0 if s.connect_ex(('127.0.0.1',int(sys.argv[1]))) == 0 else 1)
finally:
    s.close()
PY
}

owned_pid() {
  local file="$1" kind="$2" pid cmdline
  [[ -s "$file" ]] || return 1
  read -r pid < "$file"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  case "$kind" in
    graphhopper) [[ "$cmdline" == *'graphhopper'* || "$cmdline" == *'start_graphhopper.sh'* ]] ;;
    api) [[ "$cmdline" == *'uvicorn app.main:app'* ]] ;;
  esac
}

version_data() {
  if [[ -n "${DATA_VERSION:-}" ]]; then return; fi
  local osm='none' gtfs='none'
  [[ -f data/engine/busan.osm.pbf ]] && osm="$(stat -c '%s-%Y' data/engine/busan.osm.pbf)"
  [[ -f data/engine/busan.gtfs.zip ]] && gtfs="$(stat -c '%s-%Y' data/engine/busan.gtfs.zip)"
  export DATA_VERSION="busan-osm-${osm}-gtfs-${gtfs}"
}

check_java() {
  if ! command -v java >/dev/null 2>&1; then
    err 'Java가 없습니다. conda install -c conda-forge openjdk=21 -y'
    return 1
  fi
  local major
  major="$(java -version 2>&1 | sed -n '1s/.*version "\([0-9][0-9]*\).*/\1/p')"
  if [[ "$major" == '1' ]]; then major=8; fi
  if [[ -z "$major" || "$major" -lt 17 ]]; then
    err "GraphHopper가 Java 17+를 요구합니다. 현재: $(java -version 2>&1 | head -1)"
    return 1
  fi
}

start_graphhopper() {
  if http_ok 'http://127.0.0.1:8989/info'; then
    note '✓ GraphHopper: 이미 실행 중 (8989 포트). 기존 서버를 그대로 사용합니다.'
    return
  fi
  if owned_pid "$GH_PID" graphhopper; then
    note '… GraphHopper: 이미 실행을 시작했고 초기화 중입니다.'
    return
  fi
  if port_busy 8989; then
    note '… 8989 포트가 사용 중입니다. GraphHopper 초기화 중이거나 다른 서비스일 수 있으므로 중복 실행하지 않습니다.'
    note '  ./tripedit.sh status 와 기존 GraphHopper 터미널의 로그를 확인하세요.'
    return 0
  fi
  if [[ ! -s data/engine/busan.osm.pbf ]]; then
    err 'data/engine/busan.osm.pbf가 없습니다. 먼저 OSM 데이터를 준비해야 합니다.'
    return 1
  fi
  if [[ ! -s data/engine/busan.gtfs.zip ]]; then
    err 'data/engine/busan.gtfs.zip이 없습니다. 대중교통 GTFS 데이터를 먼저 준비해야 합니다.'
    return 1
  fi
  check_java
  note "▶ GraphHopper 시작 (OSM + GTFS, Java 힙 ${GRAPH_HOPPER_HEAP_GB}GB)"
  note '  기존 그래프 캐시를 삭제하지 않습니다. 초기 그래프 생성이 필요하면 서버가 준비되기 전까지 시간이 걸릴 수 있습니다.'
  nohup env GRAPH_HOPPER_HEAP_GB="$GRAPH_HOPPER_HEAP_GB" \
    bash scripts/start_graphhopper.sh --transit \
    </dev/null >>"$GH_LOG" 2>&1 &
  printf '%s\n' "$!" > "$GH_PID"
}

start_api() {
  if http_ok 'http://127.0.0.1:8000/health'; then
    note '✓ FastAPI: 이미 실행 중 (8000 포트). 기존 서버를 그대로 사용합니다.'
    return
  fi
  if owned_pid "$API_PID" api; then
    note '… FastAPI: 이미 실행을 시작했습니다.'
    return
  fi
  if port_busy 8000; then
    err '8000 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 확인하세요.'
    return 1
  fi
  if [[ ! -f data/places.csv ]]; then
    if [[ ! -f data/TripEdit-Places.xlsx ]]; then
      err '식당 데이터(data/places.csv, data/TripEdit-Places.xlsx)가 없습니다.'
      return 1
    fi
    note '▶ 처음 한 번만 restaurant 시트에서 식당 데이터 가져오는 중…'
    python -m scripts.import_restaurants
  fi
  version_data
  note '▶ FastAPI 시작 (TripEdit 일정 검증 + 길찾기 조회)'
  nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    </dev/null >>"$API_LOG" 2>&1 &
  printf '%s\n' "$!" > "$API_PID"
}

wait_for_api() {
  # A cold Python import can take a few seconds. Do not mistake it for a failure.
  local i
  for (( i=0; i<24; i++ )); do
    if http_ok 'http://127.0.0.1:8000/health'; then return 0; fi
    if [[ -f "$API_PID" ]] && ! owned_pid "$API_PID" api; then return 1; fi
    sleep 0.5
  done
  return 1
}

status() {
  note '========== TripEdit 상태 =========='
  note "프로젝트: $PROJECT_DIR"
  if http_ok 'http://127.0.0.1:8989/info'; then
    note '✓ GraphHopper (8989): 응답 정상'
  elif owned_pid "$GH_PID" graphhopper; then
    note '… GraphHopper (8989): 프로세스 실행 중, 서버 초기화 중'
  else
    note '✗ GraphHopper (8989): 응답 없음 / 프로세스 종료'
    [[ ! -f "$GH_LOG" ]] || note "  로그: $GH_LOG"
  fi
  if http_ok 'http://127.0.0.1:8000/health'; then
    note '✓ FastAPI (8000): 응답 정상'
    curl --noproxy '*' -sS -m 2 http://127.0.0.1:8000/health | python -c 'import json,sys; d=json.load(sys.stdin); print("  식당 수:", d.get("total_places"), "| 좌표 준비:", d.get("routable_places"))' || true
  elif owned_pid "$API_PID" api; then
    note '… FastAPI (8000): 프로세스 실행 중, 서버 초기화 중'
  else
    note '✗ FastAPI (8000): 응답 없음 / 프로세스 종료'
    [[ ! -f "$API_LOG" ]] || note "  로그: $API_LOG"
  fi
  note 'API 문서: http://127.0.0.1:8000/docs'
  note '경로 엔진: http://127.0.0.1:8989/info'
  note '※ 서버 응답 정상 ≠ 실제 도보/대중교통 경로 계산 검증 완료'
}

stop_pid() {
  local file="$1" kind="$2" label="$3" pid tries
  if ! owned_pid "$file" "$kind"; then
    note "- $label: 이 실행 스크립트가 시작한 프로세스 없음 (수동 실행한 서버는 종료하지 않습니다)."
    [[ ! -e "$file" ]] || rm -f "$file"
    return 0
  fi
  read -r pid < "$file"
  note "■ $label 종료 요청 (PID $pid)"
  kill -TERM "$pid" 2>/dev/null || true
  # Graceful shutdown: avoid kill -9, which may corrupt MapDB/GTFS graph caches.
  for (( tries=0; tries<15; tries++ )); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    note "  $label 종료가 아직 진행 중입니다. 강제 종료(kill -9)는 피하세요."
  else
    rm -f "$file"
    note "✓ $label 종료 완료"
  fi
}

show_logs() {
  local target="${1:-graphhopper}" logfile
  case "$target" in
    graphhopper|gh) logfile="$GH_LOG" ;;
    api|fastapi) logfile="$API_LOG" ;;
    *) err '사용법: ./tripedit.sh logs [graphhopper|api]'; exit 2 ;;
  esac
  if [[ -f "$logfile" ]]; then
    note "로그 파일: $logfile  (나가려면 Ctrl+C)"
    tail -n 60 -f "$logfile"
  else
    note "아직 로그가 없습니다: $logfile"
  fi
}

test_routes() {
  activate_conda
  if ! http_ok 'http://127.0.0.1:8000/health'; then
    err 'FastAPI를 먼저 시작하세요: ./tripedit.sh start'
    return 1
  fi
  if ! http_ok 'http://127.0.0.1:8989/info'; then
    err 'GraphHopper가 아직 준비되지 않았습니다: ./tripedit.sh status'
    return 1
  fi
  python - <<'PY'
import csv, math, os, sys
from datetime import datetime, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo
import httpx

p = 'data/places.csv'
with open(p, newline='', encoding='utf-8-sig') as f:
    places = [r for r in csv.DictReader(f) if r.get('latitude') and r.get('longitude')]
if len(places) < 2:
    print('경로 검증 불가: 좌표가 채워진 식당이 2개 미만입니다.')
    print('python -m scripts.enrich_kakao_coordinates 로 실제 좌표부터 확보하세요.')
    sys.exit(2)

def dist(a,b):
    la1,lo1,la2,lo2 = map(float,(a['latitude'],a['longitude'],b['latitude'],b['longitude']))
    r1,r2=math.radians(la1),math.radians(la2)
    dlat=math.radians(la2-la1); dlon=math.radians(lo2-lo1)
    h=math.sin(dlat/2)**2+math.cos(r1)*math.cos(r2)*math.sin(dlon/2)**2
    return 12742000 * math.atan2(math.sqrt(h), math.sqrt(1-h))

# A medium-distance pair gives a more informative transit test than adjacent restaurants.
a,b = min(combinations(places,2), key=lambda pair: abs(dist(*pair)-4500))
print(f"검사 장소: {a['name']} ({a['place_id']}) → {b['name']} ({b['place_id']})")
print(f'직선거리: {dist(a,b):.0f} m (실제 이동거리는 다름)')
now=datetime.now(ZoneInfo('Asia/Seoul'))
query_time=(now+timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
base='http://127.0.0.1:8000/travel-time'
failed=False
for mode in ('WALK','TRANSIT'):
    args={'from_id':a['place_id'],'to_id':b['place_id'],'mode':mode,'refresh':'true'}
    if mode=='TRANSIT': args['departure']=os.getenv('TRIPEDIT_TEST_DEPARTURE',query_time.isoformat())
    try:
        res=httpx.get(base,params=args,timeout=65)
        if res.status_code==200:
            data=res.json()
            print(f"{mode}: 성공 — {data['duration_minutes']}분, source={data.get('source')}")
        else:
            failed=True
            print(f'{mode}: HTTP {res.status_code} — {res.text[:700]}')
    except httpx.HTTPError as exc:
        failed=True
        print(f'{mode}: 요청 실패 — {exc}')
print('주의: TRANSIT 응답 성공만으로 실제 버스·지하철 탑승이나 시간표 정확성이 검증되지는 않습니다.')
sys.exit(1 if failed else 0)
PY
}

usage() {
  cat <<'HELP'
TripEdit 한 번에 실행 (현재 셸이 base여도 내부에서 tripedit Conda 환경 활성화)
  ./tripedit.sh start           GraphHopper + FastAPI 실행
  ./tripedit.sh status          현재 준비 상태 확인
  ./tripedit.sh test            두 식당 간 WALK/TRANSIT 실제 API 조회 시험
  ./tripedit.sh logs graphhopper   GraphHopper 로그 (Ctrl+C로 종료)
  ./tripedit.sh logs api        FastAPI 로그
  ./tripedit.sh stop            이 스크립트가 실행한 서버만 정상 종료
  ./tripedit.sh restart         정상 종료 후 재실행

참고: 기존 터미널에서 수동으로 시작한 서버는 재사용하며, stop으로 종료하지 않습니다.
환경변수: TRIPEDIT_CONDA_ROOT, TRIPEDIT_CONDA_ENV, GRAPH_HOPPER_HEAP_GB, DATA_VERSION
HELP
}

case "${1:-start}" in
  start)
    activate_conda
    note "활성화된 Python: $(command -v python)"
    start_graphhopper
    start_api
    if ! wait_for_api; then
      note 'FastAPI가 아직 준비되지 않았거나 오류로 종료됐습니다. ./tripedit.sh logs api로 확인하세요.'
    fi
    note ''
    status
    note ''
    note '초기화 중이라면 나중에 ./tripedit.sh status 로 확인하세요.'
    note '오류 확인: ./tripedit.sh logs graphhopper  또는  ./tripedit.sh logs api'
    ;;
  stop)
    stop_pid "$API_PID" api FastAPI
    stop_pid "$GH_PID" graphhopper GraphHopper
    ;;
  restart)
    stop_pid "$API_PID" api FastAPI
    stop_pid "$GH_PID" graphhopper GraphHopper
    activate_conda
    start_graphhopper
    start_api
    if ! wait_for_api; then
      note 'FastAPI 상태를 확인하세요: ./tripedit.sh logs api'
    fi
    status
    ;;
  status)
    activate_conda
    status
    ;;
  logs)
    show_logs "${2:-graphhopper}"
    ;;
  test)
    test_routes
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

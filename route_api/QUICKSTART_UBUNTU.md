# TripEdit 부산 길찾기 API — Ubuntu / Conda 빠른 실행 가이드

이 프로젝트는 `/home/doojinyang/workspace/busan_tripedit_route_api`에 압축을 덮어쓰는 방식으로 제공됩니다. **먼저 기존 폴더를 백업하세요.** 이미 서버가 실행 중이면 `Ctrl+C`로 종료하고 새 버전을 실행하세요.

## 0. 파일 설치 (기존 작업 디렉터리 유지)

> 아래 경로는 브라우저에서 ZIP을 `~/Downloads`에 저장했다는 가정입니다. 실제 다운로드 위치에 맞게 변경하세요.

```bash
cd /home/doojinyang/workspace
cp -a busan_tripedit_route_api busan_tripedit_route_api_backup
unzip -o ~/Downloads/busan_tripedit_route_api_v0.2.zip -d busan_tripedit_route_api
cd /home/doojinyang/workspace/busan_tripedit_route_api
conda activate tripedit
python -m pip install -r requirements-dev.txt
```

`data/TripEdit-Places.xlsx`는 ZIP에 포함되어 있습니다. 50개 식당의 원래 영업시간·체류시간을 그대로 사용합니다. 실제 사용자 엑셀을 다시 복사하고 싶으면 해당 이름으로 `data/` 폴더에 덮어쓰면 됩니다.

## 1. 식당 데이터 로드 + 테스트

```bash
python -m scripts.import_restaurants
python -m pytest -q
python -m scripts.status
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

브라우저: <http://127.0.0.1:8000/docs>

이 시점에서는 `GET /health`에 **total_places: 50**, **routable_places: 0**이 정상입니다. 다른 터미널에서 `GET /places`를 실행하면 식당 이름·영업시간·체류시간이 조회됩니다. **실제 길찾기는 아직 안 됩니다.**

## 2. 장소 위도/경도 확보 (카카오 장소 ID가 일치할 때만 저장)

Kakao Developers에서 앱 REST API 키를 만들고 **로컬 장소 검색** 권한·쿼터를 확인합니다. REST API는 **경로 조회가 아니라 일회성 좌표 조회용**입니다. 카카오 API 호출 한도·약관을 확인하세요.

```bash
# 새 터미널에서 가상환경 + 프로젝트 진입
conda activate tripedit
cd /home/doojinyang/workspace/busan_tripedit_route_api

# 입력한 키가 화면과 명령 기록에 나타나지 않도록 입력
read -rsp "Kakao REST API Key: " KAKAO_REST_API_KEY; echo
export KAKAO_REST_API_KEY

# 우선 2곳만 시험
python -m scripts.enrich_kakao_coordinates --limit 2

# 문제없으면 나머지 식당 조회 (다른 장소 ID가 나오면 매칭하지 않음)
python -m scripts.enrich_kakao_coordinates

python -m scripts.status
```

`data/places.csv`의 `latitude`, `longitude`가 채워지며, 찾지 못한 식당은 **공란으로 남습니다**. `data/coordinate_report.json`에 미확인 매장이 기록됩니다. 일치하지 않는 이름으로 임의 좌표를 설정하지 않습니다. 좌표 API 키가 없다면 `data/places.csv`의 두 좌표 열을 직접 채워도 됩니다.

**주의:** API 서버는 시작 시 CSV를 읽습니다. 새 좌표를 채웠다면 서버를 재시작해야 반영됩니다.

## 3. OSM 도로 데이터 + GraphHopper 준비

Python API를 실행하는 환경과 동일한 Conda 환경에서 아래 명령을 실행합니다. 한국 OSM 전체 다운로드는 크고, 이후 부산·주변 지역으로 자르므로 충분한 디스크 용량이 필요합니다.

```bash
# 프로젝트 루트
conda install -c conda-forge openjdk=21 osmium-tool curl -y
java -version

bash scripts/download_osm.sh
bash scripts/fetch_graphhopper_jar.sh

# 제1터미널: 도보 엔진부터 실행 — OSM 그래프를 처음 생성할 때는 메모리·시간이 필요함
bash scripts/start_graphhopper.sh --walk-only
```

`bash scripts/download_osm.sh`는 Geofabrik 한국 지도를 다운로드해 **부산과 주변 지역을 포함하는 범위(128.65~129.55E, 34.80~35.55N)** 로 클립합니다. 정확한 행정경계가 아닌 네트워크용 넉넉한 범위입니다.

엔진이 시작하면 브라우저 <http://127.0.0.1:8989/> 또는 다음 명령으로 확인하세요.

```bash
curl http://127.0.0.1:8989/info
```

API 서버가 실행 중이고 좌표가 2곳 이상 채워졌다면 `GET /travel-time?from_id=...&to_id=...&mode=WALK`이 실제 OSM 보행망으로 계산됩니다.

## 4. GTFS 대중교통 연결 (필수 추가 데이터)

**이 ZIP에는 부산 실 GTFS가 없습니다.** GTFS는 교통기관의 정류장·노선·운행시각표입니다. 국가교통DB(KTDB) 등에서 **TripEdit 평가 날짜에 유효한** GTFS 파일을 얻어 다음 위치에 저장해야 합니다.

```text
data/engine/busan.gtfs.zip
```

자료 안내: <https://www.ktdb.go.kr/> (GTFS 기반정보·자료신청). 2025년 3월 기준 자료는 **2026년 11월 여행의 실제 운행 데이터라고 가정하면 안 됩니다**. 데이터 라이선스도 확인하세요.

파일 준비 후:

```bash
python -m scripts.validate_gtfs data/engine/busan.gtfs.zip
python -m scripts.check_gtfs_date data/engine/busan.gtfs.zip --date 2026-11-10

# 8989에서 실행 중인 GraphHopper를 Ctrl+C로 종료하고 재시작
bash scripts/start_graphhopper.sh --transit
```

`--transit`은 OSM+GTFS 그래프를 **별도 캐시**에 생성합니다. 이 단계가 성공해야 대중교통 `mode=TRANSIT`으로 실 계산 가능합니다. 공휴일, 실시간 지연, 데이터 누락은 별도 검증이 필요합니다.

## 5. FastAPI와 TripEdit 일정 API 사용

GraphHopper는 터미널 1에서 계속 실행하고 **별도 터미널 2**에서 API 서버를 실행합니다.

```bash
conda activate tripedit
cd /home/doojinyang/workspace/busan_tripedit_route_api
export DATA_VERSION=busan-osm-gtfs-2026-v1   # OSM/GTFS 업데이트할 때 반드시 변경
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

브라우저 <http://127.0.0.1:8000/docs>에서 요청을 직접 보내세요.

- `GET /places` : 식당 50곳 및 엑셀에 있는 `opening_hours`, `min_duration` 보기
- `GET /travel-time` : `from_id`, `to_id`, `mode=WALK/TRANSIT`로 실제 이동시간 요청. 대중교통은 `departure=2026-11-10T12:00:00+09:00` 필수 (Swagger 입력은 `+` 그대로 가능)
- `POST /itineraries/validate` : 여러 방문의 운영시간, 식사 시간, 최소 체류시간, 중복, 이동시간 검증 (저장 X)
- `PUT /itineraries/{itinerary_id}` : 유효한 방문 일정만 SQLite에 저장 (기존 일정 보존)
- `GET /itineraries/{itinerary_id}` : 저장된 일정 보기
- `POST /itineraries/{itinerary_id}/edit` : `add`, `move`, `replace`, `delete`로 한 턴만 수정하며 **다른 일정은 유지**. 제약을 위반하면 HTTP 409, 기존 일정 유지.

검증/저장 요청 예시 (평일 식당 두 곳, 날짜는 예시이며 GTFS에서 2026 운행을 지원해야 함):

```json
{
  "visits": [
    {
      "visit_id": "lunch",
      "place_id": "250103468",
      "start_at": "2026-11-10T12:00:00+09:00",
      "mode_from_previous": "WALK"
    },
    {
      "visit_id": "dinner",
      "place_id": "1348213630",
      "start_at": "2026-11-10T18:00:00+09:00",
      "mode_from_previous": "TRANSIT"
    }
  ]
}
```

`mode_from_previous`는 **이전 장소에서 이 장소까지** 이동수단입니다. 첫 방문에서는 사용되지 않습니다. `duration_minutes`를 생략하면 엑셀의 최소 체류시간을 사용합니다. 식당은 기본적으로 점심 11:00~15:00 또는 저녁 17:00~20:00 안에 체류해야 하며, 유저가 시간을 명시했을 경우 `explicit_time_override: true`로 **기본 식사시간 제한만** 해제할 수 있습니다. 실제 영업시간은 여전히 준수해야 합니다.

예: `trip-1`에 방문 하나만 생성한 다음 새 방문 추가 (Swagger에서 편하게 테스트)

```http
PUT /itineraries/trip-1
```

```json
{"visits":[{"visit_id":"lunch","place_id":"250103468","start_at":"2026-11-10T12:00:00+09:00"}]}
```

```http
POST /itineraries/trip-1/edit
```

```json
{"action":"add","visit_id":"dinner","place_id":"1348213630","start_at":"2026-11-10T18:00:00+09:00","mode_from_previous":"TRANSIT"}
```

다음의 같은 endpoint로 기존 일정 수정/삭제:

```json
{"action":"move","visit_id":"dinner","start_at":"2026-11-10T19:00:00+09:00"}
```

```json
{"action":"delete","visit_id":"dinner"}
```

## 문제 해결

| 증상 | 원인/해결 |
|---|---|
| `GET /health`는 정상, `/ready`는 503 | 좌표 2개 이상 + GraphHopper 실행 필요 |
| `409 missing_coordinates` | `python -m scripts.enrich_kakao_coordinates` 실행 또는 직접 좌표 입력. 이후 API 재시작 |
| `502 GraphHopper ...` | 포트 8989 서버 미기동, GraphHopper 설정/GTFS 오류 |
| `profile=pt` 오류 | 도보 전용 엔진 실행 중. 실제 GTFS 확인 후 `--transit`으로 재시작 |
| 경로를 못 찾음 | 데이터 날짜 범위 밖, OSM 클립 범위 밖, 보행망 단절, GTFS 노선 부족 등 확인 |
| `409 insufficient_travel_time` | 두 방문 사이에 실제 이동시간이 부족. TripEdit 요청을 자동 승인하지 않음 |
| 변경한 `places.csv`가 API에 안 보임 | `uvicorn` 프로세스 재시작 필요 |

**완성 상태 요약:** Python API+일정 검증·수정 코드 및 테스트는 완성되어 있습니다. 실제 부산 좌표, OSM, GTFS는 사용자 PC에서 준비해야 하며, 그 전에는 도보·대중교통 실경로를 성공했다고 주장할 수 없습니다.

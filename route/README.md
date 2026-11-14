# 도보·대중교통 Route API

## 데이터

```
dataset/
├── gtfs/                   # 대중교통 데이터
│   ├── agency.txt          # 운영 기관
│   ├── calendar.txt        # 운행 요일·기간
│   ├── routes.txt          # 노선
│   ├── stop_times.txt      # 정류장별 도착·출발 시각
│   ├── stops.txt           # 정류장
│   ├── transfers.txt       # 환승 규칙
│   └── trips.txt           # 노선별 운행 편
└── osm/                    # 지도 데이터
    └── korea.osm.pbf
```

- OSM 데이터: https://download.geofabrik.de/asia/south-korea-latest.osm.pbf
- GTFS 데이터: https://www.ktdb.go.kr/www/contents.do?key=202 
             -> 교통분석자료 신청 
             -> Step 01. 교통망 GIS DB - 지역좌표계, 대중교통
             -> Step 02. 전국
             -> Step 03. 2026
             -> Step 04. 대중교통GTFS(2025년 기준)

## 설치 및 실행

```bash
cd route
./setup.sh
./graphhopper.sh
```

다른 터미널에서:

```bash
cd route
./run.sh
```

- API 문서: http://127.0.0.1:8001/docs
- GraphHopper 지도: http://127.0.0.1:8989/maps/
- 대중교통 지도: http://127.0.0.1:8989/maps/pt/

## 이동 시간 조회

```bash
curl -X POST http://127.0.0.1:8001/routes \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": {"lat": 37.5665, "lon": 126.9780},
    "destination": {"lat": 37.5547, "lon": 126.9707},
    "departure_time": "2026-11-14T09:00:00",
    "max_solutions": 3,
    "include_geometry": false
  }'
```

## 이동 시간 조회 결과

| 필드 | 의미 |
|---|---|
| `kind` | `walk` / `transit` (대중교통 탐색에도 도보만 있는 대안이 반환될 수 있음) |
| `duration_seconds` / `duration_minutes` | GraphHopper 경로 시간(ms)을 초/분으로 변환한 값 |
| `distance_meters` | 전체 이동 거리. 승차 거리 정보가 부족하면 `null` |
| `distance_is_complete` | 모든 승차 구간의 거리 정보가 제공되는지 여부 |
| `walking_distance_meters` | 도보 이동 거리 |
| `walking_seconds` | 도보 구간 시간의 합 |
| `transfers` | 실제 환승 횟수, 도보 경로는 0 |
| `departure_time` / `arrival_time` | 대중교통 탐색 결과의 실제 출발·도착 시각 |
| `elapsed_seconds_from_request` | 요청한 출발 시각부터 도착까지의 시간 (출발 전 대기까지 포함) |
| `legs` | 도보·승차 구간, 노선 ID, 정류장 등 GraphHopper 정보 |
| `geometry` | `include_geometry=true`일 때 전체 경로 좌표(GeoJSON) |

- 도보 전용 경로는 90분 이하만 반환

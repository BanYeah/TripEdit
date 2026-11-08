# TripEdit — 부산 OSM/GTFS 자체 길찾기 + 일정 검증 API (v0.2)

**먼저 [QUICKSTART_UBUNTU.md](QUICKSTART_UBUNTU.md)를 읽으세요.** 사용자의 Linux/Conda 설치 경로 `/home/doojinyang/workspace/busan_tripedit_route_api`를 기준으로 작성했습니다.

## 무엇이 구현되어 있나?

이 소스는 사용자가 제공한 `TripEdit-Places.xlsx`의 `restaurant` 탭 **50곳만** 사용합니다. source workbook 자체도 `data/TripEdit-Places.xlsx`에 포함했습니다.

```text
TripEdit 클라이언트/에이전트
  ├─ GET /places                           (식당 50곳 + 운영시간/체류시간)
  ├─ GET /travel-time                      (WALK / TRANSIT)
  ├─ POST /itineraries/validate            (일정 검증)
  ├─ PUT /itineraries/{id}                 (유효한 일정만 저장)
  ├─ GET /itineraries/{id}                 (일정 조회)
  └─ POST /itineraries/{id}/edit           (멀티턴 수정: add/replace/move/delete)
                    │
                 FastAPI
                    ├─ CSV 식당 장소 데이터 + 운영시간 JSON
                    ├─ SQLite 경로캐시 / 일정 DB
                    └─ GraphHopper REST /route (localhost:8989)
                              ├─ OSM: 도보 이동시간
                              └─ GTFS: 대중교통 이동시간 (유효한 운행날짜 필요)
```

### 1~5단계 결과

| 단계 | 코드 구현 여부 | 실 데이터/운영 상태 |
|---|---|---|
| 1. 부산 식당 데이터 읽기 | **구현 / 테스트** | 원본 식당 50곳 모두 로드. 카카오 ID·운영시간·최소 체류시간 유지 |
| 2. 위경도 연결 | **정확한 카카오 ID로만 매칭하는 도구 구현** | 원본에는 좌표 0개. 카카오 REST API 키로 좌표 조회 필요 |
| 3. OSM 도보 경로 엔진 | **다운로드·클립·시작 스크립트 구현** | 사용자의 PC에서 OSM 다운로드/GraphHopper 첫 빌드 필요 |
| 4. GTFS 대중교통 경로 | **GraphHopper PT 어댑터/검증/실행 구현** | 유효한 부산 GTFS가 없어 실경로 미검증 |
| 5. TripEdit 일정 연결 | **검증·저장·한 턴 수정 API 구현** | LLM 자연어 파서는 미연결. TripEdit 에이전트에서 이 API를 호출하도록 연동 필요 |

가짜 시간이나 대체 거리 계산으로 정상인 척하지 않습니다. 실제 길찾기는 `data/places.csv`의 좌표와 GraphHopper 그래프가 준비된 뒤 가능합니다. 현재 ZIP에는 사용자의 시스템에서 실행하는 지도/GTFS 데이터(대용량)를 포함하지 않았습니다.

### 운영시간 데이터에 관하여

`opening_hours`는 **업로드된 엑셀에 들어 있던 JSON을 그대로 보존**했습니다. 카카오맵 최신 영업시간을 재확인한 데이터가 아닙니다. 구간은 `[개점, 폐점]`이며 브레이크타임은 구간으로 분할, `[]`는 휴무입니다. 밤샘은 `['22:00','02:00']`처럼 다음 날 종료로 처리합니다.

### API semantics

- 식당은 기본 점심(11~15) 또는 저녁(17~20)에 방문, 하루 각 시간대 최대 1곳.
- `duration_minutes`를 생략하면 엑셀 `min_duration` 사용. 사용자 명시 체류시간은 기본 최소 체류시간보다 우선.
- `explicit_time_override=true`는 기본 점심/저녁 규칙만 우회; 실제 영업시간은 필수.
- 전후 방문의 시간 중복과 경로 이동시간을 검사. 같은 날 `mode_from_previous` 기준 GraphHopper 호출, 다른 날짜 간 이동은 자동 검증하지 않음.
- 불가능한 일정은 저장하지 않고 `409` 오류로 반환. 기존 방문은 허가된 ID만 변경 가능.
- 대중교통 경로는 날짜·출발시각 필수. 버킷이 필요한 경우 요청시각을 올림하고 그 대기시간을 이동시간에 더해, 먼저 출발한 차를 탈 수 있는 것처럼 계산하지 않습니다. 경로 캐시는 **시간·이동수단·방향·장소 좌표·데이터 버전**을 구분합니다.
- Python FastAPI와 GraphHopper 엔진은 서로 다른 프로세스(포트 8000 / 8989)입니다.

### 출처와 참고문서

- 요청자 제공 `TripEdit-Places.xlsx` — restaurant 시트
- 요청자 제공 `벤치마크 구축 초안.pdf` — 일정 생성/수정, 이동시간 제약, 식당 기본 방문시간 등
- https://klaus9267.tistory.com/50 — OTP + OSM + GTFS
- https://klaus9267.tistory.com/51 — GraphHopper + GTFS
- https://github.com/graphhopper/graphhopper — 자체 운영 경로 탐색 엔진
- https://developers.kakao.com/docs/ko/kakaomap/rest-api — Kakao Local API / 장소 검색/좌표
- https://download.geofabrik.de/asia/south-korea-latest.osm.pbf — OSM 원본
- https://www.ktdb.go.kr/ — 대한민국 대중교통 GTFS 기반정보 자료신청 등

OSM ODbL 표시/배포 조건, 카카오/KTDB 이용 약관, GTFS 자료 라이선스를 준수하세요. 상용 배포 전에는 GTFS의 실제 운행일 범위 및 부산 도보·대중교통 시간 오차를 검증해야 합니다.

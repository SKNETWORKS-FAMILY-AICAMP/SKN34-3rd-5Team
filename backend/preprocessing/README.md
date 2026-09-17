# preprocessing (전처리)

원본/크롤링 결과를 가공·구조화하는 스크립트만 둠 (결과물은 없음 — 실행하면 ../data/preprocessed/에 저장됨).

- parse_ticket_policy.py
- kbo_schedule_postseason_placeholder.py
- team_stadium_map.py (팀·구장 코드 정규화 모듈 — 매핑표 원본은 ../data/raw/team_stadium_code_map.csv)
- normalize_new_supplements.py (2026-09-08 추가. 팀원 보완자료 2종의 stadium_id를 표준 stadium_code로 정규화 — 편의시설 통합.xlsx의 stadium_id가 INCHEON_SSG/DAEJEON_HANWHA처럼 "지역_팀명" 형태라 team_stadium_code_map.csv 기준 코드와 안 맞았음. 실행하면 data/preprocessed/구장편의시설.csv, 구장편의시설_보류이력.csv, 구장잔여정보_좌석주차버스.csv 3개 생성)
- normalize_food_stores.py (2026-09-08 추가, 같은 날 밤 최종 갱신. `data/raw/구장먹거리,컨텐츠.xlsx`의 Food Stores(284건)·Attractions(68건) 두 시트를 CSV로 전처리 — 이 파일만 다른 원본들과 달리 raw 상태로 방치돼 있던 걸 오늘 전처리 마감 점검 중 발견해서 처리함. Evidence Type이 OFFICIAL_GUIDE_MAP처럼 세분화된 값이라 프로젝트 공통 evidence_type 어휘에 맞게 `OFFICIAL`로 정규화하고 원래 값은 `evidence_subtype`에 보존. 실행하면 data/preprocessed/구장먹거리_공식매점.csv, 구장부가콘텐츠_공식.csv 2개 생성. 원본 xlsx가 로컬에서 Excel로 열려있어도 읽기 전용이라 문제없이 실행됨. **최종 갱신**: `apply_daejeon_deoban_enrichment()` 오버레이 추가 — 팀원 3차 재검증(`backlog 보충.xlsx`)에서 확보한 더본코리아 대전 입점 8개 브랜드 실명을 반영해 기존 요약 행 1개를 개별 8행으로 확장(284→291행))
- normalize_ticket_prices.py (2026-09-08 밤 추가. `data/raw/구장정보.xlsx`의 Ticket Prices 시트(10구단 740행) — 지금까지 Facilities 시트만 쓰고 나머지 16개 시트는 미처리 상태였던 걸 발견해서 처리 시작. 좌석 등급명이 팀마다 이름형/색상형/티어형으로 달라 표준화하지 않고 원본 필드 그대로 옮김. NC 50행은 특정 경기 1건의 동적가격 스냅샷, PARTIAL 5행은 단가 단위 불명확, `price_krw=0`인 4행은 무료 요금(정상) — 상세는 스크립트 docstring과 data/preprocessed/README.md 참고. 실행하면 data/preprocessed/구장티켓가격.csv 생성)
- normalize_transport.py (2026-09-08 밤 추가, 같은 날 밤 2차·3차·4차 갱신. 같은 `구장정보.xlsx`의 Transport 시트(9개 구장 37행, 지하철·버스·주차·셔틀). 기존 normalize_new_supplements.py 결과물인 구장잔여정보_좌석주차버스.csv(3개 구장, 지하철 없음)와는 겹치는 3개 구장(대전·광주·대구)에서 수치가 달라 병합하지 않고 별도 파일로 유지하기로 결정 — 상세 우선순위 규칙은 스크립트 docstring 참고. 2차 갱신에서 `apply_manual_research_enrichment()` 오버레이 함수를 추가해 브라우저 보완 조사 결과(대구 지하철역명 정정, 창원 셔틀 2026 운영 확정, 대구·인천·사직·수원·창원 신규 5행)를 반영 — 37행→42행. 대구 주차 수용면(1,117면)도 위키백과+언론 교차확인으로 RECHECK→CONFIRMED 최종 확정(스크립트 docstring 참고). 3차 갱신은 팀원 3차 재검증(`backlog 보충.xlsx`) 반영 — GOCHEOK 주차 details에 전기차충전소 문구 추가, DAEJEON 지하주차장(한화생명볼파크 본구장) 신규 행 추가로 42행→43행. 4차 갱신은 청킹 검토 중 나온 지적 반영 — DAEJEON 지하주차장 행이 단독으로 검색돼도 완결된 답이 나오도록 총 수용면(1,679면=지하 1,220면+지상 459면, 구장잔여정보_좌석주차버스.csv 기준) 문구를 details에 직접 포함하고 parking_spaces=1220도 채움(행 수 변동 없음). 실행하면 data/preprocessed/구장교통정보.csv 생성)
- normalize_seat_zones.py (2026-09-08 밤 3차 추가. 같은 `구장정보.xlsx`의 Seat Zones 시트(10구단 192행, 좌석 구역 상세) — Ticket Prices와 같은 이유로 등급명(zone_code/zone_name_ko)을 표준화하지 않고 원본 필드 그대로 옮김. `level`/`side`/`group_size` 결측은 원본에 애초에 없는 값(해당 없음)이라 정상. PARTIAL 2행(삼성 대구, KIA 광주)은 원본 `description` 필드로 사유가 이미 설명됨. 실행하면 data/preprocessed/구장좌석구역.csv 생성)
- normalize_official_extras.py (2026-09-08 밤 최종 추가. "총정리" 감사 중 발견한 `구장정보.xlsx`의 마지막 미처리 시트 3개 — Seat Experience(8행)/Operations(9행)/Seat Maps(10행) — 를 처리. 값 표준화 없이 원본 그대로 옮김, 전부 CONFIRMED/OFFICIAL. 실행하면 data/preprocessed/구장좌석경험.csv, 구장운영정보.csv, 구장좌석도.csv 3개 생성)
- build_backlog_findings_ref.py (2026-09-08 밤 최종 추가. 팀원 3차 재검증 문서 `data/raw/backlog 보충.xlsx`의 `신규확보데이터` 시트(14건, 이번 총정리 감사 중 처음 발견)를 그대로 옮긴 참조 테이블 생성 — 기존 CSV 스키마와 안 맞는 항목(팀 정책·시즌권 등)도 유실 없이 보존하고 `incorporation_status` 컬럼으로 실제 반영 여부를 추적. 실행하면 data/preprocessed/3차_신규확보데이터.csv 생성. 상세 반영 내역은 data/preprocessed/README.md "총정리 감사에서 발견한 최종 누락분 처리" 섹션 참고)

## 실행

Python 의존성은 `backend/pyproject.toml`에서 공통 관리합니다. 프로젝트 루트에서 실행합니다.

```bash
uv sync --project backend --locked
uv run --project backend --locked python preprocessing/parse_ticket_policy.py
uv run --project backend --locked python preprocessing/kbo_schedule_postseason_placeholder.py
```

- 예매정책 파서는 `data/raw/kbo_ticket_policy.csv`를 읽어 `data/preprocessed/kbo_ticket_policy_structured.csv`를 갱신합니다.
- 포스트시즌 스크립트는 `data/preprocessed/kbo_schedule_postseason_tbd.csv`를 갱신합니다. 참가팀 미정인 참고 일정이며 확정 경기 데이터가 아닙니다.

[전체 실행 안내](../README.md) · [결과 데이터](../data/preprocessed/README.md)

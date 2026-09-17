# crawling (크롤링)

API·웹에서 데이터를 직접 긁어오는 스크립트만 둠 (결과물은 없음 — 실행하면 ../data/preprocessed/에 저장됨).

패키지는 `../backend/pyproject.toml`과 `../backend/uv.lock`으로 통일합니다. 프로젝트 루트에서 실행:

```bash
uv sync --project backend --locked
uv run --project backend --locked python crawling/kbo_standing.py
uv run --project backend --locked python crawling/kbo_schedule.py
uv run --project backend --locked python crawling/collect_kakao_places.py
```

카카오 수집은 루트 `.env`의 `KAKAO_REST_API_KEY`가 필요합니다. 실행 시 결과 CSV가 갱신됩니다.

| 스크립트 | 역할 | 결과 파일 (`data/preprocessed/`) |
| --- | --- | --- |
| `kbo_standing.py` | TVING API 순위 수집 | `kbo_standing.csv`, `kbo_standing_history.csv` |
| `kbo_schedule.py` | TVING API 경기 일정 수집 | `kbo_schedule_full.csv` |
| `collect_kakao_places.py` | 카카오 API 구장 좌표·주변 장소 수집 | `stadium_coordinates.csv`, `external_places.csv` |

## 기존 예약 작업 사용 시

Windows 작업 스케줄러 등에 과거 이름 `kbo_standing_crawler.py`, `kbo_schedule_full_crawler.py`가 남아 있다면 현재 파일명과 uv 환경으로 변경합니다.

[전체 실행 안내](../README.md) · [결과 데이터](../data/preprocessed/README.md)

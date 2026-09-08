# preprocessing (전처리)

원본/크롤링 결과를 가공·구조화하는 스크립트만 둠 (결과물은 없음 — 실행하면 ../data/preprocessed/에 저장됨).

- parse_ticket_policy.py
- kbo_schedule_postseason_placeholder.py
- team_stadium_map.py (팀·구장 코드 정규화 모듈)

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

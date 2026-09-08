# data/preprocessed

크롤링·전처리 스크립트의 생성 결과입니다. 프로젝트 루트의 `crawling/`, `preprocessing/` 스크립트 실행 시 갱신됩니다.

- kbo_standing.csv — kbo_standing.py가 실행할 때마다 덮어쓰는 최신 순위 스냅샷
- kbo_standing_history.csv — 같은 스크립트가 날짜별로 계속 누적하는 이력
- kbo_schedule_full.csv — kbo_schedule.py 결과 (3~10월 전체, 스코어 포함)
- kbo_schedule_postseason_tbd.csv — kbo_schedule_postseason_placeholder.py 결과 (참가팀 미정, TBD)
- kbo_ticket_policy_structured.csv — parse_ticket_policy.py 결과 (예매정책 구조화)
- stadium_coordinates.csv / external_places.csv — collect_kakao_places.py 결과 (카카오 API)

카카오 CSV를 최종 배포용 엑셀로 만드는 후처리는 아직 자동화되지 않았습니다.
포스트시즌 TBD는 미확정 참고 일정입니다. 순위·일정은 각 파일의 수집 시점 기준으로 해석합니다.

[데이터 관리 기준](../README.md) · [수집 실행](../../crawling/README.md) · [전처리 실행](../../preprocessing/README.md)

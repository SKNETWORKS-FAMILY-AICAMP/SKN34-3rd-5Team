# 채팅 Stop·게스트 통합 구현 보고

## 결과

- 회원 SSE는 DB에 pending turn만 만들고, 빈 prefix부터 각 누적 prefix까지 회원·session·turn·길이·SHA-256 digest를 묶은 서버 서명 receipt를 보냅니다.
- 완료 또는 명시적 Stop 뒤 별도 finalize가 receipt를 검증하고 질문과 비어 있지 않은 assistant prefix를 한 번만 저장합니다. Stop은 같은 turn의 완료 경합에서만 우선하며, 뒤 메시지가 생긴 완료 turn은 수정하지 않습니다.
- 게스트 SSE는 요청 body의 제한된 `user`/`assistant` 기록만 모델에 전달하고 chat DB나 브라우저 저장소에 쓰지 않습니다. 로그인 상태 확인 실패는 게스트로 강등하지 않습니다.
- Nginx 설정은 변경하지 않았습니다. Compose backend만 Nginx가 덮어쓴 `X-Real-IP`를 신뢰하며, 서명키는 필수 `CHAT_CHECKPOINT_SIGNING_KEY`로 분리했습니다.

## 변경 파일

- backend: `config/settings.py`, `config/urls.py`, `llm/models.py`, `llm/migrations/0004_chatturn_chatmessage_status.py`, `llm/chat_message_histories.py`, `llm/chat_service.py`, `llm/views.py`, `llm/tests.py`
- frontend: `lib/chat/client.ts`, `lib/chat/types.ts`, `components/chat-provider.tsx`, `components/chat-popup.tsx`, `components/chat-workspace.tsx`, `tests/chat-direct.test.mjs`, `README.md`, `docs/CHAT_SETUP.md`
- runtime examples: `.env.example`, `docker-compose.yml`
- 이전 MVP에서 이미 변경돼 있던 `frontend/app/layout.tsx`, `frontend/package.json` 변경은 보존했습니다.

## 검증

- 현재 소스를 실행 중인 `chatbot-integration-qa` backend의 격리된 `/tmp` 복사본에서 `python manage.py test llm --verbosity 1`: 15/15 통과
- 같은 pinned Django 6.1.1 runtime에서 `python manage.py makemigrations --check --dry-run`: 변경 없음
- `npm test`: 261/261 통과
- `npm run test:chat`: 46/46 통과
- `npx next typegen && npx tsc --noEmit`: 통과
- 변경 파일 대상 ESLint: 통과
- Next.js 16.3.4 `npm run build`: 통과, 34개 정적 페이지 생성
- `docker compose config --quiet`, `git diff --check`, `nginx/nginx.conf` exact-unchanged gate: 통과
- `npm ci`: audit 취약점 0건, 지원 종료된 ESLint 9.39.5 deprecation 경고 1건

첫 `docker compose run` 검증은 shell의 기존 `DB_PORT=5433`을 가져와 내부 PostgreSQL 접속이 거절됐습니다. 서비스 장애나 코드 실패가 아니며, 실행 중인 scoped backend의 실제 DB 환경을 사용한 격리 복사본 검증으로 다시 실행해 통과했습니다. 컨테이너 rebuild·migration·브라우저 E2E는 coordinator QA 범위로 남겼고, 커밋·Push·PR·Merge는 수행하지 않았습니다.

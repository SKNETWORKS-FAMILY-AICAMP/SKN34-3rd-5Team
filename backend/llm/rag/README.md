# llm/rag — KBO 직관 안내 RAG (도메인 분리 구조)

2026-09-14 · 담당: club = 형준, venue = 현준

## 구조

```
llm/
├─ rag_views.py          POST /chat/  ← 프론트(Next 서버) 중계 진입점. 계약: {messages, context} → {reply}
└─ rag/
   ├─ dispatcher.py      안내데스크. 질문을 보고 club / venue / 둘 다 / 범위 밖 으로 나눔 (LLM 0회)
   ├─ persona.py         말투 규칙 + 후처리(soften/clean). ★ 두 도메인이 같이 쓰는 유일한 공통 파일
   ├─ club/              구단·야구: 순위·일정·가격·예매·좌석·반입·재입장·규칙   — 형준만 수정
   │    agent.py         진입점 answer() · 가드 · 검색 조합 · LangChain ChatOpenAI 호출 · 후처리
   │    router.py        구장·팀 별칭, 카테고리 키워드 (rag_test/router.py 와 동일)
   │    retrieval.py     임베딩 · pgvector 검색 · 키워드 재정렬
   │    structured.py    순위·일정 DB 직접 조회 (LLM 0회)
   │    prompts.py       내용 규칙 · few-shot · 고정 문구
   └─ venue/             구장 안팎: 먹거리·시설·교통·포토존·주변  — 현준만 수정
        agent.py         틀만 있음 (READY=False). test.py 를 여기로 옮긴다
        prompts.py       내용 규칙 틀 (말투는 persona 에서 가져옴)
```

## 두 도메인이 지키는 약속 (이것만 맞으면 안은 자유)

```python
READY: bool                                   # False 면 디스패처가 이 도메인으로 안 보냄
def answer(question: str, history: list[dict] | None, hint_stadium: str | None) -> dict:
    return {"answer": str, "sources": list[dict], "route": str}
```

- `history`: `[{"role": "user"|"assistant", "content": str}, ...]` 이번 질문 제외, 오래된 것부터
- `hint_stadium`: 프론트에서 고른 구장 코드(`JAMSIL` 등) 또는 None
- `sources[i]`: `{"doc_id", "grade", "category", "stadium", ...}` — grade 는 OFFICIAL / UNCERTAIN / UNOFFICIAL / THIRD_PARTY

## 질문이 흐르는 길

```
프론트 /chat-api → Next 서버 → POST backend:8000/chat/ (rag_views.ChatView)
   → rag.answer(question, history, stadium_name)
   → dispatcher.route()   "scope" | "venue" | "club" | "both"
       scope : 야구 무관 → 고정 문구
       venue : venue.READY 면 venue.answer, 아니면 club.answer
       club  : club.answer
       both  : 둘 다 부르고 이어 붙임 (LLM 최대 2회)
   → persona.finalize()   말투 통일 후처리
   → {"reply": ...}
```

## 규칙

1. **자기 폴더만 고친다.** club/ 은 형준, venue/ 는 현준. 상대 폴더는 PR 리뷰로만.
2. 말투를 바꾸고 싶으면 `persona.py` — 두 도메인에 동시에 적용된다. 바꾸기 전에 팀 채널에 한 줄.
3. 디스패처 키워드(`VENUE_WORDS`·`CLUB_WORDS`)는 "어느 도메인이냐"만 정한다. 카테고리 세부 사전은 각자 폴더 안에.
4. LLM 은 `langchain_openai.ChatOpenAI` (팀 기준). 모델은 `LLM_MODEL` 환경변수 (기본 gpt-5.6-luna).
5. 임베딩 모델은 `EMBEDDING_MODEL` — 적재(build_index) 때와 같아야 한다.

## 로컬 실행

```bash
# 1. DB 에 청크가 있어야 한다 (3,839건). 없으면:
docker compose exec backend python manage.py build_index

# 2. 백엔드 기동 (compose 가 migrate + runserver)
docker compose up -d --build backend

# 3. 직접 호출
curl -X POST http://localhost:8000/chat/ -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"잠실 주차 얼마야?"}]}'
# → {"reply": "...", "sources": [...], "route": "club>rag:JAMSIL:TRANSPORT"}

# 4. 프론트 연결: frontend/.env.local
CHAT_PROVIDER=backend
CHAT_BACKEND_URL=http://backend:8000/chat/      # 컨테이너 안에서 Django 직접 호출 (Nginx 안 거침)
# 바꾼 뒤 프론트 컨테이너 재시작 → 화면에서 질문
```

`route` 값으로 어느 길로 갔는지 바로 알 수 있다 (`structured` = 순위·일정 직접조회, `guard:clarify` = 되묻기, `venue(not ready)>club>…` = venue 준비 전이라 club 이 대신 답함).

## 평가

`rag_test/`(step4·step5)는 그대로 채점 도구로 쓴다. club 로직을 여기서 고치면 `rag_test/`의 같은 파일(router·structured·chain)도 맞춰 둔다 — 지금은 수동 동기화(4차에서 rag_test 가 이 패키지를 import 하도록 정리 예정).

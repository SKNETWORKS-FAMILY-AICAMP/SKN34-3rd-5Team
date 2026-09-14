"""[venue] 구장 안팎 도메인 — 먹거리·편의시설·교통·포토존·주변 맛집 (담당: 현준)

이 파일은 틀만 있다. rag_test 에서 만든 test.py(LangChain Agent + search_documents_tool)를
여기로 옮기면 된다. 옮기는 동안은 READY = False 로 두면 디스패처가 구장 질문도 club 으로 보낸다.

디스패처와의 약속 (이것만 지키면 안은 자유):
    READY: bool
    answer(question: str, history: list[dict] | None, hint_stadium: str | None) -> dict
        반환 {"answer": str, "sources": list[dict], "route": str}
        - history: [{"role": "user"|"assistant", "content": str}, ...] 이번 질문 제외
        - hint_stadium: 프론트에서 고른 구장 코드 (JAMSIL·GOCHEOK·MUNHAK·SUWON·DAEJEON·DAEGU·GWANGJU·SAJIK·CHANGWON) 또는 None
        - sources 항목 예: {"doc_id": ..., "grade": "OFFICIAL|UNCERTAIN|UNOFFICIAL|THIRD_PARTY", "category": ..., "stadium": ...}

test.py 를 옮길 때 바꿀 것:
    1. DB: psycopg2 ThreadedConnectionPool 대신 django.db.connection 사용
       (club/retrieval.py 의 search() 를 참고. 그대로 import 해서 써도 되고, 자기 것으로 만들어도 됨)
    2. 범위 밖 차단(EXCLUDED_QUERY_TERMS · "다른 Search Agent 담당")은 삭제 — 순위·일정·티켓은 디스패처가 club 으로 보낸다
    3. 프롬프트: prompts.py 에서 내용 규칙은 자기 것, 말투는 ../persona.TONE_RULES 를 붙인다
    4. LLM 은 langchain_openai.ChatOpenAI (팀 기준). Agent(create_agent) 방식 유지해도 된다
    5. 근거 등급: 자리어때(UNOFFICIAL)·카카오(THIRD_PARTY) 청크가 많으니 club/agent.grade() 와 같은 기준으로 sources 에 grade 를 넣는다
"""
from .prompts import SYSTEM  # noqa: F401  (프롬프트 틀 — 아래 answer() 에서 사용)

READY = False          # test.py 이식이 끝나면 True 로


def answer(question, history=None, hint_stadium=None):
    """현준 형이 채울 자리. READY=False 인 동안은 디스패처가 여기를 부르지 않는다."""
    raise NotImplementedError("venue 도메인은 아직 준비 중 — test.py 를 이 파일로 옮기세요")

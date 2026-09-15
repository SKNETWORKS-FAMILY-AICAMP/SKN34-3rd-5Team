"""RAG 가 제대로 붙었는지 한 번에 확인 — shell 에 붙여넣기 없이 한 줄로.

    docker compose exec backend python manage.py rag_check
    docker compose exec backend python manage.py rag_check -q "잠실 코스 짜줘"
    docker compose exec backend python manage.py rag_check --course    # 코스 추천까지 확인

확인 항목
    1) 환경변수   CHAT_USE_RAG · LLM_MODEL · EMBEDDING_MODEL · LANGSMITH_*
    2) 스위치     use_rag() / chat_chain() — 지금 챗봇이 RAG 로 도는지
    3) 인덱스     llm_documentchunk 건수 (0 이면 build_index 필요)
    4) 실제 호출  질문 하나를 끝까지 태워 본다 (reasoning_effort 등 모델 파라미터 검증 포함)
"""
import os
import time

from django.core.management.base import BaseCommand
from django.db import connection

MASK = ("API_KEY", "PASSWORD", "SECRET", "SIGNING")


def show(k):
    v = os.getenv(k)
    if v is None:
        return "(없음)"
    if any(m in k for m in MASK):
        return f"설정됨 ({len(v)}자)" if v else "(빈 값)"
    return v or "(빈 값)"


class Command(BaseCommand):
    help = "RAG 연결 상태를 점검한다 (환경변수 · 스위치 · 인덱스 · 실제 호출)"

    def add_arguments(self, parser):
        parser.add_argument("-q", "--question", default="LG 지금 몇 위야?")
        parser.add_argument("--course", action="store_true", help="코스 추천 질문으로 확인")
        parser.add_argument("--stadium", default=None, help='예: "잠실야구장"')

    def handle(self, *a, **o):
        ok, ng = self.style.SUCCESS, self.style.ERROR
        p = self.stdout.write

        p("\n[1] 환경변수")
        for k in ("CHAT_USE_RAG", "LLM_MODEL", "EMBEDDING_MODEL",
                  "LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
            p(f"    {k:<20} {show(k)}")

        p("\n[2] 스위치")
        try:
            from llm.rag.pipeline import chat_chain, use_rag
        except Exception as e:
            p(ng(f"    pipeline import 실패: {e!r}"))
            return
        on = use_rag()
        p(f"    use_rag()            {ok('True  → RAG 로 답한다') if on else ng('False → 예전 helpful-assistant 체인')}")
        p(f"    chat_chain()         {type(chat_chain()).__name__ if chat_chain() else 'None'}")
        if not on:
            p("    (CHAT_USE_RAG=1 로 두고 backend 를 restart 하세요)")

        p("\n[3] 인덱스")
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT count(*) FROM llm_documentchunk")
                n = cur.fetchone()[0]
                cur.execute("SELECT metadata->>'category', count(*) FROM llm_documentchunk "
                            "GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
                rows = cur.fetchall()
            p(f"    청크 {ok(str(n)) if n else ng('0 — build_index 필요')} 건")
            for c, k in rows:
                p(f"      {c or '(없음)':<12} {k}")
        except Exception as e:
            p(ng(f"    DB 조회 실패: {e!r}"))

        p("\n[4] 실제 호출")
        q = "잠실에서 친구들이랑 첫 직관인데 경기 전후 코스 짜줘. 치킨 좋아해" if o["course"] else o["question"]
        p(f"    질문: {q}")
        try:
            from llm.rag.pipeline import answer
            t0 = time.perf_counter()
            r = answer(q, stadium_name=o["stadium"])
            ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            p(ng(f"    실패: {type(e).__name__}: {e}"))
            p("    (unsupported parameter 류면 ChatOpenAI 의 reasoning_effort 를 빼야 합니다)")
            return
        p(f"    route   {r.get('route')}")
        p(f"    소요    {ms:.0f}ms   timing={r.get('timing') or {}}")
        p(f"    근거    {len(r.get('sources') or [])}건")
        p(f"    답변    {r['answer'][:300]}")
        for pl in r.get("places") or []:
            p(f"      {pl.get('time','--:--')} [{pl['phase']:<6}] {pl['name']} ({pl['distance']}m)")
        if r.get("coursePayload"):
            cp = r["coursePayload"]
            p(f"    코스저장 payload: '{cp['title']}' · {cp['duration']} · stops {len(cp['stops'])}개")
        p(ok("\n  통과 — 챗봇이 RAG 로 답하고 있습니다\n") if on else "\n")

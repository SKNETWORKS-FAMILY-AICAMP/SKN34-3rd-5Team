"""KBO 직관 안내 RAG — 도메인별 분리 구조.

    from llm.rag import answer
    answer("잠실 주차 얼마야?", history=[...], stadium_name="잠실야구장")
    → {"answer": "...", "sources": [...], "route": "club>rag:JAMSIL:TRANSPORT"}

구조·규칙은 README.md 참고.
"""
from .dispatcher import answer, route  # noqa: F401

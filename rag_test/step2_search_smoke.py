"""STEP 2. 검색이 되나 + 필터 걸면 결과가 사라지나 (임베딩 호출 3회)
실행: python rag_test/step2_search_smoke.py
"""
from common import connect, count_candidates, embed, search

conn = connect()
questions = ["잠실 주차장 몇 면이야", "라팍 주차장 있어?", "고척돔 셔틀버스 시간표"]
vecs = dict(zip(questions, embed(questions)))


def show(q, **kw):
    rows, ms = search(conn, vecs[q], **kw)
    print(f"\n[{q}] {kw or '필터 없음'} → {len(rows)}개 {ms:.0f}ms")
    for r in rows:
        print(f"  {r['dist']:.3f} {r['stadium']} {r['category']:10s} {r['doc_id'][:45]:45s} | {r['content'][:40]}")


# A. 기본 검색 — 결과를 보고 메모
show("잠실 주차장 몇 면이야")                       # 전부 JAMSIL 인가?
show("라팍 주차장 있어?")                           # DAEGU 가 나오나? (별칭)
show("고척돔 셔틀버스 시간표")                       # 없는 데이터 → 무엇이 나오나 (거절 테스트 재료)

# B. 필터 + HNSW 함정 — 같은 질문을 ef_search 40 / 200 / 정확검색으로
q = "잠실 주차장 몇 면이야"
print("\n필터(JAMSIL+TRANSPORT) 통과 청크 수:", count_candidates(conn, "JAMSIL", ["TRANSPORT"]))
show(q, stadium="JAMSIL", categories=["TRANSPORT"], ef_search=40)
show(q, stadium="JAMSIL", categories=["TRANSPORT"], ef_search=200)
show(q, stadium="JAMSIL", categories=["TRANSPORT"], exact=True)

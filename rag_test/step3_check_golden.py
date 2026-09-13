"""STEP 3. 골든셋 검증 — 시험지가 맞게 만들어졌나 (OpenAI 호출 0회)
실행: python rag_test/step3_check_golden.py --golden golden_club.jsonl
"""
import argparse
import re

from common import add_golden_arg, connect, load_golden, resolve_dynamic
from router import detect_categories, detect_stadium

ap = argparse.ArgumentParser()
add_golden_arg(ap)
args = ap.parse_args()

conn = connect()
golden = load_golden(args.golden)
golden = resolve_dynamic(conn, golden)   # 순위처럼 매일 바뀌는 정답은 DB 에서 읽어 채운다
text = {r["doc_id"]: r["content"] for r in conn.execute(
    "SELECT metadata->>'doc_id' AS doc_id, content FROM llm_documentchunk").fetchall()}
norm = lambda s: re.sub(r"[\s,]", "", s)

problems = 0
for q in golden:
    hit = [d for d in text if any(re.fullmatch(p, d) for p in q["gold"])]
    if q["gold"] and not hit:
        problems += 1
        print("❌ gold 가 DB에 없음        ", q["id"], q["gold"])
    if q["expect"] == "answer" and q["must"] and hit:
        body = norm(" ".join(text[d] for d in hit))
        if not any(norm(m) in body for m in q["must"]):
            problems += 1
            print("⚠ must 가 정답 청크에 없음 ", q["id"], q["must"])
    got = detect_stadium(q["question"])
    if got != q["stadium"]:
        problems += 1
        print("✗ 라우터 구장 불일치        ", q["id"], q["question"], "기대", q["stadium"], "→", got,
              detect_categories(q["question"]))

print("\n거절 문항 키워드는 0건이어야 함")
for w in ["와이파이", "비밀번호", "타율", "환불", "선발", "가사", "2027", "치어리더", "유모차", "숙소"]:
    n = conn.execute("SELECT count(*) AS n FROM llm_documentchunk WHERE content ILIKE %s", (f"%{w}%",)).fetchone()["n"]
    print(f"  {w}: {n}")

print(f"\n[{args.golden}] {len(golden)}문항 검사, 문제 {problems}건")

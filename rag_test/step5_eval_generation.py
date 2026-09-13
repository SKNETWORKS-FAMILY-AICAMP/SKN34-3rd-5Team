"""STEP 5. 생성·환각 평가 G0/G1/G2 (월요일 성능 검증)
실행: python rag_test/step5_eval_generation.py --golden golden_club.jsonl --limit 10   # 동작·비용 확인
      python rag_test/step5_eval_generation.py --golden golden_club.jsonl              # 전체
      python rag_test/step5_eval_generation.py --golden golden_club.jsonl --modes G2   # G2만 다시
결과: rag_test/results/club/generation_<시각>.csv
"""
import argparse
import csv
import re
import time
from datetime import datetime

import numpy as np

from chain import answer
from common import LLM_MODEL, add_golden_arg, connect, embed, load_golden, resolve_dynamic, results_dir
from scoring import WARN, judge, number_check

ap = argparse.ArgumentParser()
add_golden_arg(ap)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--modes", default="G0,G1,G2")
args = ap.parse_args()

conn = connect()
golden = load_golden(args.golden, args.limit)
golden = resolve_dynamic(conn, golden)   # 순위처럼 매일 바뀌는 정답은 DB 에서 읽어 채운다
qvecs = embed([q["question"] for q in golden])
all_text = {r["doc_id"]: r["content"] for r in conn.execute(
    "SELECT metadata->>'doc_id' AS doc_id, content FROM llm_documentchunk").fetchall()}
gold_text = {q["id"]: " ".join(t for d, t in all_text.items() if any(re.fullmatch(p, d) for p in q["gold"]))
             for q in golden}  # G0 처럼 문맥이 없어도 숫자를 정답 청크와 대조하려고

print(f"모델: {LLM_MODEL} · [{args.golden}] {len(golden)}문항")
rows_out, summary = [], []
for mode in args.modes.split(","):
    labels, lat = [], []
    warn_need = warn_ok = warn_raw_ok = over_warn = official_n = nums_checked = nums_bad = 0
    for q, v in zip(golden, qvecs):
        t0 = time.perf_counter()
        r = answer(conn, mode, q["question"], v)
        total_ms = (time.perf_counter() - t0) * 1000
        lat.append(total_ms)

        label = judge(q, r["answer"])
        labels.append((q["expect"], label))
        evidence = gold_text[q["id"]] + " " + " ".join(
            (x["content"] + " " + str(x.get("updated_at") or "")) for x in r["rows"])   # 기준일도 근거로 인정
        checked, bad = number_check(r["answer"], evidence, q["question"])
        nums_checked += checked
        nums_bad += len(bad)

        if q["expect"] in ("answer", "correct") and label != "오거절":
            if q["grade"] in ("UNOFFICIAL", "UNCERTAIN"):
                warn_need += 1
                warn_ok += bool(WARN.search(r["answer"]))
                warn_raw_ok += bool(WARN.search(r["answer_raw"]))
            elif q["grade"] == "OFFICIAL":
                official_n += 1
                over_warn += bool(WARN.search(r["answer"]))

        rows_out.append({"mode": mode, "id": q["id"], "group": q["group"], "expect": q["expect"], "label": label,
                         "question": q["question"], "answer": r["answer"].replace("\n", " "), "guard": r["guard"],
                         "top5": " | ".join(x["doc_id"] for x in r["rows"]), "bad_numbers": " ".join(bad),
                         "retrieval_ms": round(r["retrieval_ms"]), "llm_ms": round(r["llm_ms"]),
                         "total_ms": round(total_ms)})
        print(f"  {mode} {q['id']} {label}")

    def rate(expects, lab):
        d = sum(e in expects for e, _ in labels)
        return round(sum(e in expects and l == lab for e, l in labels) / d, 3) if d else "-"

    pct = lambda n, d: round(n / d, 3) if d else "-"
    fact = sum(e in ("answer", "correct", "refuse") for e, _ in labels)
    p50, p95 = np.percentile(lat, [50, 95])
    summary.append({
        "mode": mode, "정답률": rate(("answer", "correct"), "OK"), "거절정확도": rate(("refuse",), "OK"),
        "오거절률": rate(("answer", "correct"), "오거절"), "되묻기": rate(("clarify",), "OK"),
        "환각률": pct(sum(l in ("오답", "전제동조", "지어냄") for _, l in labels), fact),
        "등급문구": pct(warn_ok, warn_need), "등급문구_프롬프트만": pct(warn_raw_ok, warn_need),
        "과잉경고": pct(over_warn, official_n), "숫자근거일치": pct(nums_checked - nums_bad, nums_checked),
        "P50ms": int(p50), "P95ms": int(p95),
    })

path = results_dir(args.golden) / f"generation_{datetime.now():%m%d_%H%M}.csv"
with open(path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
    w.writeheader()
    w.writerows(rows_out)

head = list(summary[0])
print("\n| " + " | ".join(head) + " |\n|" + " --- |" * len(head))
for s in summary:
    print("| " + " | ".join(str(s[h]) for h in head) + " |")
print(f"\n문항별 결과: {path}")

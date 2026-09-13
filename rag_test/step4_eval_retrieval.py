"""STEP 4. 검색 성능 평가 R0~R3 (LLM 호출 0회, 질문 임베딩은 캐시)
실행: python rag_test/step4_eval_retrieval.py --golden golden_club.jsonl                 # ef_search 40
      python rag_test/step4_eval_retrieval.py --golden golden_club.jsonl --ef-search 200  # 한 가지만 바꿔서
      python rag_test/step4_eval_retrieval.py --golden golden_club.jsonl --exact          # 정확 검색
결과: rag_test/results/club/retrieval_<설정>_<시각>.csv
"""
import argparse
import csv
from datetime import datetime

import numpy as np

from common import (add_golden_arg, connect, count_candidates, date_tokens, embed, keyword_rerank,
                    load_golden, results_dir, search)
from router import detect_categories, detect_stadium
from scoring import hit_at, mrr, rank_of

CONFIGS = {  # 위에서 아래로 한 가지씩만 더한다
    "R0_vector":   dict(stadium=False, category=False, hybrid=False, date=False),
    "R1_stadium":  dict(stadium=True,  category=False, hybrid=False, date=False),
    "R2_category": dict(stadium=True,  category=True,  hybrid=False, date=False),
    "R3_hybrid":   dict(stadium=True,  category=True,  hybrid=True,  date=False),
    "R4_date":     dict(stadium=True,  category=True,  hybrid=True,  date=True),   # 실제 G2 파이프라인
}

ap = argparse.ArgumentParser()
add_golden_arg(ap)
ap.add_argument("--ef-search", type=int, default=40)
ap.add_argument("--exact", action="store_true")
args = ap.parse_args()

conn = connect()
golden = load_golden(args.golden)
qvecs = embed([q["question"] for q in golden])

rows_out, summary = [], []
for name, cfg in CONFIGS.items():
    ranks, mix, times, alias_ok, lost = [], [], [], [], 0
    for q, v in zip(golden, qvecs):
        stadium = detect_stadium(q["question"]) if cfg["stadium"] else None
        cats = detect_categories(q["question"]) if cfg["category"] else None
        hits, ms = search(conn, v, k=30 if cfg["hybrid"] else 5, stadium=stadium,
                          categories=cats or None, ef_search=args.ef_search, exact=args.exact)
        if cfg["date"]:                     # 날짜가 든 청크는 벡터 순위와 무관하게 후보에 넣는다 (chain.py 와 동일)
            for d in date_tokens(q["question"]):
                extra, extra_ms = search(conn, v, k=5, stadium=stadium, categories=cats or None,
                                         ef_search=args.ef_search, exact=args.exact, must_text=d)
                ms += extra_ms
                have = {h["doc_id"] for h in hits}
                hits += [e for e in extra if e["doc_id"] not in have]
        if cfg["hybrid"]:
            hits = keyword_rerank(q["question"], hits, k=5)
        ids = [h["doc_id"] for h in hits]
        times.append(ms)
        lost += len(hits) < min(5, count_candidates(conn, stadium, cats or None))  # 있는데 못 가져옴

        rank = rank_of(ids, q["gold"]) if q["gold"] else None
        if q["gold"]:
            ranks.append(rank)
        if q["stadium"]:
            wrong = [h for h in hits if h["stadium"] not in (q["stadium"], None)]
            mix.append(len(wrong) / max(len(hits), 1))
        if q["group"] == "별칭" and cfg["stadium"]:
            alias_ok.append(stadium == q["stadium"])

        rows_out.append({"config": name, "id": q["id"], "group": q["group"], "question": q["question"],
                         "router_stadium": stadium or "", "router_categories": "|".join(cats or []),
                         "rank": rank or ("miss" if q["gold"] else ""), "n_results": len(hits),
                         "top5": " | ".join(ids), "ms": round(ms, 1)})

    p50, p95 = np.percentile(times, [50, 95])
    summary.append({"config": name, "Hit@1": round(hit_at(ranks, 1), 3), "Hit@5": round(hit_at(ranks, 5), 3),
                    "MRR": round(mrr(ranks), 3), "구장혼입률": round(float(np.mean(mix)), 3) if mix else "-",
                    "결과유실": lost, "별칭": f"{sum(alias_ok)}/{len(alias_ok)}" if alias_ok else "-",
                    "P50ms": int(p50), "P95ms": int(p95)})

tag = f"ef{args.ef_search}" + ("_exact" if args.exact else "")
path = results_dir(args.golden) / f"retrieval_{tag}_{datetime.now():%m%d_%H%M}.csv"
with open(path, "w", newline="", encoding="utf-8-sig") as f:        # 엑셀에서 한글 안 깨짐
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
    w.writeheader()
    w.writerows(rows_out)

head = list(summary[0])
print(f"[{args.golden}] {len(golden)}문항 · ef_search={args.ef_search} · exact={args.exact}")
print("| " + " | ".join(head) + " |\n|" + " --- |" * len(head))
for s in summary:
    print("| " + " | ".join(str(s[h]) for h in head) + " |")
print(f"\n문항별 결과: {path}")

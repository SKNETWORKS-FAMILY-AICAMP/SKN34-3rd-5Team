"""STEP 1. 적재 확인 — DB에 제대로 들어갔나 (OpenAI 호출 0회)
실행: python rag_test/step1_check_db.py
"""
from common import connect

conn = connect()
one = lambda sql: conn.execute(sql).fetchone()
many = lambda sql: conn.execute(sql).fetchall()

print("pgvector 버전 :", one("SELECT extversion AS v FROM pg_extension WHERE extname='vector'")["v"])
print("총 청크       :", one("SELECT count(*) AS n FROM llm_documentchunk")["n"], "(기대 3839)")
print("embedding NULL:", one("SELECT count(*) AS n FROM llm_documentchunk WHERE embedding IS NULL")["n"], "(기대 0)")
print("doc_id 중복   :", len(many("""SELECT metadata->>'doc_id' FROM llm_documentchunk
                                   GROUP BY 1 HAVING count(*) > 1""")), "(기대 0)")
print("인덱스        :", [r["indexname"] for r in many(
    "SELECT indexname FROM pg_indexes WHERE tablename='llm_documentchunk'")])

# 지문: DB를 다시 만들거나 팀원 DB와 비교할 때 이 두 값이 같으면 "완전히 같은 청크·같은 벡터"
fp = one("""SELECT md5(string_agg(metadata->>'doc_id' || content, '|' ORDER BY metadata->>'doc_id')) AS text_fp,
                   md5(string_agg(md5(embedding::text), '' ORDER BY metadata->>'doc_id'))       AS vec_fp
            FROM llm_documentchunk""")
print("텍스트 지문   :", fp["text_fp"])
print("벡터 지문     :", fp["vec_fp"])

print("\n카테고리별")
for r in many("SELECT metadata->>'category' AS k, count(*) AS n FROM llm_documentchunk GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {str(r['k']):14s}{r['n']:5d}")
print("\n구장별")
for r in many("SELECT metadata->>'stadium_code' AS k, count(*) AS n FROM llm_documentchunk GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {str(r['k']):14s}{r['n']:5d}")

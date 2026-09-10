"""원격 DB에 인덱스가 제대로 들어갔는지 확인 (읽기 전용, 임베딩 호출 없음).

python manage.py check_index            # 요약
python manage.py check_index --expect 3832
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from llm.models import Document, DocumentChunk


class Command(BaseCommand):
    help = "llm_documentchunk 적재 상태 점검"

    def add_arguments(self, parser):
        parser.add_argument("--expect", type=int, default=0, help="기대 청크 수 (차이 200 이상이면 경고)")

    def handle(self, *args, **o):
        w = self.stdout.write
        w(f"DB: {connection.settings_dict['HOST']}:{connection.settings_dict['PORT']}/{connection.settings_dict['NAME']}")
        total = DocumentChunk.objects.count()
        w(f"\n총 청크: {total}  (Document {Document.objects.count()}개)")
        if o["expect"] and abs(total - o["expect"]) >= 200:
            w(self.style.WARNING(f"  ⚠ 기대값 {o['expect']}과 {abs(total-o['expect'])} 차이"))

        rows = DocumentChunk.objects.values_list("metadata", flat=True)
        cat, src, sc_none = Counter(), Counter(), 0
        for m in rows:
            m = m or {}
            cat[m.get("category")] += 1
            src[m.get("source_file")] += 1
            if not m.get("stadium_code"):
                sc_none += 1
        w("\n카테고리별:")
        for k, v in sorted(cat.items(), key=lambda x: -x[1]):
            w(f"  {str(k):14s} {v:5d}")
        w("\n파일별:")
        for k, v in sorted(src.items(), key=lambda x: -x[1]):
            w(f"  {str(k):40s} {v:5d}")
        w(f"\nstadium_code 없음: {sc_none}  (정상: 5 = 반입 공통 1 + 기초규칙 4)")

        with connection.cursor() as c:
            c.execute("SELECT count(*) FROM llm_documentchunk WHERE embedding IS NULL")
            null_emb = c.fetchone()[0]
            c.execute("SELECT count(*) FROM llm_documentchunk WHERE length(content) < 50")
            short = c.fetchone()[0]
            c.execute("SELECT indexname FROM pg_indexes WHERE tablename='llm_documentchunk'")
            idx = [r[0] for r in c.fetchall()]
        w(f"embedding NULL: {null_emb}  (0이어야 함)")
        w(f"50자 미만 content: {short}")
        w(f"인덱스: {', '.join(idx)}")
        hnsw = any("hnsw" in i.lower() or "embedding" in i.lower() for i in idx)
        w(("✔ 벡터 인덱스 있음" if hnsw else "⚠ 벡터 인덱스 없음 — 검색 느릴 수 있음"))

        w("\n자리어때 청크 샘플:")
        for ch in DocumentChunk.objects.filter(metadata__source_file="구장먹거리_위치_자리어때.csv")[:2]:
            w(f"  [{ch.metadata.get('doc_id')}] {ch.content[:110]}")
        for ch in DocumentChunk.objects.filter(metadata__source_file="구장편의시설_위치_자리어때.csv")[:1]:
            w(f"  [{ch.metadata.get('doc_id')}] {ch.content[:110]}")
        n_off = DocumentChunk.objects.filter(metadata__source_file="구장먹거리_공식매점.csv").count()
        w(f"\n공식매점 청크: {n_off}  (B안 반영됐으면 0)")

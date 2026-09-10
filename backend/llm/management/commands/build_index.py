"""
RAG 인덱싱: 전처리 CSV/docs → 청크 텍스트 → 임베딩 → DocumentChunk 적재

실행:
  python manage.py build_index --dry-run          # 청크만 만들고 통계·샘플 출력 (임베딩 X)
  python manage.py build_index --limit 50         # 50건만 끝까지 (연결·키 테스트용)
  python manage.py build_index                    # 전량 (약 3,832청크, 100원 안팎)

재현성: 이 파일 하나로 처음부터 다시 만들어짐. 임베딩은 artifacts/ 에 500건마다 체크포인트.
근거 문서: claude/임베딩_대상파일_정리.md, claude/청킹임베딩_의사결정노트.md
"""

import hashlib
import json
import os
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from dotenv import load_dotenv

from llm.models import Document, DocumentChunk

BACKEND_DIR = Path(__file__).resolve().parents[3]
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")  # chat_service.py 와 같은 위치


def _pick_dir(env_key: str, container_path: str, repo_rel: str) -> Path:
    """컨테이너(/data)와 로컬 venv(레포 상대경로) 둘 다 동작하게."""
    if os.getenv(env_key):
        return Path(os.getenv(env_key))
    p = Path(container_path)
    return p if p.exists() else REPO_DIR / repo_rel


DATA_DIR = _pick_dir("RAG_DATA_DIR", "/data/preprocessed", "data/preprocessed")
DOCS_DIR = _pick_dir("RAG_DOCS_DIR", "/docs", "docs")
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # 1536차원
EMBED_BATCH = 100
CHECKPOINT_EVERY = 500

# ── 파일 → (category, 자연키 컬럼들) ────────────────────────────────────────────
CSV_SPEC = {
    "구장티켓가격.csv":               ("PRICE",         ["team_code", "zone_code", "day_type", "customer_type", "price_tier"]),
    # 2026-09-10 팀 결정(B안): 구장 내 먹거리는 자리어때만 임베딩. 구장먹거리_공식매점.csv 는 임베딩 제외(파일은 4차 크롤링 소스로 보존)
    "구장먹거리_위치_자리어때.csv":     ("FOOD_IN",       ["record_id"]),
    "kbo_ticket_policy_structured.csv": ("TICKET_POLICY", ["id"]),
    "구장편의시설.csv":               ("FACILITY",      ["record_id"]),
    "구장편의시설_위치_자리어때.csv":   ("FACILITY",      ["record_id"]),   # 굿즈샵·포토부스·물품보관함 — 공식과 유형 안 겹침
    "구장좌석구역.csv":               ("SEAT",          ["stadium_code", "zone_code"]),
    "구장부가콘텐츠_공식.csv":         ("CONTENT",       ["record_id"]),
    "구장교통정보.csv":               ("TRANSPORT",     ["stadium_code", "access_code"]),
    "구장잔여정보_좌석주차버스.csv":   ("TRANSPORT",     ["stadium_code", "data_type", "field_name"]),
    "구장좌석도.csv":                 ("SEAT",          ["team_code", "stadium_code"]),
    "구장운영정보.csv":               ("OPERATION",     ["stadium_code"]),
    "구장좌석경험.csv":               ("SEAT",          ["stadium_code", "scope_code"]),
}
KAKAO_CATEGORY = {"FD6": "FOOD_OUT", "CE7": "CAFE", "AT4": "SPOT"}

# 크롤러 CSV: content 컬럼이 이미 자연어 문장 → row_text 대신 그대로 사용 (2026-09-10 추가)
# 일정·순위는 원래 SQL 전용이었지만 game_schedule/team_standing 테이블이 아직 없어
# 직접 질문("삼성 몇 위야", "9/12 잠실 경기 있어")만이라도 답하도록 임베딩에도 넣는다. 상대 날짜 질문은 SQL 라우팅(4차)에서.
SENTENCE_CSV_SPEC = {
    "kbo_schedule_full.csv":           ("SCHEDULE", ["id"]),
    "kbo_standing.csv":                ("STANDING", ["id"]),
    # kbo_schedule_postseason_tbd(4건)은 참가팀 TBD 플레이스홀더라 제외 (9/10 결정). 순위 확정 후 크롤러가 실제 일정을 쓰면 그때 포함
}
# 구장 기본정보(주소·좌표) 9건 — "잠실야구장 주소 알려줘" 용
STADIUM_CSV = ("stadium_coordinates.csv", "STADIUM", ["stadium_code"])

TEAM_SHORT_KO = {  # 크롤러 CSV의 team 컬럼(한글 약칭) → 코드
    "LG": "LG", "두산": "DOOSAN", "키움": "KIWOOM", "SSG": "SSG", "KT": "KT",
    "한화": "HANWHA", "삼성": "SAMSUNG", "KIA": "KIA", "롯데": "LOTTE", "NC": "NC",
}

TEAM_HOME = {
    "LG": "JAMSIL", "DOOSAN": "JAMSIL", "KIWOOM": "GOCHEOK", "SSG": "MUNHAK", "KT": "SUWON",
    "HANWHA": "DAEJEON", "SAMSUNG": "DAEGU", "KIA": "GWANGJU", "LOTTE": "SAJIK", "NC": "CHANGWON",
}
TEAM_KO = {
    "LG": "LG 트윈스", "DOOSAN": "두산 베어스", "KIWOOM": "키움 히어로즈", "SSG": "SSG 랜더스",
    "KT": "KT 위즈", "HANWHA": "한화 이글스", "SAMSUNG": "삼성 라이온즈", "KIA": "KIA 타이거즈",
    "LOTTE": "롯데 자이언츠", "NC": "NC 다이노스",
}

# 본문에 넣지 않는 컬럼 (metadata 에는 그대로 보존됨)
SKIP_IN_TEXT = {
    "source", "source_id", "source_url", "source_grade", "source_type", "source_date",
    "verified_at", "collected_at", "updated_at", "evidence_type", "evidence_subtype", "evidence_scope",
    "status", "parse_status", "raw_id", "id", "record_id", "stadium_id", "attraction_id",
    "kakao_place_id", "place_url", "lng_x", "lat_y", "overlaps_legacy_parking_csv", "season",
    "team", "category", "content",  # kbo_ticket_policy 의 원문 content 는 구조화 필드로 대체
}
UNCERTAIN_NOTE = " (공식 확인 전 정보로 정확하지 않을 수 있습니다.)"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig")  # BOM 처리


def clean_meta(d: dict) -> dict:
    """NaN → None, numpy 타입 → 파이썬 타입 (JSONField 저장용)."""
    out = {}
    for k, v in d.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out[k] = None
        elif hasattr(v, "item"):
            out[k] = v.item()
        else:
            out[k] = v
    return out


def row_text(header: str, row: dict) -> str:
    parts = []
    for k, v in row.items():
        if k in SKIP_IN_TEXT or v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        s = str(v).strip()
        if s and s.lower() != "nan":
            parts.append(f"{k}: {s}")
    return f"[{header}] " + " / ".join(parts)


class Command(BaseCommand):
    help = "전처리 CSV/docs → 청크 → 임베딩 → DocumentChunk 적재"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="청크만 만들고 통계 출력")
        parser.add_argument("--limit", type=int, default=0, help="앞에서 N건만 처리")
        parser.add_argument("--sample", type=int, default=8, help="dry-run 시 출력할 샘플 수")

    # ── 1. 청크 만들기 ───────────────────────────────────────────────────────
    def build_chunks(self) -> list[dict]:
        coords = read_csv("stadium_coordinates.csv")
        stadium_ko = dict(zip(coords["stadium_code"], coords["stadium_name_ko"]))
        chunks: list[dict] = []
        seen: Counter = Counter()

        def add(source, category, stadium_code, team_code, natural, text, meta):
            scope = stadium_code or team_code or "COMMON"
            base = f"{category}_{scope}_{natural}"
            seen[base] += 1
            doc_id = base if seen[base] == 1 else f"{base}_{seen[base]}"  # 중복 17행 → _2, _3
            meta = clean_meta(meta)
            meta.update({"doc_id": doc_id, "category": category, "stadium_code": stadium_code,
                         "team_code": team_code, "source_file": source})
            chunks.append({"source": source, "category": category, "stadium_code": stadium_code,
                           "doc_id": doc_id, "content": text, "metadata": meta})

        # 1-1. 일반 CSV 11개
        for fname, (category, key_cols) in CSV_SPEC.items():
            df = read_csv(fname)
            for r in df.to_dict("records"):
                sc = r.get("stadium_code")
                if not isinstance(sc, str) or not sc:
                    sc = TEAM_HOME.get(r.get("team_code"))  # kbo_ticket_policy 에는 stadium_code 없음
                tc = r.get("team_code") if isinstance(r.get("team_code"), str) else None
                header = stadium_ko.get(sc, sc or "전 구장")
                if tc and "," not in tc:  # 'LG,DOOSAN'(잠실 공동홈)은 구장명만
                    header += f" · {TEAM_KO.get(tc, tc)}"
                text = row_text(header, r)
                if str(r.get("status", "")).upper() not in ("CONFIRMED", "CONFIRMED_OFFICIAL", "NAN", ""):
                    text += UNCERTAIN_NOTE
                natural = "_".join(str(r.get(c, "")) for c in key_cols)
                add(fname, category, sc, tc, natural, text, r)

        # 1-1b. 크롤러 CSV 3개: 자연어 content 그대로 (일정 786 + 순위 10)
        for fname, (category, key_cols) in SENTENCE_CSV_SPEC.items():
            df = read_csv(fname)
            for r in df.to_dict("records"):
                sc = r.get("stadium_code") if isinstance(r.get("stadium_code"), str) else None
                tc = TEAM_SHORT_KO.get(str(r.get("team", "")).strip())
                if sc in (None, "", "TBD"):
                    sc = TEAM_HOME.get(tc) if tc else None      # 순위: 팀 → 홈구장, 포스트시즌 TBD: None
                header = stadium_ko.get(sc, sc) if sc and sc != "OTHER" else ("포항 특별경기" if sc == "OTHER" else "KBO 리그")
                if tc:
                    header += f" · {TEAM_KO.get(tc, tc)}"
                text = f"[{header}] {str(r.get('content', '')).strip()}"
                if str(r.get("status_tag", r.get("status", ""))).upper() not in ("CONFIRMED", "NAN", ""):
                    text += UNCERTAIN_NOTE                            # 포스트시즌 TBD 4건 → OPEN
                natural = "_".join(str(r.get(c, "")) for c in key_cols)
                add(fname, category, sc, tc, natural, text, r)

        # 1-1c. 구장 기본정보 9건 (주소·좌표)
        fname, category, key_cols = STADIUM_CSV
        for r in read_csv(fname).to_dict("records"):
            sc = r["stadium_code"]
            homes = [TEAM_KO[t] for t, h in TEAM_HOME.items() if h == sc]
            text = (f"[{stadium_ko.get(sc, sc)}] {stadium_ko.get(sc, sc)} 주소: {r.get('address', '')}"
                    f" ({'·'.join(homes)} 홈구장)")
            add(fname, category, sc, None, sc, text, r)

        # 1-2. external_places: in_stadium_flag=Y(구장 내 매장 22건) 전부 제외 — 구장 내 먹거리는 자리어때가 담당
        #      (이전의 DAEGU 14건 예외는 자리어때 대구 43건이 생겨 2026-09-10 제거)
        df = read_csv("external_places.csv")
        for r in df.to_dict("records"):
            sc = r["stadium_code"]
            if str(r.get("in_stadium_flag", "")).upper() == "Y":
                continue
            category = KAKAO_CATEGORY.get(r.get("category_group_code"), "SPOT")
            header = stadium_ko.get(sc, sc)
            text = row_text(header, r)
            r["evidence_type"] = "THIRD_PARTY_API"
            add("external_places.csv", category, sc, None, str(r["attraction_id"]), text, r)

        # 1-3. docs JSON: 공통 1 + 구단별 (반입 1 + 재입장 1) × 10
        j = json.load(open(DOCS_DIR / "KBO_반입물품_재입장규정.json", encoding="utf-8"))
        common = j.get("carry_in_common_rules")
        add("KBO_반입물품_재입장규정.json", "CARRY_IN", None, None, "COMMON",
            "[전 구장 공통] KBO 야구장 반입물품 공통 규정: " + json.dumps(common, ensure_ascii=False),
            {"scope": "COMMON", "status": "CONFIRMED", "evidence_type": "OFFICIAL"})
        for code, t in j.get("teams", {}).items():
            name = TEAM_KO.get(code, code)
            home = TEAM_HOME.get(code)
            carry = {k: v for k, v in t.items() if not k.startswith("reentry")}
            reentry = {k: v for k, v in t.items() if k.startswith("reentry")}
            add("KBO_반입물품_재입장규정.json", "CARRY_IN", home, code, "RULES",
                f"[{name} 홈경기] 반입물품 규정: " + json.dumps(carry, ensure_ascii=False),
                {**t, "status": t.get("status") or t.get("carry_in_status"), "evidence_type": t.get("evidence_type")})
            add("KBO_반입물품_재입장규정.json", "REENTRY", home, code, "RULES",
                f"[{name} 홈경기] 재입장 규정 (구단 공식 확인이 안 된 비공식 정보입니다): "
                + json.dumps(reentry, ensure_ascii=False),
                {**t, "status": "PARTIAL", "evidence_type": "UNOFFICIAL"})

        # 1-4. 기초규칙: 헤딩 기준 분할
        md = (DOCS_DIR / "기초규칙_요약본.md").read_text(encoding="utf-8")
        parts = [p.strip() for p in re.split(r"^# ", md, flags=re.M) if p.strip()]
        for i, part in enumerate(parts, 1):
            add("기초규칙_요약본.md", "RULE", None, None, f"PART{i}", "[야구 기초 규칙] " + part,
                {"part": i, "status": "CONFIRMED", "evidence_type": "OFFICIAL"})

        return chunks

    # ── 2. 임베딩 ────────────────────────────────────────────────────────────
    def embed(self, texts: list[str]) -> np.ndarray:
        from langchain_openai import OpenAIEmbeddings  # 팀원 chat_service 와 같은 스택

        ARTIFACTS_DIR.mkdir(exist_ok=True)
        ckpt = ARTIFACTS_DIR / "embeddings.npy"
        fp = ARTIFACTS_DIR / "embeddings.fingerprint"
        fingerprint = hashlib.sha256("\n".join(texts).encode()).hexdigest()

        vecs: list = []
        if ckpt.exists() and fp.exists() and fp.read_text() == fingerprint:
            vecs = list(np.load(ckpt))
            self.stdout.write(f"체크포인트 재개: {len(vecs)}/{len(texts)}")
        fp.write_text(fingerprint)

        model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        for i in range(len(vecs), len(texts), EMBED_BATCH):
            vecs.extend(model.embed_documents(texts[i:i + EMBED_BATCH]))
            if len(vecs) % CHECKPOINT_EVERY < EMBED_BATCH:
                np.save(ckpt, np.array(vecs, dtype=np.float32))
                self.stdout.write(f"  임베딩 {len(vecs)}/{len(texts)}")
        arr = np.array(vecs, dtype=np.float32)
        np.save(ckpt, arr)
        return arr

    # ── 3. 적재 ──────────────────────────────────────────────────────────────
    @transaction.atomic
    def load(self, chunks: list[dict], vecs: np.ndarray):
        DocumentChunk.objects.all().delete()
        Document.objects.all().delete()
        docs = {}
        objs = []
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            src = c["source"]
            if src not in docs:
                docs[src] = Document.objects.create(title=src, source=src)
            objs.append(DocumentChunk(document=docs[src], content=c["content"], chunk_index=i,
                                      metadata=c["metadata"], embedding=v.tolist()))
        DocumentChunk.objects.bulk_create(objs, batch_size=500)
        return len(objs)

    # ── main ────────────────────────────────────────────────────────────────
    def handle(self, *args, **opt):
        self.stdout.write(f"DATA_DIR={DATA_DIR}\nDOCS_DIR={DOCS_DIR}\nEMBEDDING_MODEL={EMBEDDING_MODEL}")
        chunks = self.build_chunks()
        if opt["limit"]:
            chunks = chunks[: opt["limit"]]

        # STEP 12 검사
        n = len(chunks)
        no_stadium = sum(1 for c in chunks if not c["stadium_code"])
        short = sum(1 for c in chunks if len(c["content"]) < 50)
        by_cat = Counter(c["category"] for c in chunks)
        dup = n - len({c["doc_id"] for c in chunks})
        self.stdout.write(f"\n총 청크: {n}  (기대 3,832 ± 200, 2026-09-10 기준)")
        self.stdout.write(f"stadium_code 없음: {no_stadium}  (정상 5 = 반입 공통 1 + 기초규칙 4)")
        self.stdout.write(f"50자 미만: {short}")
        self.stdout.write(f"doc_id 중복: {dup}  (0 이어야 함)")
        for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {cat:14s} {cnt:5d}")

        if opt["dry_run"]:
            self.stdout.write("\n--- 샘플 ---")
            for c in random.sample(chunks, min(opt["sample"], n)):
                self.stdout.write(f"[{c['doc_id']}]\n{c['content'][:300]}\n")
            (ARTIFACTS_DIR).mkdir(exist_ok=True)
            with open(ARTIFACTS_DIR / "chunks.json", "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=1, default=str)
            self.stdout.write(f"청크 전체를 {ARTIFACTS_DIR / 'chunks.json'} 에 저장했습니다. --dry-run 종료.")
            return

        self.stdout.write("\n임베딩 시작...")
        vecs = self.embed([c["content"] for c in chunks])
        assert vecs.shape == (n, 1536), vecs.shape

        self.stdout.write("적재 시작...")
        loaded = self.load(chunks, vecs)
        self.stdout.write(self.style.SUCCESS(f"완료: DocumentChunk {loaded}건, Document {Document.objects.count()}건"))

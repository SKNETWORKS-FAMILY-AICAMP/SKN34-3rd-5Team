"""
data/preprocessed CSV에 `content` 컬럼을 채운다 (팀 공통 6컬럼 중 content 만, 2026-09-10 결정).

- 이미 있는 컬럼은 값·순서 모두 그대로. content 가 없는 파일에만 맨 뒤에 추가한다.
- content 는 build_index.py 의 청크 문장과 같은 규칙(row_text)으로 만든다 → 임베딩 청크와 1:1.
- id/source/team/category/updated_at 은 build_index 가 metadata 로 만들고 있어 CSV 에 넣지 않는다
  (넣으면 두 군데서 관리하게 됨). 필요해지면 ADD_COLUMNS 에 추가하면 같은 규칙으로 채워진다.

실행:  python backend/preprocessing/add_common_columns.py            # 덮어쓰기
       python backend/preprocessing/add_common_columns.py --check    # 변경 없이 통계만
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "preprocessed"
COMMON = ["id", "source", "team", "category", "updated_at", "content"]
ADD_COLUMNS = ["content"]  # 실제로 CSV 에 추가할 컬럼

# ── build_index.py 와 동일하게 유지할 것 ─────────────────────────────────────
CSV_SPEC = {
    "구장티켓가격.csv":               ("PRICE",         ["team_code", "zone_code", "day_type", "customer_type", "price_tier"]),
    "구장먹거리_공식매점.csv":         ("FOOD_IN",       ["record_id"]),
    "구장편의시설.csv":               ("FACILITY",      ["record_id"]),
    "구장좌석구역.csv":               ("SEAT",          ["stadium_code", "zone_code"]),
    "구장부가콘텐츠_공식.csv":         ("CONTENT",       ["record_id"]),
    "구장교통정보.csv":               ("TRANSPORT",     ["stadium_code", "access_code"]),
    "구장잔여정보_좌석주차버스.csv":   ("TRANSPORT",     ["stadium_code", "data_type", "field_name"]),
    "구장좌석도.csv":                 ("SEAT",          ["team_code", "stadium_code"]),
    "구장운영정보.csv":               ("OPERATION",     ["stadium_code"]),
    "구장좌석경험.csv":               ("SEAT",          ["stadium_code", "scope_code"]),
}
# 임베딩 대상은 아니지만 같은 규칙으로 채우는 파일
EXTRA_SPEC = {
    "stadium_coordinates.csv":        ("STADIUM",       []),
    "구장편의시설_보류이력.csv":       ("FACILITY_HOLD", ["facility_type", "floor"]),
    "3차_신규확보데이터.csv":          ("SUPPLEMENT",    ["no"]),
    "kbo_standing_history.csv":       ("STANDING",      ["snapshot_date", "team_code"]),
    # 자리어때(myseatcheck.com) 구역 단위 위치 — UNOFFICIAL/PARTIAL, 2026-09-10 추가. build_index 등록은 별도 결정
    "구장먹거리_위치_자리어때.csv":     ("FOOD_IN",       ["record_id"]),
    "구장편의시설_위치_자리어때.csv":   ("FACILITY",      ["record_id"]),
}
KAKAO_CATEGORY = {"FD6": "FOOD_OUT", "CE7": "CAFE", "AT4": "SPOT"}
TEAM_HOME = {
    "LG": "JAMSIL", "DOOSAN": "JAMSIL", "KIWOOM": "GOCHEOK", "SSG": "MUNHAK", "KT": "SUWON",
    "HANWHA": "DAEJEON", "SAMSUNG": "DAEGU", "KIA": "GWANGJU", "LOTTE": "SAJIK", "NC": "CHANGWON",
}
TEAM_KO = {
    "LG": "LG 트윈스", "DOOSAN": "두산 베어스", "KIWOOM": "키움 히어로즈", "SSG": "SSG 랜더스",
    "KT": "KT 위즈", "HANWHA": "한화 이글스", "SAMSUNG": "삼성 라이온즈", "KIA": "KIA 타이거즈",
    "LOTTE": "롯데 자이언츠", "NC": "NC 다이노스",
}
SKIP_IN_TEXT = {
    "source", "source_id", "source_url", "source_grade", "source_type", "source_date",
    "verified_at", "collected_at", "updated_at", "evidence_type", "evidence_subtype", "evidence_scope",
    "status", "parse_status", "raw_id", "id", "record_id", "stadium_id", "attraction_id",
    "kakao_place_id", "place_url", "lng_x", "lat_y", "overlaps_legacy_parking_csv", "season",
    "team", "category", "content",
}
UNCERTAIN_NOTE = " (공식 확인 전 정보로 정확하지 않을 수 있습니다.)"
KAKAO_INSIDE_NOTE = " (카카오 지도 기준 정보로 영업시간·폐업 여부 확인이 필요합니다.)"
# ──────────────────────────────────────────────────────────────────────────────

# 날짜 컬럼이 전혀 없는 파일 → 수집일(레포에 파일이 들어온 날짜)로 채움. 행별 갱신일이 아님.
FALLBACK_DATE = {
    "stadium_coordinates.csv": "2026-09-07",     # 카카오 지오코딩 실행일
    "external_places.csv": "2026-09-07",         # 카카오 로컬 API 수집일
    "구장편의시설_보류이력.csv": "2026-09-07",    # 원본 xlsx 파일명 기준일(…_20260907)
}

# team 컬럼은 크롤러 CSV와 같은 한글 약칭 ('두산', '롯데삼성' 식 이어붙임)
TEAM_SHORT = {
    "LG": "LG", "DOOSAN": "두산", "KIWOOM": "키움", "SSG": "SSG", "KT": "KT",
    "HANWHA": "한화", "SAMSUNG": "삼성", "KIA": "KIA", "LOTTE": "롯데", "NC": "NC",
}
STADIUM_TEAMS = {}
for t, s in TEAM_HOME.items():
    STADIUM_TEAMS.setdefault(s, []).append(t)
STADIUM_KO_TO_CODE = {}  # 보류이력에는 stadium_code 가 없어 한글명으로 찾는다


def stadium_from_name(name: str) -> str:
    name = _s(name)
    if name in STADIUM_KO_TO_CODE:
        return STADIUM_KO_TO_CODE[name]
    for k, v in STADIUM_KO_TO_CODE.items():
        if k and k in name:
            return v
    return ""


def _s(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def row_text(header: str, row: dict) -> str:
    parts = []
    for k, v in row.items():
        if k in SKIP_IN_TEXT:
            continue
        s = _s(v)
        if s:
            parts.append(f"{k}: {s}")
    return f"[{header}] " + " / ".join(parts)


def pick(row, *keys):
    for k in keys:
        s = _s(row.get(k))
        if s:
            return s
    return ""


def team_short(team_code, stadium_code):
    if team_code:
        return TEAM_SHORT.get(team_code, team_code)
    return "".join(TEAM_SHORT[t] for t in STADIUM_TEAMS.get(stadium_code, []))


SEEN = Counter()  # build_index 와 동일하게 파일을 가로질러 중복을 센다 (좌석구역/좌석경험 SEAT_SAJIK_* 충돌 4건)


def build(fname, category, key_cols, df, stadium_ko):
    seen = SEEN
    rows = []
    for r in df.to_dict("records"):
        sc = _s(r.get("stadium_code")) or stadium_from_name(r.get("stadium_name"))
        tc = _s(r.get("team_code"))
        if not sc and tc:
            sc = TEAM_HOME.get(tc, "")
        cat = category
        header = stadium_ko.get(sc, sc or "전 구장")
        if tc and "," not in tc:  # 'LG,DOOSAN'(잠실 공동 홈)은 구장명만
            header += f" · {TEAM_KO.get(tc, tc)}"
        text = row_text(header, r)
        note = ""
        if fname == "external_places.csv":
            inside = _s(r.get("in_stadium_flag")).upper() == "Y"
            cat = "FOOD_IN" if inside else KAKAO_CATEGORY.get(_s(r.get("category_group_code")), "SPOT")
            header = stadium_ko.get(sc, sc)
            text = row_text(header, r)
            if inside:
                note = KAKAO_INSIDE_NOTE
        elif _s(r.get("status")).upper() not in ("CONFIRMED", "CONFIRMED_OFFICIAL", ""):
            note = UNCERTAIN_NOTE
        text += note

        natural = "_".join(_s(r.get(c)) for c in key_cols)
        scope = sc or tc or "COMMON"
        base = f"{cat}_{scope}" + (f"_{natural}" if natural else "")
        seen[base] += 1
        doc_id = base if seen[base] == 1 else f"{base}_{seen[base]}"

        rows.append({
            "id": doc_id,
            "source": pick(r, "source", "source_url", "source_id", "geocode_source"),
            "team": _s(r.get("team")) or team_short(tc, sc),
            "category": _s(r.get("category")) or cat,
            "updated_at": pick(r, "updated_at", "verified_at", "source_date", "collected_at", "snapshot_date")
                          or FALLBACK_DATE.get(fname, ""),
            "content": text,
        })
    return pd.DataFrame(rows)


def main(check_only: bool):
    coords = pd.read_csv(DATA / "stadium_coordinates.csv", encoding="utf-8-sig", dtype=str)
    stadium_ko = dict(zip(coords["stadium_code"], coords["stadium_name_ko"]))
    STADIUM_KO_TO_CODE.update({v: k for k, v in stadium_ko.items()})
    # 보류이력의 stadium_name 은 '잠실야구장' 처럼 짧은 표기라 부분일치도 허용
    STADIUM_KO_TO_CODE.update({"잠실": "JAMSIL", "고척": "GOCHEOK", "문학": "MUNHAK", "인천": "MUNHAK",
                               "수원": "SUWON", "대전": "DAEJEON", "대구": "DAEGU", "광주": "GWANGJU",
                               "사직": "SAJIK", "부산": "SAJIK", "창원": "CHANGWON"})

    specs = {**CSV_SPEC, **EXTRA_SPEC, "external_places.csv": ("KAKAO", ["attraction_id"])}
    report = []
    for fname, (category, key_cols) in specs.items():
        path = DATA / fname
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        common = build(fname, category, key_cols, df, stadium_ko)
        missing = [c for c in ADD_COLUMNS if c not in df.columns]
        out = df.copy()
        for c in missing:  # 맨 뒤에 추가, 기존 컬럼 순서 유지
            out[c] = common[c].values
        dup = int(common["id"].duplicated().sum())
        empty_content = int((out["content"].str.len() < 20).sum())
        report.append((fname, len(out), missing, dup, empty_content))
        if not check_only:
            out.to_csv(path, index=False, encoding="utf-8-sig")

    print(f"{'file':34} {'rows':>5}  {'dup_id':>6} {'short':>5}  added")
    for f, n, m, d, e in report:
        print(f"{f:34} {n:>5}  {d:>6} {e:>5}  {','.join(m) or '-'}")


if __name__ == "__main__":
    main(check_only="--check" in sys.argv)

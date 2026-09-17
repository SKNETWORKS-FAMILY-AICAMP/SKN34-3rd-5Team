"""
팀원 보완자료 2종(편의시설 통합, 잔여정보 보완자료) 정규화 스크립트

- 입력: data/raw/KBO_9개구장_편의시설_통합_20260907.xlsx (현행_시설 시트)
        data/raw/KBO_잔여정보_보완자료_좌석도_주차_버스_20260907.xlsx (최종_보완데이터 시트)
- 문제: 두 파일의 stadium_id가 팀 표준 코드(team_stadium_code_map.csv 기준 JAMSIL/GOCHEOK/MUNHAK/
  SUWON/DAEJEON/DAEGU/GWANGJU/SAJIK/CHANGWON)가 아니라 "지역_팀명" 조합(INCHEON_SSG,
  DAEJEON_HANWHA 등)으로 되어 있어서, 다른 전처리 결과(stadium_coordinates.csv 등)와 조인이 안 됨.
- 처리: NEW_STADIUM_ID_MAP으로 표준 stadium_code + team_code를 붙여서 data/preprocessed/에
  새 CSV 2개로 저장. 원본 raw 파일은 건드리지 않음(전처리 규칙 준수).

기존 구장정보.xlsx Facilities 시트(49건)와의 대조 결과 (2026-09-08):
    이번 편의시설 통합자료(205건)가 기존 Facilities 시트와 겹치는 항목(고척·대전·대구·광주의
    수유실/흡연구역/장애인화장실)을 대조해본 결과, 대부분 새 자료가 기존 자료와 같은 사실을 더
    정밀한 위치로 재확인해준 것이었다(예: 대구 수유실 3개소, 흡연구역 4개소 — 기존과 새 자료가
    개수까지 일치). 다만 두 가지 예외가 있었다:
    1. **대전 2층**: 기존 Facilities 시트는 "1층·2층 모두 수유실"로 돼 있었는데, 새 자료는
       "2층은 임산부휴게실"로 더 세분화해서 구분하고 있다. 새 자료가 더 최근(2026-09-07)
       조사이고 출처 등급도 A라서, 이 문서에서는 새 자료(구장편의시설.csv)를 그대로 따른다 —
       기존 Facilities 시트 쪽 "2층 수유실" 표기는 낡은 정보로 간주.
    2. **고척 장애인화장실**: 기존 Facilities 시트엔 "2층 내야, 장애인화장실 남 8·여 8"이 있는데
       새 자료(205건)엔 고척의 장애인화장실 항목이 아예 없다 — 새 자료가 기존 자료의 완전한
       상위호환은 아니라는 뜻. 이 항목만 아래 MANUAL_SUPPLEMENT_FROM_OLD_FACILITIES로 살려서
       같이 저장한다(출처: 구장정보.xlsx Facilities S038, 확인일 2026-09-03).

사용법:
    pip install openpyxl
    python normalize_new_supplements.py
"""

import csv
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).parent
RAW_DIR = SCRIPT_DIR / ".." / "data" / "raw"
OUT_DIR = SCRIPT_DIR / ".." / "data" / "preprocessed"

FACILITIES_XLSX = RAW_DIR / "KBO_9개구장_편의시설_통합_20260907.xlsx"
SUPPLEMENT_XLSX = RAW_DIR / "KBO_잔여정보_보완자료_좌석도_주차_버스_20260907.xlsx"

FACILITIES_OUT = OUT_DIR / "구장편의시설.csv"
FACILITIES_HOLD_OUT = OUT_DIR / "구장편의시설_보류이력.csv"
SUPPLEMENT_OUT = OUT_DIR / "구장잔여정보_좌석주차버스.csv"

# 구장정보.xlsx(기존 Facilities 시트, S038)에만 있고 이번 205건 신규자료엔 빠진 항목을
# 수기로 보충. 새 자료가 상위호환이 아니라는 걸 확인한 유일한 항목(2026-09-08 대조).
MANUAL_SUPPLEMENT_FROM_OLD_FACILITIES = [
    {
        "record_id": "FAC-MANUAL-001", "stadium_id": "GOCHEOK", "stadium_code": "GOCHEOK",
        "team_code": "KIWOOM", "stadium_name": "고척스카이돔", "facility_type": "장애인화장실",
        "floor": "2F", "side": None, "nearby_section": "내야", "nearby_gate": None,
        "gender": "남", "indoor_outdoor": "실내", "location_detail": "2층 내야 장애인화장실 남 8칸",
        "source_url": None, "source_grade": None, "source_date": "2026",
        "verified_at": "2026-09-03", "status": "CONFIRMED", "evidence_type": "OFFICIAL",
        "notes": "구장정보.xlsx Facilities 시트(S038, ACCESSIBILITY 행)에서 이관 — 신규 205건 자료엔 고척 장애인화장실 항목이 없어서 수기 보충",
    },
    {
        "record_id": "FAC-MANUAL-002", "stadium_id": "GOCHEOK", "stadium_code": "GOCHEOK",
        "team_code": "KIWOOM", "stadium_name": "고척스카이돔", "facility_type": "장애인화장실",
        "floor": "2F", "side": None, "nearby_section": "내야", "nearby_gate": None,
        "gender": "여", "indoor_outdoor": "실내", "location_detail": "2층 내야 장애인화장실 여 8칸",
        "source_url": None, "source_grade": None, "source_date": "2026",
        "verified_at": "2026-09-03", "status": "CONFIRMED", "evidence_type": "OFFICIAL",
        "notes": "구장정보.xlsx Facilities 시트(S038, ACCESSIBILITY 행)에서 이관 — 신규 205건 자료엔 고척 장애인화장실 항목이 없어서 수기 보충",
    },
]

# 두 파일에서 실제로 쓰인 stadium_id -> (표준 stadium_code, 표준 team_code)
# team_stadium_code_map.csv 기준. 잠실은 두 팀(LG/DOOSAN) 공용이라 team_code는 참고용으로만 채움.
NEW_STADIUM_ID_MAP = {
    "SEOUL_JAMSIL": ("JAMSIL", "LG,DOOSAN"),
    "GOCHEOK": ("GOCHEOK", "KIWOOM"),
    "INCHEON_SSG": ("MUNHAK", "SSG"),
    "SUWON_KT": ("SUWON", "KT"),
    "DAEJEON_HANWHA": ("DAEJEON", "HANWHA"),
    "DAEGU_SAMSUNG": ("DAEGU", "SAMSUNG"),
    "GWANGJU_KIA": ("GWANGJU", "KIA"),
    "BUSAN_SAJIK": ("SAJIK", "LOTTE"),
    "CHANGWON_NC": ("CHANGWON", "NC"),
}


def normalize_stadium_id(raw_id: str):
    mapped = NEW_STADIUM_ID_MAP.get(raw_id)
    if mapped is None:
        print(f"[WARN] 매핑표에 없는 stadium_id 발견: {raw_id!r} — 표준 코드로 못 바꿈, 원본 값 그대로 둠")
        return None, None
    return mapped


def process_facilities():
    wb = openpyxl.load_workbook(FACILITIES_XLSX, data_only=True)

    ws = wb["현행_시설"]
    header = [c.value for c in ws[1]]
    rows = []
    for r in range(2, ws.max_row + 1):
        row = {header[i]: ws.cell(r, i + 1).value for i in range(len(header))}
        if row.get("record_id") is None:
            continue
        stadium_code, team_code = normalize_stadium_id(row.get("stadium_id"))
        row["stadium_code"] = stadium_code
        row["team_code"] = team_code
        rows.append(row)

    fieldnames = ["record_id", "stadium_id", "stadium_code", "team_code"] + [
        h for h in header if h not in ("record_id", "stadium_id")
    ]
    rows.extend(MANUAL_SUPPLEMENT_FROM_OLD_FACILITIES)
    with open(FACILITIES_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"완료: {FACILITIES_OUT} ({len(rows)}행)")

    # 보류_이력 시트도 참고용으로 별도 저장 (RAG에는 안 넣고, 사람이 재검토할 때 참고)
    ws2 = wb["보류_이력"]
    header2 = [c.value for c in ws2[1]]
    rows2 = []
    for r in range(2, ws2.max_row + 1):
        row = {header2[i]: ws2.cell(r, i + 1).value for i in range(len(header2))}
        if row.get(header2[0]) is None:
            continue
        rows2.append(row)
    with open(FACILITIES_HOLD_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header2)
        w.writeheader()
        w.writerows(rows2)
    print(f"완료: {FACILITIES_HOLD_OUT} ({len(rows2)}행, RAG 미반영·참고용)")


def process_supplement():
    wb = openpyxl.load_workbook(SUPPLEMENT_XLSX, data_only=True)
    ws = wb["최종_보완데이터"]
    header = [c.value for c in ws[1]]
    rows = []
    for r in range(2, ws.max_row + 1):
        row = {header[i]: ws.cell(r, i + 1).value for i in range(len(header))}
        if row.get("stadium_id") is None:
            continue
        stadium_code, team_code = normalize_stadium_id(row.get("stadium_id"))
        row["stadium_code"] = stadium_code
        row["team_code"] = team_code
        rows.append(row)

    fieldnames = ["stadium_id", "stadium_code", "team_code"] + [
        h for h in header if h != "stadium_id"
    ]
    with open(SUPPLEMENT_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"완료: {SUPPLEMENT_OUT} ({len(rows)}행)")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    process_facilities()
    process_supplement()

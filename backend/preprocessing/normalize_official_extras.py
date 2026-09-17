"""
`구장정보.xlsx`의 마지막까지 미처리 상태였던 3개 소규모 시트를 전처리하는 스크립트.

대상 시트 (전부 8~10행의 작은 시트라 시트당 파일 하나씩 그대로 CSV로 옮김. 값 표준화 없음 —
Ticket Prices/Seat Zones와 같은 이유로 원본 필드를 그대로 보존):

1. Seat Experience (8행) -> 구장좌석경험.csv
   시야/지붕 관련 "구역 단위가 아닌 구장 전체/그룹 단위" 설명. scope_code가
   ALL_SEATS/INFIELD_1F 처럼 구장좌석구역.csv(zone_code, 개별 구역)보다 상위 개념이라
   별도 파일로 유지 — 구장좌석구역.csv와 병합하지 않음.
2. Operations (9행) -> 구장운영정보.csv
   구장별 시설관리 주체/경기운영 주체/대표전화 3종(총괄·시설·티켓) 연락처 표.
   phone_facility/phone_ticket 결측은 별도 번호가 없다는 뜻(정상).
3. Seat Maps (10행, 팀당 1행) -> 구장좌석도.csv
   팀별 공식 좌석도 페이지/이미지 URL. asset_url/secondary_asset_url 결측은 이미지
   없이 페이지 링크만 공식 제공된다는 뜻(정상, 예: LG).

전부 status=CONFIRMED, evidence_type=OFFICIAL (원본 시트에 이미 그렇게 명시돼 있음).
"""
import openpyxl
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RAW_DIR = SCRIPT_DIR / ".." / "data" / "raw"
OUT_DIR = SCRIPT_DIR / ".." / "data" / "preprocessed"
SRC_XLSX = RAW_DIR / "구장정보.xlsx"

VALID_TEAM_CODES = {"LG", "DOOSAN", "KIWOOM", "SSG", "KT", "HANWHA", "SAMSUNG", "KIA", "LOTTE", "NC"}
VALID_STADIUM_CODES = {"JAMSIL", "GOCHEOK", "MUNHAK", "SUWON", "DAEJEON", "DAEGU", "GWANGJU", "SAJIK", "CHANGWON"}


def _sheet_to_df(wb, sheet_name):
    ws = wb[sheet_name]
    headers = [c.value for c in ws[1]]
    rows = [dict(zip(headers, r)) for r in ws.iter_rows(min_row=2, values_only=True) if any(v is not None for v in r)]
    return pd.DataFrame(rows)


def process_seat_experience(wb):
    df = _sheet_to_df(wb, "Seat Experience")
    assert set(df["team_code"]).issubset(VALID_TEAM_CODES), f"unknown team_code: {set(df['team_code']) - VALID_TEAM_CODES}"
    assert set(df["stadium_code"]).issubset(VALID_STADIUM_CODES), f"unknown stadium_code: {set(df['stadium_code']) - VALID_STADIUM_CODES}"
    df["evidence_type"] = "OFFICIAL"
    col_order = ["season", "team_code", "stadium_code", "scope_code", "scope_name_ko",
                 "view_characteristic", "roof_coverage", "evidence_scope", "evidence_type",
                 "source_id", "verified_at", "status", "notes"]
    df = df[col_order]
    out = OUT_DIR / "구장좌석경험.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[Seat Experience] {len(df)}행 -> {out}")
    print(df["status"].value_counts())
    return df


def process_operations(wb):
    df = _sheet_to_df(wb, "Operations")
    assert set(df["stadium_code"]).issubset(VALID_STADIUM_CODES), f"unknown stadium_code: {set(df['stadium_code']) - VALID_STADIUM_CODES}"
    assert df["stadium_code"].is_unique, "stadium_code 중복 존재"
    df["evidence_type"] = "OFFICIAL"
    col_order = ["stadium_code", "facility_manager", "game_operator", "phone_general",
                 "phone_facility", "phone_ticket", "evidence_type", "source_id",
                 "verified_at", "status", "notes"]
    df = df[col_order]
    out = OUT_DIR / "구장운영정보.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[Operations] {len(df)}행 -> {out}")
    print(df["status"].value_counts())
    return df


def process_seat_maps(wb):
    df = _sheet_to_df(wb, "Seat Maps")
    assert set(df["team_code"]).issubset(VALID_TEAM_CODES), f"unknown team_code: {set(df['team_code']) - VALID_TEAM_CODES}"
    assert set(df["stadium_code"]).issubset(VALID_STADIUM_CODES), f"unknown stadium_code: {set(df['stadium_code']) - VALID_STADIUM_CODES}"
    assert df["team_code"].is_unique, "team_code 중복 존재 (팀당 1행이어야 함)"
    df["evidence_type"] = "OFFICIAL"
    col_order = ["season", "team_code", "stadium_code", "map_title", "page_url",
                 "asset_url", "secondary_asset_url", "evidence_type", "source_id",
                 "verified_at", "status", "notes"]
    df = df[col_order]
    out = OUT_DIR / "구장좌석도.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[Seat Maps] {len(df)}행 -> {out}")
    print(df["status"].value_counts())
    return df


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(SRC_XLSX, data_only=True)
    process_seat_experience(wb)
    process_operations(wb)
    process_seat_maps(wb)

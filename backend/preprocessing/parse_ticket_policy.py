"""
kbo_ticket_policy.csv 구조화 파싱 스크립트 (2-전처리)

목적:
  원본 kbo_ticket_policy.csv(244행, yagu.today 크롤링, 자연어 문장 하나에 값이 다 들어있는 형태)를
  MySQL 정형 테이블(예: ticket_policy)에 바로 적재할 수 있는 구조화 컬럼으로 재구성한다.
  RAG(Chroma)용 원문(content)은 그대로 보존하고, 별도 컬럼으로 구조화 값을 덧붙이는 방식이라
  기존 파일을 덮어쓰지 않는다.

입력: baseball_data_organized/data/raw/kbo_ticket_policy.csv
출력: baseball_data_organized/data/preprocessed/kbo_ticket_policy_structured.csv

실행 위치: 이 스크립트는 baseball_data_organized/preprocessing/ 폴더에 두고 실행한다고 가정한다
(경로가 ../data/raw, ../data/preprocessed로 상대 참조되어 있음).

파싱 방식에 대한 솔직한 한계:
  "3차_수집데이터_점검_및_RAG반영가이드.md" 3-3에도 이미 적혀 있듯,
  예매처/조건 부분은 자유 문장이라 정규식만으로 100% 깔끔하게 못 뽑는다.
  그래서 이 스크립트는:
    - 신뢰도 높게 뽑히는 필드(정책유형, 하위구분, 오픈 날짜/시간, 상대전 날짜, 매칭업, 최대 매수)는
      각각 별도 컬럼으로 구조화한다.
    - "예매처:" 뒤에 붙는 예매 채널 + 조건 문구는 자유 형식이 너무 다양해서 하나의 필드
      (booking_channel_and_condition)로 그대로 보존한다 — 억지로 쪼개면 오히려 틀린 값이 생길 위험이
      크다고 판단했다. 이 필드는 Chroma 원문(content)과 함께 텍스트 검색으로 커버하는 걸 권장한다.
    - 정규식이 매칭되지 않는 행은 parse_status=FAILED로 표시하고 원본 content는 그대로 보존한다
      (건너뛰거나 데이터를 버리지 않는다 — 실패한 행도 값 손실 없이 확인 가능해야 하므로).

id 재생성 (2026-09-07 추가):
  원본 kbo_ticket_policy.csv의 id 컬럼이 244행 중 186개만 고유하다 — 58개 행(54개 그룹)이
  서로 다른 정책인데 id가 같다 (예: 두산 "베어스클럽"과 "두린이클럽" 선예매가 같은 id 공유).
  원본 id 생성 로직에서 생긴 충돌로 보이며, 이 id를 MySQL 기본키로 쓰면 서로 다른 정책이 조용히
  덮어써질 위험이 있다. 그래서 이 스크립트는:
    - team_code + game_date_mmdd + policy_type + policy_name + policy_subtype 조합으로 새 id를
      만들어서 구조화 파일의 대표 id로 쓴다 (파싱 성공행 기준 — 이 조합이면 실제로 244행 전부
      서로 다른 정책을 구분해낸다).
    - 파싱 실패(FAILED)행은 위 필드가 비어 있으므로 원본 content 전체를 키로 써서 새 id를 만든다.
    - 원본 id는 절대 버리지 않고 raw_id 컬럼으로 그대로 보존한다 (원본 파일 대조/추적용).
"""

import csv
import hashlib
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INPUT_PATH = SCRIPT_DIR / ".." / "data" / "raw" / "kbo_ticket_policy.csv"
OUTPUT_PATH = SCRIPT_DIR / ".." / "data" / "preprocessed" / "kbo_ticket_policy_structured.csv"

# 팀 표기(한글 축약형) -> 표준 team_code. team_stadium_code_map.csv와 반드시 일치시켜야 함.
TEAM_NAME_TO_CODE = {
    "LG": "LG", "두산": "DOOSAN", "키움": "KIWOOM", "SSG": "SSG", "KT": "KT",
    "한화": "HANWHA", "삼성": "SAMSUNG", "KIA": "KIA", "롯데": "LOTTE", "NC": "NC",
}

# 메인 패턴: [정책유형] 나머지(팀명+하위구분) 오픈요일날짜 오전/오후 시간 (M/D 상대팀전) 원정 vs 홈 (M/D)
#            오픈: 요일날짜 오전/오후 (시간)? (최대 N매)? 예매처: 나머지전부
PATTERN = re.compile(
    r"^\[(?P<policy_type>선예매|일반)\]\s*"
    r"(?P<name_part>.+?)\s+"
    r"(?P<open_date>\d{1,2}월\s*\d{1,2}일\s*[가-힣]요일)\s+"
    r"(?P<open_ampm1>오전|오후)\s*(?P<open_time1>\d{1,2}시(?:\s*\d{1,2}분)?)\s*"
    r"\((?P<game_mmdd>\d{1,2}/\d{1,2}(?:~\d{1,2})?)\s*(?:(?P<opponent>[^)]+?)전)?\)\s*"
    r"(?P<away>.+?)\s+vs\s+(?P<home>.+?)\s*\(\d{1,2}/\d{1,2}(?:~\d{1,2})?\)\s*"
    r"오픈:\s*(?P<open_date2>\d{1,2}월\s*\d{1,2}일\s*[가-힣]요일)\s+"
    r"(?P<open_ampm2>오전|오후)\s*(?P<open_time2>\d{1,2}시(?:\s*\d{1,2}분)?|\d{1,2}분)?\s*"
    r"(?:최대\s*(?P<max_tickets>\d+)매)?\s*"
    r"예매처:\s*(?P<booking>.+)$"
)

SUBTYPE_PATTERN = re.compile(r"\((?P<subtype>[^)]+)\)\s*$")


def make_new_id(parsed: dict, team_code: str, raw_content: str) -> str:
    """원본 id 충돌(58행/54그룹)을 피하기 위한 새 id 생성.
    파싱 성공행: team_code+경기날짜+정책유형+정책명+하위구분 조합 -> 서로 다른 정책이면 무조건 다른 키가 됨.
    파싱 실패행: 위 필드가 비어 있으므로 원본 content 전체를 키로 사용."""
    if parsed.get("parse_status") == "OK":
        key = "|".join([
            team_code,
            parsed.get("game_date_mmdd", ""),
            parsed.get("policy_type", ""),
            parsed.get("policy_name", ""),
            parsed.get("policy_subtype", ""),
        ])
    else:
        key = f"FAILED|{raw_content}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    return f"ticket_policy_{digest}"


def parse_row(content: str) -> dict:
    m = PATTERN.match(content.strip())
    if not m:
        return {"parse_status": "FAILED"}

    d = m.groupdict()

    # name_part 예: "두산 선예매 (베어스클럽)" 또는 "KT 시즌권 선예매" 또는 "SSG 일반예매 (프렌즈)"
    # 맨 끝 괄호가 있으면 하위구분(subtype)으로 뽑고, 없으면 빈 값.
    name_part = d["name_part"].strip()
    subtype_match = SUBTYPE_PATTERN.search(name_part)
    subtype = subtype_match.group("subtype").strip() if subtype_match else ""
    policy_name = SUBTYPE_PATTERN.sub("", name_part).strip()

    away_raw = d["away"].strip()
    home_raw = d["home"].strip()

    return {
        "parse_status": "OK",
        "policy_type": d["policy_type"],
        "policy_name": policy_name,
        "policy_subtype": subtype,
        "open_date": d["open_date"],
        "open_ampm": d["open_ampm1"],
        "open_time": d["open_time1"],
        "game_date_mmdd": d["game_mmdd"],
        "opponent_name_raw": (d["opponent"] or "").strip(),
        "away_team_name_raw": away_raw,
        "home_team_name_raw": home_raw,
        "away_team_code": TEAM_NAME_TO_CODE.get(away_raw, ""),
        "home_team_code": TEAM_NAME_TO_CODE.get(home_raw, ""),
        "max_tickets": d["max_tickets"] or "",
        "booking_channel_and_condition": d["booking"].strip(),
    }


def main():
    with open(INPUT_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    out_rows = []
    ok_count = 0
    fail_count = 0

    for row in rows:
        parsed = parse_row(row["content"])
        if parsed["parse_status"] == "OK":
            ok_count += 1
        else:
            fail_count += 1

        team_code = TEAM_NAME_TO_CODE.get(row["team"], row["team"])
        new_id = make_new_id(parsed, team_code, row["content"])

        out_row = {
            "id": new_id,
            "raw_id": row["id"],
            "source": row["source"],
            "team": row["team"],
            "team_code": team_code,
            "category": row["category"],
            "updated_at": row["updated_at"],
            "content": row["content"],
            "status": "CONFIRMED" if parsed["parse_status"] == "OK" else "RECHECK",
            "evidence_type": "THIRD_PARTY_API",
        }
        # 파싱 성공/실패와 무관하게 항상 같은 컬럼 세트를 유지 (실패시 빈 문자열)
        for key in [
            "parse_status", "policy_type", "policy_name", "policy_subtype",
            "open_date", "open_ampm", "open_time", "game_date_mmdd",
            "opponent_name_raw", "away_team_name_raw", "home_team_name_raw",
            "away_team_code", "home_team_code", "max_tickets",
            "booking_channel_and_condition",
        ]:
            out_row[key] = parsed.get(key, "")

        out_rows.append(out_row)

    fieldnames = list(out_rows[0].keys()) if out_rows else []
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"총 {len(rows)}행 처리 완료 -> {OUTPUT_PATH}")
    print(f"파싱 성공(OK): {ok_count}행 / 파싱 실패(FAILED, status=RECHECK로 표시): {fail_count}행")
    if fail_count:
        print("실패한 행들의 team_code/team_code 매핑이 안 된 팀명 등은 아래에서 확인:")
        for row in out_rows:
            if row["parse_status"] == "FAILED":
                print(" -", row["id"], ":", row["content"][:80])

    # id 재생성이 실제로 충돌 없이 끝났는지 확인 (원본 id는 58행/54그룹이 중복이었음)
    new_ids = [row["id"] for row in out_rows]
    raw_ids = [row["raw_id"] for row in out_rows]
    new_dup = len(new_ids) - len(set(new_ids))
    raw_dup = len(raw_ids) - len(set(raw_ids))
    print(f"id 중복 검사: raw_id 중복 {raw_dup}건 (원본 파일 자체 문제, 그대로 보존) "
          f"/ 새로 만든 id 중복 {new_dup}건 (0이어야 정상)")


if __name__ == "__main__":
    main()

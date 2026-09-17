"""
KBO 포스트시즌 대진 플레이스홀더 생성 스크립트

TVING 일정 API(gw.tving.com)에는 포스트시즌 데이터가 아직 없다(정규시즌 순위가
확정돼야 대진이 나오기 때문). 대신 KBO가 이미 공식 발표한 라운드별 "일정(날짜)"과
"대진 규칙"은 고정된 사실이므로, 실제 API를 크롤링하는 대신 이 스크립트에서
구조적으로 생성한다.

참고 출처 (2026-09-06 확인):
- https://namu.wiki/w/2026%20%EC%8B%A0%ED%95%9C%20SOL%20KBO%20%ED%8F%AC%EC%8A%A4%ED%8A%B8%EC%8B%9C%EC%A6%8C
- KBO 2026 정규시즌 일정 발표 자료(2025-12-19)

만약 KBO가 일정을 변경 발표하거나 시즌이 바뀌면 아래 ROUNDS 딕셔너리만 수정하면 된다.
참가팀이 확정되면(포스트시즌 개막 직전) 이 스크립트로 다시 만들지 말고, 실제 확정된
팀명으로 수동으로 content를 업데이트하는 걸 권장한다(그 시점부턴 이 자리표시자가 아니라
확정 정보이므로).
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path

# 실행 위치 무관하게 항상 baseball_data_organized/data/preprocessed로 저장되도록
# 이 스크립트(preprocessing 폴더) 기준 상대 경로로 고정.
SCRIPT_DIR = Path(__file__).parent
OUTPUT_PATH = SCRIPT_DIR / ".." / "data" / "preprocessed" / "kbo_schedule_postseason_tbd.csv"

SEASON_YEAR = 2026
SOURCE_NOTE = (
    "https://namu.wiki/w/2026%20%EC%8B%A0%ED%95%9C%20SOL%20KBO%20%ED%8F%AC%EC%8A%A4%ED%8A%B8%EC%8B%9C%EC%A6%8C "
    "(2026-09-06 확인, KBO 공식 일정 발표 기반 정리)"
)

ROUNDS = [
    {
        "round_code": "WILDCARD",
        "round_name": "와일드카드 결정전",
        "date_range": "2026-10-09 ~ 2026-10-10",
        "matchup": "정규시즌 4위 vs 정규시즌 5위",
        "format_desc": "2전 2선승제, 4위팀 1승 어드밴티지 보유",
    },
    {
        "round_code": "SEMI_PLAYOFF",
        "round_name": "준플레이오프",
        "date_range": "2026-10-12 ~ 2026-10-18",
        "matchup": "와일드카드 결정전 승자 vs 정규시즌 3위",
        "format_desc": "5전 3선승제",
    },
    {
        "round_code": "PLAYOFF",
        "round_name": "플레이오프",
        "date_range": "2026-10-20 ~ 2026-10-26",
        "matchup": "준플레이오프 승자 vs 정규시즌 2위",
        "format_desc": "5전 3선승제",
    },
    {
        "round_code": "KOREAN_SERIES",
        "round_name": "한국시리즈",
        "date_range": "2026-10-28 ~ 2026-11-05",
        "matchup": "플레이오프 승자 vs 정규시즌 1위",
        "format_desc": "7전 4선승제",
    },
]


def main():
    updated_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_rows = []

    for rd in ROUNDS:
        identity = f"postseason_{SEASON_YEAR}_{rd['round_code']}"
        hash_value = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        doc_id = f"schedule_{hash_value[:16]}"

        content = (
            f"{SEASON_YEAR} 시즌 KBO 포스트시즌 {rd['round_name']} 일정입니다. "
            f"기간은 {rd['date_range']}로 예정되어 있습니다. "
            f"대진은 {rd['matchup']}이며, {rd['format_desc']}로 진행됩니다. "
            f"실제로 어느 팀이 여기에 해당하는지는 정규시즌 최종 순위가 확정되어야 알 수 있으며, "
            f"현재는 정규시즌 진행 중이라 참가팀이 아직 정해지지 않았습니다(TBD)."
        )

        out_rows.append({
            "id": doc_id,
            "source": SOURCE_NOTE,
            "team": "TBD",
            "category": "schedule_postseason",
            "updated_at": updated_at_str,
            "content": content,
            "game_date": rd["date_range"],
            "game_time": "",
            "stadium_code": "TBD",
            "stadium_name_raw": "",
            "away_team_code": "TBD",
            "home_team_code": "TBD",
            "away_score": "",
            "home_score": "",
            "status_code": "TBD",
            "game_type": "POSTSEASON_PLACEHOLDER",
            "evidence_type": "DERIVED",
            "status_tag": "OPEN",
        })

    cols = ["id", "source", "team", "category", "updated_at", "content",
            "game_date", "game_time", "stadium_code", "stadium_name_raw",
            "away_team_code", "home_team_code", "away_score", "home_score",
            "status_code", "game_type", "evidence_type", "status_tag"]

    out_file = OUTPUT_PATH
    with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    print(f"CSV 저장 완료: {out_file} ({len(out_rows)}건)")


if __name__ == "__main__":
    main()

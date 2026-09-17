"""
KBO 10개 구단 팀코드/구장코드 정규화 매핑 모듈
- 구장정보.xlsx(Teams/Stadiums) 기준 영문 team_code를 표준으로 삼음
- kbo_standing.csv, kbo_ticket_policy.csv 등에서 쓰이는 한글 축약형을 이 표준으로 변환
- kbo_schedule.csv의 team 컬럼은 두 팀명이 붙어있는 형태(예: "KTKIA", "삼성LG")라
  이 매핑만으로는 분리 불가 -> content 문장에서 정규식으로 재추출 권장 (parse_schedule_content 참고)

사용 예:
    from team_stadium_map import normalize_team, TEAM_MAP
    normalize_team("두산")   -> "DOOSAN"
    normalize_team("KIA")    -> "KIA"
    normalize_team("기아")   -> "KIA"
"""

import re

# team_code(영문, 표준) : {정식명칭, 한글축약형(csv에서 실제 등장하는 값), 지역, 구장코드}
TEAM_MAP = {
    "LG":      {"name_full": "LG 트윈스",      "short": "LG",  "region": "서울", "stadium_code": "JAMSIL"},
    "DOOSAN":  {"name_full": "두산 베어스",     "short": "두산", "region": "서울", "stadium_code": "JAMSIL"},
    "KIWOOM":  {"name_full": "키움 히어로즈",   "short": "키움", "region": "서울", "stadium_code": "GOCHEOK"},
    "SSG":     {"name_full": "SSG 랜더스",     "short": "SSG", "region": "인천", "stadium_code": "MUNHAK"},
    "KT":      {"name_full": "KT 위즈",        "short": "KT",  "region": "수원", "stadium_code": "SUWON"},
    "HANWHA":  {"name_full": "한화 이글스",     "short": "한화", "region": "대전", "stadium_code": "DAEJEON"},
    "SAMSUNG": {"name_full": "삼성 라이온즈",   "short": "삼성", "region": "대구", "stadium_code": "DAEGU"},
    "KIA":     {"name_full": "KIA 타이거즈",   "short": "KIA", "region": "광주", "stadium_code": "GWANGJU"},
    "LOTTE":   {"name_full": "롯데 자이언츠",   "short": "롯데", "region": "부산", "stadium_code": "SAJIK"},
    "NC":      {"name_full": "NC 다이노스",    "short": "NC",  "region": "창원", "stadium_code": "CHANGWON"},
}

# 역방향 조회용 (모든 표기 변형 -> 표준 team_code)
_ALIASES = {}
for code, info in TEAM_MAP.items():
    _ALIASES[code] = code                     # "DOOSAN" -> "DOOSAN"
    _ALIASES[info["short"]] = code            # "두산" -> "DOOSAN"
    _ALIASES[info["name_full"]] = code        # "두산 베어스" -> "DOOSAN"
    _ALIASES[info["name_full"].split(" ")[0]] = code  # "두산" 등 앞 단어
# KIA는 "기아"로도 종종 표기됨
_ALIASES["기아"] = "KIA"
_ALIASES["키움 히어로즈"] = "KIWOOM"


def normalize_team(raw: str) -> str | None:
    """다양한 표기의 팀명을 표준 team_code로 변환. 매칭 실패 시 None 반환."""
    if raw is None:
        return None
    raw = raw.strip()
    return _ALIASES.get(raw)


def stadium_code_of(team_code: str) -> str | None:
    info = TEAM_MAP.get(team_code)
    return info["stadium_code"] if info else None


# kbo_schedule.csv처럼 두 팀명이 구분자 없이 붙은 컬럼은 신뢰하지 말고
# content 문장("OO 원정팀과 XX 홈팀")에서 아래처럼 재추출할 것을 권장
_SCHEDULE_PATTERN = re.compile(r"([가-힣A-Za-z]+)\s*원정팀과\s*([가-힣A-Za-z]+)\s*홈팀")


def parse_schedule_content(content: str):
    """kbo_schedule.csv의 content 문장에서 (away_team_code, home_team_code) 추출.
    매칭 실패 시 (None, None) 반환 — 이 경우 원문을 사람이 확인해야 함."""
    m = _SCHEDULE_PATTERN.search(content)
    if not m:
        return None, None
    away_raw, home_raw = m.group(1), m.group(2)
    return normalize_team(away_raw), normalize_team(home_raw)


if __name__ == "__main__":
    tests = ["두산", "KIA", "기아", "삼성", "SSG", "존재하지않는팀"]
    for t in tests:
        print(t, "->", normalize_team(t))

    sample = "2026 시즌 KBO 경기 일정입니다. 2026-09-05 17:00에 광주구장에서 KT 원정팀과 KIA 홈팀이 경기를 진행합니다. 경기 상태는 경기 전입니다."
    print(parse_schedule_content(sample))

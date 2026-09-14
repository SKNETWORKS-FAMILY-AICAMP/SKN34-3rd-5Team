"""안내데스크 — 질문을 보고 club(구단·야구, 형준) / venue(구장 안팎, 현준) 중 누가 답할지 정한다. LLM 호출 0회.

두 도메인 모듈이 지켜야 하는 약속은 딱 하나:
    answer(question: str, history: list[dict] | None, hint_stadium: str | None) -> dict
        반환 {"answer": str, "sources": list[dict], "route": str}
    READY: bool   # False 면 디스패처가 이 도메인으로 보내지 않는다 (아직 채우는 중)

history 는 [{"role": "user"|"assistant", "content": str}, ...] (이번 질문은 제외, 오래된 것부터).
hint_stadium 은 프론트 context.stadium 을 구장 코드(JAMSIL 등)로 바꾼 값. 없으면 None.
"""
import logging
import re

from . import persona
from .club import agent as club
from .venue import agent as venue

log = logging.getLogger(__name__)

# ── 도메인 판별 키워드 (디스패처 전용 · 각 도메인의 상세 사전과는 별개) ───────────
# 구장 안팎: 먹거리·시설·교통·주변 → venue
VENUE_WORDS = [
    "먹거리", "매점", "맛집", "음식점", "식당", "밥집", "치킨", "피자", "버거", "떡볶이", "스낵",
    "카페", "커피", "디저트", "음료수",
    "주차", "지하철", "버스", "셔틀", "교통", "출구", "오는길", "가는 법", "어떻게 가",
    "수유실", "화장실", "보관함", "물품보관", "보관소", "짐보관", "의무실", "휠체어", "충전소", "흡연", "편의시설", "유모차",
    "굿즈", "팀스토어", "포토", "포토존", "사진", "전시", "이벤트", "체험",
    "근처", "주변", "놀거리", "명소", "가볼", "관광", "주소", "전화", "문의처",
]
# 구단·야구: 일정·순위·가격·예매·좌석·반입·규칙 → club
CLUB_WORDS = [
    "순위", "몇 위", "승률", "게임차", "꼴찌", "선두",
    "경기", "일정", "몇 시", "결과", "스코어", "몇대몇", "상대", "홈경기", "다음",
    "예매", "선예매", "티켓", "가격", "얼마", "요금",
    "좌석", "시야", "응원석", "내야", "외야", "테이블석", "휠체어석",
    "반입", "가져가", "들고", "가방", "캔", "페트", "소주", "맥주", "술", "주류", "우산", "돗자리", "도시락", "외부 음식",
    "재입장", "나갔다",
    "규칙", "룰", "이닝", "스트라이크", "볼넷", "삼진", "홈런", "ABS", "피치클락", "비디오 판독", "연장", "우천", "취소", "노게임",
]

# 야구 직관과 무관한 주제 — 어느 도메인으로도 보내지 않고 바로 범위 안내
OFF_TOPIC = re.compile(r"축구|K리그|농구|배구|골프|e스포츠|롤드컵|올림픽|월드컵|"
                       r"날씨|주식|코인|부동산|영화|드라마|아이돌|연예인|다이어트|"
                       r"코딩|파이썬|숙제|레시피|요리법")
BASEBALL = re.compile(r"야구|KBO|구장|직관|경기|반입|재입장|좌석|예매|순위|선수|"
                      r"잠실|고척|문학|수원|대전|대구|광주|사직|창원|포항|"
                      r"LG|두산|키움|SSG|KT|한화|삼성|KIA|기아|롯데|NC", re.I)

# 프론트 context.stadium("잠실야구장") → 구장 코드
STADIUM_NAME_TO_CODE = {
    "잠실": "JAMSIL", "고척": "GOCHEOK", "문학": "MUNHAK", "인천": "MUNHAK", "랜더스": "MUNHAK",
    "수원": "SUWON", "대전": "DAEJEON", "대구": "DAEGU", "광주": "GWANGJU",
    "사직": "SAJIK", "부산": "SAJIK", "창원": "CHANGWON", "포항": "OTHER",
}


def _hits(question: str, words: list[str]) -> list[str]:
    q = question.replace(" ", "").upper()
    return [w for w in words if w.replace(" ", "").upper() in q]


# "얼마·요금" 은 주차 요금처럼 구장 쪽 질문에도 붙는다 → 구장 단어와 같이 나오면 club 쪽 신호로 세지 않는다
WEAK_CLUB_WORDS = {"얼마", "요금", "가격", "다음", "취소"}


def route(question: str) -> str:
    """'venue' | 'club' | 'both' | 'scope'"""
    if OFF_TOPIC.search(question) and not BASEBALL.search(question):
        return "scope"
    v, c = _hits(question, VENUE_WORDS), _hits(question, CLUB_WORDS)
    if v:
        c = [w for w in c if w not in WEAK_CLUB_WORDS]
    if v and c:
        return "both"
    if v:
        return "venue"
    return "club"          # 아무 데도 안 걸리면 club — 되묻기·거절 가드가 거기 있다


def stadium_code_from_name(name: str | None) -> str | None:
    if not name:
        return None
    for key, code in STADIUM_NAME_TO_CODE.items():
        if key in name:
            return code
    return None


def _call(domain, question, history, hint_stadium):
    try:
        return domain.answer(question, history=history, hint_stadium=hint_stadium)
    except Exception:            # 한 도메인이 죽어도 챗봇 전체가 죽지 않게
        log.exception("rag domain failed: %s", domain.__name__)
        return {"answer": persona.FIXED["error"], "sources": [], "route": f"{domain.__name__}:error"}


def answer(question: str, history: list[dict] | None = None, stadium_name: str | None = None) -> dict:
    """진입점. 반환 {"answer", "sources", "route"} — route 는 디버깅용 (어느 길로 갔는지)."""
    history = history or []
    hint = stadium_code_from_name(stadium_name)
    kind = route(question)

    if kind == "scope":
        return {"answer": persona.FIXED["scope"], "sources": [], "route": "dispatcher:scope"}

    use_venue = venue.READY
    if kind == "venue":
        result = _call(venue if use_venue else club, question, history, hint)
        result["route"] = f"venue>{result['route']}" if use_venue else f"venue(not ready)>club>{result['route']}"
    elif kind == "both" and use_venue:
        # 복합 질문: 두 도메인에 각각 묻고 이어 붙인다 (3차 범위. LLM 최대 2회)
        a, b = _call(club, question, history, hint), _call(venue, question, history, hint)
        result = {
            "answer": f"{a['answer']}\n\n{b['answer']}",
            "sources": a["sources"] + b["sources"],
            "route": f"both>club[{a['route']}]+venue[{b['route']}]",
        }
    else:
        result = _call(club, question, history, hint)
        result["route"] = f"club>{result['route']}"

    result["answer"] = persona.finalize(result["answer"])
    return result

"""RAG 체인 G0/G1/G2 (장고 없이 OpenAI SDK 직접). 가드·후처리는 프롬프트가 아니라 코드로 강제."""
import re
import time
from datetime import date

from common import LLM_MODEL, date_tokens, embed, keyword_rerank, openai_client, search
import structured
from router import PLACE_ALIAS, TEAM_ALIAS, detect_categories, detect_stadium
from scoring import REFUSE, WARN

G2_EF_SEARCH = 200  # ← STEP 4 결과로 고른 값으로 바꾸기

# ── 근거 등급 (status 13종 → 4등급) ─────────────────────────────────────────
OFFICIAL_STATUS = {"CONFIRMED", "CONFIRMED_OFFICIAL", "CONFIRMED_BASELINE"}


def grade(row):
    ev = str(row.get("evidence_type") or "").upper()
    st = str(row.get("status") or "").upper()
    if ev == "UNOFFICIAL":
        return "UNOFFICIAL"
    if ev == "THIRD_PARTY_API":
        return "THIRD_PARTY"
    if st in OFFICIAL_STATUS or (not st and ev in {"", "OFFICIAL", "DERIVED"}):
        return "OFFICIAL"
    return "UNCERTAIN"  # PARTIAL · RECHECK · OFFICIAL_APPROXIMATE · FIELD_VERIFIED · HISTORICAL_*


# ── 프롬프트 ────────────────────────────────────────────────────────────────
SYSTEM_PLAIN = "You are a helpful assistant."                      # G0 = 지금 chat_service 그대로
SYSTEM_NAIVE = "아래 문맥을 참고해서 사용자 질문에 한국어로 답하세요."  # G1
SYSTEM_GUARDED = """너는 KBO 직관 안내 챗봇이다. <context> 안의 정보만 근거로 답한다.

규칙
1. context에 없는 사실은 만들지 않는다. 없으면 "확인한 자료에 없습니다"라고 말하고 확인할 곳(구단 홈페이지·현장 안내소)을 알려준다.
2. 질문의 전제가 context와 다르면 맞장구치지 말고 context의 값으로 바로잡는다.
3. 근거의 등급에 따라 말투를 바꾼다.
   - OFFICIAL: 단정해서 말한다.
   - UNCERTAIN: "공식 확인 전 정보라 달라질 수 있습니다"를 붙인다.
   - UNOFFICIAL: 첫 문장을 "비공식 정보라 현장과 다를 수 있습니다."로 시작한다.
   - THIRD_PARTY: "외부 서비스 기준 정보라 방문 전 확인을 권합니다"를 붙인다.
4. 숫자·가격·시각은 context의 문자열을 그대로 옮긴다. 계산하거나 반올림하지 않는다.
5. 질문과 다른 구장의 정보는 쓰지 않는다.
6. context 항목에 기준일이 있으면 순위·일정·경기결과처럼 바뀌는 정보는 "9월 7일 기준"처럼 기준일을 함께 밝힌다.
7. 한국어 존댓말, 3~5문장."""

# 서비스용 — 평가용(G2)과 규칙은 같고 말투·구성만 사용자 눈높이에 맞춘다. 지표는 G2 로 측정하므로 여기 손대도 리포트 수치는 안 바뀐다.
SYSTEM_SERVICE = """너는 야구장을 자주 다녀서 직관 꿀팁을 잘 아는 다정한 선배다. 처음 가는 사람도 편하게 물어볼 수 있게 친근하게 안내한다. <context> 안의 정보만 근거로 답한다.

내용 규칙 (지킬 것)
1. context 에 없는 사실은 만들지 않는다. 없으면 솔직히 없다고 하고 확인할 곳(구단 홈페이지·현장 안내소)을 알려준다.
2. 질문의 전제가 context 와 다르면 맞장구치지 말고 바로잡는다.
3. 숫자·가격·시각은 context 의 값을 그대로 쓴다. 계산하거나 반올림하지 않는다.
4. 질문과 다른 구장의 정보는 쓰지 않는다.
5. 순위·일정처럼 바뀌는 정보는 기준일을 함께 밝힌다.
5-1. 반입물품은 KBO 전 구장 공통 규정이 기본값이다. 구단 예외가 context 에 있으면 그것이 공통 규정보다 우선하고,
     예외가 없으면 "정보가 없다"고 하지 말고 공통 규정으로 답한다("전 구장 공통 기준으로는 ~").
     공통 규정에도 그 품목이 없을 때만 없다고 한다. 구단 예외의 적용 범위(예: LG 홈경기 한정)는 그 범위에만 적용한다.
5-2. 단, 술의 종류와 도수는 예외다. 공통 규정이 정하는 것은 용기와 용량(미개봉 PET 1개 또는 캔 2개, 총 1L, 유리병 금지)뿐이고
     도수 기준은 정하지 않는다. 그러므로 소주처럼 도수가 높은 술을 물으면, 도수 기준이 context 에 있는 구장은 그 기준으로 답하고
     기준이 없는 구장은 용기·용량 기준만 알려준 뒤 "도수 제한은 구장마다 달라서 제 자료에는 이 구장 기준이 없다"고 밝힌다.
     도수 기준이 없다는 이유로 소주가 허용된다고 말하지 않는다.

말투 규칙
6. 결론을 첫 문장에 먼저 말한다. 주의 문구로 시작하지 않는다.
7. 근거가 비공식이거나 확인 전이면 마지막 줄에 한 문장으로만 가볍게 덧붙인다.
   - UNOFFICIAL: "이건 다녀온 분들 제보 기준이라 현장이랑 조금 다를 수 있어요!"
   - UNCERTAIN: "아직 공식 확인 전이라 바뀔 수도 있어요."
   - THIRD_PARTY: "외부 서비스 기준이라 가시기 전에 한 번만 더 확인해 보세요."
   - OFFICIAL: 아무것도 붙이지 않는다.
8. 자료의 항목명(경기 상태, 상품명, details 같은 말)을 그대로 옮기지 말고 사람이 말하듯 풀어 쓴다.
9. 항목이 3개 이상이면 줄바꿈과 "- " 목록으로 정리한다.
10. 친한 선배가 알려주듯 "~해요", "~예요", "~거든요", "~보세요" 같은 부드러운 존댓말을 쓴다. 딱딱한 "~입니다", "~됩니다" 체는 피한다.
    답이 좋은 소식이면 "좋아요!", "다행이에요" 처럼 짧은 리액션을 첫머리에 붙여도 된다. 이모지는 한 답변에 최대 1개까지만.
15. 도움이 될 만한 것이 context 에 같이 있으면 마지막에 "참고로 ~" 한 문장으로 덧붙인다. 없으면 억지로 만들지 않는다.
    질문과 직접 관련 없는 내용(좌석을 안 물었는데 좌석 안내 등)은 참고로도 붙이지 않는다.
21. 야구 직관과 무관한 주제는 "저는 KBO 야구 직관만 도와드려요"처럼 짧게 범위를 밝히고, 그 분야의 다른 사이트나
    정보원을 추천하지 않는다. 확인처 안내는 야구 관련 질문일 때만 한다.
20. 앞으로 일어날 일(순위 전망·승부 예측·매진 여부)은 단정하지 않는다. 대신 context 에 있는 현재 사실만 알려주고
    "남은 경기에 달려 있어 점치기는 어렵다"처럼 솔직히 말한다.
17. 한 번에 여러 가지를 물으면 빠뜨리지 말고 물어본 순서대로 "- 주차: ...", "- 반입: ..." 처럼 항목을 나눠 답한다.
    그중 일부만 context 에 있으면 있는 것부터 답하고, 없는 항목은 "~는 제가 가진 정보에 없네요" 라고 따로 밝힌다.
19. 여러 구장을 물으면 구장별로 "- 잠실: ...", "- 고척: ..." 항목을 나눠 답한다.
    "각 구단", "구장별로", "나머지도" 처럼 전체를 물으면 context 에 있는 구장을 하나도 빼지 말고 다 적는다.
    구단 예외가 없는 구장은 "공통 기준과 같아요" 한 줄로 짧게 적고, 같은 설명을 구장마다 반복하지 않는다.
18. 질문이 길고 사연이 섞여 있어도 실제로 궁금해하는 것만 골라 답한다. 인사말이나 상황 설명은 그대로 반복하지 않는다.
16. 거절할 때도 미안한 마음을 담아 "그 부분은 제가 가진 정보에 없네요, 죄송해요" 처럼 부드럽게 말하고, 어디서 확인하면 되는지 알려준다.
11. "제공된 자료에 따르면", "context", "문서", "doc_id", "등급" 같은 내부 용어는 답변에 쓰지 않는다.
    없을 때도 "확인된 정보가 없어요"처럼 사람이 하는 말로 한다.
12. 오늘은 {today} 다. "다음", "이번 주", "오늘", "내일" 같은 표현은 이 날짜를 기준으로 판단하고,
    확인한 일정이 오늘보다 과거면 지난 경기라고 알려준다.
13. 앞선 대화에서 구장·팀이 정해졌으면 이어서 그 구장으로 답한다. 사용자가 새 구장을 말하면 그때 바꾼다.
14. 근거가 서로 다르면 공식 자료를 우선하고, 같은 성격이면 기준일이 최신인 것을 쓴다.
    두 값이 정말 충돌하면 둘 다 알려주고 현장 확인을 권한다."""

FEW_SHOT = [  # 실제 구장 대신 '예시구장' — 예시 숫자가 실제 답에 새지 않게
    {"role": "user", "content": "<context>\n[1] (등급=OFFICIAL · doc_id=EX1) [예시구장] title: 구장 주차 / details: 총 500면\n</context>\n질문: 예시구장 주차 몇 면이에요?"},
    {"role": "assistant", "content": "예시구장 주차장은 총 500면입니다."},
    {"role": "user", "content": "<context>\n[1] (등급=UNOFFICIAL · doc_id=EX2) [예시구장] facility_type: 물품보관함 / location_detail: 1루 2층\n</context>\n질문: 예시구장 물품보관함 어디 있어요?"},
    {"role": "assistant", "content": "비공식 정보라 현장과 다를 수 있습니다. 이용자 제보 기준으로 물품보관함은 1루 2층에 있습니다. 방문 당일 안내소에서 한 번 더 확인해 주세요."},
    {"role": "user", "content": "<context>\n[1] (등급=OFFICIAL · doc_id=EX3) [예시구장] title: 지하철 / details: 3번 출구\n</context>\n질문: 예시구장 와이파이 비밀번호 알려줘"},
    {"role": "assistant", "content": "와이파이 비밀번호는 확인한 자료에 없습니다. 구장 안내소나 구단 홈페이지에서 확인해 주세요."},
]


FEW_SHOT_SERVICE = FEW_SHOT + [
    {"role": "user", "content": "<context>\n[1] (등급=THIRD_PARTY · 기준일=2026-09-07 · doc_id=EX4) 2026-09-12 17:00에 예시구장에서 A팀 원정팀과 B팀 홈팀이 경기를 진행합니다.\n</context>\n질문: 9월 12일 예시구장 경기 A팀 홈경기 맞지?"},
    {"role": "assistant", "content": "앗, 그날 예시구장 경기는 B팀 홈경기예요! A팀은 원정으로 와요.\n경기는 오후 5시에 시작하니 조금 일찍 가시면 여유 있게 들어가실 거예요.\n외부 서비스 기준이라 가시기 전에 한 번만 더 확인해 보세요."},
    {"role": "user", "content": "<context>\n[1] (등급=OFFICIAL · doc_id=EX5) [예시구장] 반입 규정: 캔·병 반입 불가, 1L 이하 페트병 음료 가능, 외부 음식 가능\n</context>\n질문: 예시구장에 맥주 캔 들고 가도 돼?"},
    {"role": "assistant", "content": "아쉽지만 캔은 반입이 안 돼요. 대신 1L 이하 페트병 음료랑 외부 음식은 가져가실 수 있어요.\n참고로 구장 안에서도 생맥주를 팔고 있으니 그걸 이용하셔도 좋아요."},
]


def build_context(rows, with_grade=True, max_chars=1200):
    return "\n".join(
        f"[{i}] ({'등급=' + grade(r) + ' · ' if with_grade else ''}"
        f"{'기준일=' + r['updated_at'] + ' · ' if with_grade and r.get('updated_at') else ''}"
        f"doc_id={r['doc_id']}) {r['content'][:max_chars]}"
        for i, r in enumerate(rows, 1)
    )


# ── 가드 (LLM 호출 전) ─────────────────────────────────────────────────────
# 야구 직관과 무관한 주제 — 짧게 범위를 밝히고 끝낸다 (설계서 OUT_OF_SCOPE 인텐트)
OFF_TOPIC = re.compile(r"축구|K리그|농구|배구|골프|e스포츠|롤드컵|올림픽|월드컵|"
                       r"날씨|주식|코인|부동산|영화|드라마|아이돌|연예인|여자친구\s*선물|다이어트|"
                       r"코딩|파이썬|숙제|레시피|요리법")
BASEBALL = re.compile(r"야구|KBO|구장|직관|경기|반입|재입장|좌석|예매|순위|선수|"
                      r"잠실|고척|문학|수원|대전|대구|광주|사직|창원|포항|"
                      r"LG|두산|키움|SSG|KT|한화|삼성|KIA|기아|롯데|NC")
REFUND = re.compile(r"환불|예매\s*취소|티켓\s*취소|취소\s*수수료")
POHANG_AROUND = re.compile(r"포항.*(주차|맛집|먹거리|교통|카페|근처)|(주차|맛집|먹거리|교통|카페|근처).*포항")
NEED_STADIUM = {"TRANSPORT", "FOOD_IN", "FOOD_OUT", "CAFE", "SPOT", "FACILITY", "CONTENT",
                "SEAT", "PRICE", "REENTRY", "OPERATION", "STADIUM"}
CARRY_OVER = NEED_STADIUM | {"CARRY_IN"}   # 구장 이어받기 대상 (반입은 구단마다 달라 이어받되, 없을 땐 공통 규정으로 답한다)
FIXED = {
    "scope": "야구 직관 안내만 도와드릴 수 있습니다. 다른 주제는 확인한 자료에 없습니다.",
    "refund": "취소/환불 규정은 예매처에 문의하시기 바랍니다.",
    "pohang": "포항 특별경기 구장의 주변 정보는 확인한 자료에 없습니다. 경기 일정은 안내해 드릴 수 있어요.",
    "clarify": "어느 구장 기준으로 알려드릴까요? (잠실·고척·문학·수원·대전·대구·광주·사직·창원)",
}
FIXED_SERVICE = {   # 서비스용 가드 문구 (평가용 FIXED 는 채점 정규식과 맞물려 있어 그대로 둔다)
    "scope": "저는 KBO 야구 직관만 도와드릴 수 있어요! 경기 일정이나 순위, 반입 규정, 좌석, 예매처럼 "
             "구장 가실 때 궁금한 건 편하게 물어보세요.",
    "refund": "취소랑 환불은 구단이 아니라 예매처 규정을 따라서요, 예매하신 곳(티켓링크·인터파크 등)에 문의하시는 게 제일 정확해요. 예매처에 문의하시면 수수료까지 바로 안내받으실 수 있어요.",
    "pohang": "포항은 특별경기 구장이라 주변 정보까지는 제가 아직 못 챙겼어요, 죄송해요. 경기 일정은 바로 알려드릴 수 있어요!",
    "clarify": "어느 구장으로 가시나요? 구장을 알려주시면 바로 찾아드릴게요. (잠실·고척·문학·수원·대전·대구·광주·사직·창원)",
}
WARN_PREFIX = {"UNOFFICIAL": "비공식 정보라 현장과 다를 수 있습니다. ",
               "UNCERTAIN": "공식 확인 전 정보라 달라질 수 있습니다. "}
WARN_SUFFIX = {"UNOFFICIAL": "이건 다녀온 분들 제보 기준이라 현장이랑 조금 다를 수 있어요!",   # 서비스용은 맨 끝에 한 줄
               "UNCERTAIN": "아직 공식 확인 전이라 바뀔 수도 있어요."}


# 우리 답변에 나올 일이 없는 문자 체계 (키릴·히브리·아랍·인도계·타이 등). 한글·영문·숫자·기호·×·℃ 등은 그대로 둔다.
JUNK = re.compile(r"[\u0400-\u052F\u0590-\u1CFF\u1D00-\u1DFF\uE000-\uF8FF\uFB00-\uFDFF\uFE70-\uFEFF]")

# 답변 끝에 붙는 모델 부스러기: "…없어요..calc" 처럼 마침표 뒤에 영소문자 토막이 달라붙는 경우.
# 앞 글자가 영숫자면(kbo.co.kr, ver.2 등) 건드리지 않는다.
TAIL_JUNK = re.compile(r"(?<![A-Za-z0-9/])\.{1,4}\s*[a-z]{1,12}\s*$")


_SOFT = [  # (딱딱한 어미, 부드러운 어미) — 뜻이 안 바뀌는 것만
    (r"않습니다", "않아요"), (r"있습니다", "있어요"), (r"없습니다", "없어요"), (r"됩니다", "돼요"), (r"됐습니다", "됐어요"),
    (r"합니다", "해요"), (r"했습니다", "했어요"), (r"드립니다", "드려요"), (r"바랍니다", "바라요"), (r"권합니다", "권해요"),
    (r"주세요\.", "주세요."), (r"습니다", "어요"),
]


def soften(text):
    """'~입니다' 체를 '~예요' 체로. 입니다는 앞 글자 받침에 따라 이에요/예요."""
    def _ipnida(m):
        prev = m.group(1)
        has = "가" <= prev <= "힣" and (ord(prev) - ord("가")) % 28 != 0
        return prev + ("이에요" if has else "예요")
    text = re.sub(r"([가-힣A-Za-z0-9\)%])입니다", _ipnida, text)
    for a, b in _SOFT:
        text = re.sub(a, b, text)
    return text


def clean(text):
    """모델이 가끔 답변 끝에 섞는 다른 언어 글자를 지운다 (예: 구자라트 문자)"""
    t = re.sub(r"[ \t]{2,}", " ", JUNK.sub("", text)).strip()
    return TAIL_JUNK.sub("", t).strip()


def call_llm(messages):
    """Responses API — GPT-5.6 계열을 포함한 최신 모델을 모두 지원하는 OpenAI 기본 API"""
    t0 = time.perf_counter()
    resp = openai_client().responses.create(model=LLM_MODEL, input=messages)
    return resp.output_text or "", (time.perf_counter() - t0) * 1000


# ── 후속 질문 재구성: "그럼 사직은?" → "사직 경기 몇대몇이야?" ────────────────────
# 사람들은 "구장"과 "구단"을 섞어 쓴다("각 구단 소주 돼?"). 둘 다 다구장 질문으로 본다.
ALL_STADIUM = re.compile(
    r"(?:다른|나머지|타|전|모든|각|딴|여러|전체|10개|열개)\s*(?:구장|구단|팀)|"
    r"구장별|구장마다|구단별|구단마다|팀별|팀마다|다른\s*데|어느\s*구장|어떤\s*구장"
)
STADIUM_CODES = ["JAMSIL", "GOCHEOK", "MUNHAK", "SUWON", "DAEJEON", "DAEGU", "GWANGJU", "SAJIK", "CHANGWON"]


def cats_from_history(history):
    """직전 사용자 질문의 카테고리 — "다른 구장은?" 처럼 주제를 생략했을 때 이어받는다"""
    for m in reversed(history or []):
        if m.get("role") == "user":
            c = detect_categories(m["content"])
            if c:
                return c
    return []


_ENTITY_WORDS = sorted({w for ws in PLACE_ALIAS.values() for w in ws} | {w for ws in TEAM_ALIAS.values() for w in ws}
                       | set(structured.TEAM_SYNONYM), key=len, reverse=True)
_FILLER_WORDS = {"그럼", "그러면", "그렇다면", "근데", "그리고", "그래서", "거기", "거긴", "그쪽", "여기",
                 "어때", "어때요", "어떰", "어떄", "은", "는", "이", "가", "도", "요", "은요", "는요", "이면", "라면",
                 "알려줘", "알려주세요", "보여줘", "보여줄래", "말해줘", "궁금해", "궁금해요", "궁금", "뭐야", "뭐임",
                 "좀", "다", "전부", "또", "말고", "대해", "관해", "어떻게", "돼", "되나요", "될까", "가능해"}
_JOSA_TAIL = re.compile(r"(은요|는요|이면|라면|은데|는데|에서|에선|으로|은|는|이|가|도|요|의|에|로|서|엔)$")


def _content_left(question, ents):
    """구장·팀 이름과 조사·군말을 뺀 뒤 남는 내용어 (없으면 '그럼 사직은?' 같은 후속 질문)"""
    q = question
    for w in ents:
        q = re.sub(re.escape(w), " ", q, flags=re.IGNORECASE)
    q = re.sub(r"[?？!.,~]", " ", q)
    toks = []
    for t in q.split():
        t = _JOSA_TAIL.sub("", t)
        if t and t not in _FILLER_WORDS:
            toks.append(t)
    return "".join(toks)


_SHORT_FOLLOW = re.compile(
    r"^(어디서|어디야|어디|몇\s*시|시간은?|언제|누구랑|누구|상대는?|장소는?|어느\s*구장)"
    r"(\s*(해|해요|하나요|야|예요|이야|인가요|임|하는데|하지|되는데))?[\s?!.]*$"
)


def _topic_question(history):
    """대화를 거슬러 올라가며 '주제'가 담긴 사용자 질문을 찾는다 ("다른 구장도 알려줘" 같은 건 주제가 없다)"""
    for m in reversed(history or []):
        if m.get("role") != "user":
            continue
        q = ALL_STADIUM.sub("", m["content"]).strip()
        q = re.sub(r"^(그럼|그러면|근데|그리고)\s*", "", q)
        if _SHORT_FOLLOW.match(q):                      # "어디서 해?" 같은 초단문은 주제가 아니다
            continue
        if detect_categories(q) or len(_content_left(q, [w for w in _ENTITY_WORDS if w.upper() in q.upper()])) >= 3:
            return q
    return None


def rewrite_followup(question, history):
    """질문에 구장·팀 이름만 있거나 초단문이면, 직전 '주제' 질문과 합쳐 완전한 질문으로 만든다."""
    q = question.strip()
    if _SHORT_FOLLOW.match(q):                          # "어디서 해?" → "삼성 다음 경기는? 어디서 해?"
        topic = _topic_question(history)                # 직전이 또 초단문이면 그 앞의 주제 질문을 쓴다
        return f"{topic} {q}" if topic else q

    new_ents = [w for w in _ENTITY_WORDS if w.upper() in q.upper()]
    if not new_ents or _content_left(q, new_ents):      # 내용어가 있으면 온전한 질문 → 그대로
        return question

    prev = _topic_question(history)                     # 주제가 담긴 직전 질문 ("다른 구장도 알려줘" 는 건너뜀)
    if not prev:
        return question
    new = new_ents[0]
    old_ents = [w for w in _ENTITY_WORDS if w.upper() in prev.upper() and w.upper() != new.upper()]
    if old_ents:                                        # "잠실 주차 얼마야?" → "사직 주차 얼마야?"
        pat = re.compile("|".join(re.escape(w) for w in old_ents), re.IGNORECASE)
        out = pat.sub(new, prev)
        return re.sub(rf"({re.escape(new)}\s*)+", new + " ", out).strip()
    return f"{new} {prev}"                              # "경기 몇대몇이야?" → "사직 경기 몇대몇이야?"


PAST_GAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def drop_past_games(rows, question, today=None):
    """날짜를 묻지 않았는데 지난 경기 청크가 근거로 들어오면 뺀다.
       "몇 시부터 입장?" 같은 질문에 5월·6월 경기 시각을 나열하는 걸 막는다."""
    if date_tokens(question) or re.search(r"어제|그제|지난|작년|결과|스코어|이겼|졌", question):
        return rows                                   # 과거를 실제로 물은 질문은 그대로
    today = today or date.today().isoformat()
    keep = []
    for r in rows:
        if r.get("category") == "SCHEDULE":
            m = PAST_GAME.search(r["content"] or "")
            if m and m[1] < today:
                continue                              # 지난 경기 → 근거에서 제외
        keep.append(r)
    return keep or rows                               # 전부 빠지면 원래대로 (빈 근거 방지)


def slots_from_history(history, today=None):
    """직전 대화(최신부터)에서 구장·팀·날짜를 찾는다. history = [{'role','content'}, ...]"""
    today = today or date.today().isoformat()
    for m in reversed(history or []):
        if m.get("role") != "user":
            continue
        st, team = detect_stadium(m["content"]), structured.team_in(m["content"])
        when = structured.date_in(m["content"], today)
        if st or team or when:
            return st, team, when
    return None, None, None


def answer(conn, mode, question, qvec, history=None):
    """mode: G0(LLM 단독) | G1(기본 RAG) | G2(평가용) | SV(서비스용) → answer_raw·answer·rows·시간"""
    out = {"guard": "", "rows": [], "retrieval_ms": 0.0, "llm_ms": 0.0}

    if mode == "G0":
        raw, out["llm_ms"] = call_llm([{"role": "system", "content": SYSTEM_PLAIN},
                                       {"role": "user", "content": question}])
        return {**out, "answer_raw": raw, "answer": raw}

    if mode == "G1":
        rows, out["retrieval_ms"] = search(conn, qvec, k=5)
        raw, out["llm_ms"] = call_llm([{"role": "system", "content": SYSTEM_NAIVE},
                                       {"role": "user", "content": f"{build_context(rows, with_grade=False)}\n\n질문: {question}"}])
        return {**out, "answer_raw": raw, "answer": raw, "rows": rows}

    # G2(평가용) · SV(서비스용) — 검색 과정은 같고, 프롬프트와 후처리만 다르다 -------
    service = mode == "SV"

    prev_stadium, prev_team, prev_date = slots_from_history(history) if service else (None, None, None)
    if service:
        rewritten = rewrite_followup(question, history)
        if rewritten != question:                       # 재구성했으면 그 질문으로 검색·생성 (임베딩도 다시)
            out["guard"] = f"rewrite:{rewritten}"
            question, qvec = rewritten, embed([rewritten])[0]

    other_intent = set(detect_categories(question)) - {"SCHEDULE", "STANDING"}
    if service and not other_intent:       # 순위·일정만 물었을 때 DB 직접 조회 ("오늘 두산 경기 보러 가는데 소주 돼?" 는 반입 질문 → RAG)
        t0 = time.perf_counter()
        fixed = structured.answer(conn, question, date.today().isoformat(), hint_team=prev_team,
                                  hint_place=structured.STADIUM_PLACE.get(prev_stadium), hint_date=prev_date)
        out["retrieval_ms"] = (time.perf_counter() - t0) * 1000
        if fixed:
            return {**out, "guard": "structured", "answer_raw": fixed, "answer": fixed}

    stadium, cats = detect_stadium(question), detect_categories(question)
    multi = bool(service and ALL_STADIUM.search(question))
    if service and not cats:               # 주제를 생략한 후속 질문이면 직전 질문의 주제를 잇는다
        cats = cats_from_history(history)
    if multi:
        stadium, prev_stadium = None, None  # "다른 구장은?" → 특정 구장으로 좁히지 않는다
        out["guard"] = (out["guard"] + " " if out["guard"] else "") + "multi_stadium"
    # 복합 질문은 일정 카테고리를 빼지 않는다. "9/12 누가 홈이고 소주 돼?" 처럼 둘 다 물을 수 있어서,
    # 직접조회(structured)만 양보하고 검색은 카테고리별로 3건씩 균등 확보한다.
    if service and stadium is None and prev_stadium and not multi and (not cats or set(cats) & CARRY_OVER):
        # "재입장은?" 처럼 구장을 생략하면 직전 구장으로 이어간다 (규칙·순위처럼 구장 무관한 질문은 제외)
        stadium = prev_stadium
        out["guard"] = (out["guard"] + " " if out["guard"] else "") + f"carry:{stadium}"
    guard = ("scope" if OFF_TOPIC.search(question) and not BASEBALL.search(question) else
             "refund" if REFUND.search(question) else
             "pohang" if POHANG_AROUND.search(question) else
             "clarify" if stadium is None and not multi and set(cats) & NEED_STADIUM else "")
    if guard:
        text = (FIXED_SERVICE if service else FIXED)[guard]
        return {**out, "guard": guard, "answer_raw": text, "answer": text}

    if multi:
        # 구장마다 따로 검색해 2건씩 확보 (한꺼번에 뽑으면 특정 구장이 후보를 독점한다)
        rows, seen, common_kept = [], set(), False
        for st in STADIUM_CODES:
            part, ms = search(conn, qvec, k=8, stadium=st, categories=cats or None, ef_search=G2_EF_SEARCH)
            out["retrieval_ms"] += ms
            for r in keyword_rerank(question, part, k=2):
                if r["doc_id"] in seen:
                    continue
                if not r["stadium"]:          # 공통 청크는 구장마다 중복되니 처음 1건만 남긴다
                    if common_kept:
                        continue
                    common_kept = True
                seen.add(r["doc_id"])
                rows.append(r)
    elif service and len(cats) >= 2:
        # 복합 질문: 카테고리를 한꺼번에 검색하면 청크가 많은 쪽(좌석·일정)이 자리를 다 차지한다.
        # 카테고리마다 따로 검색해 3건씩 확보해야 "반입은 정보가 없어요" 같은 누락이 안 생긴다.
        rows, seen = [], set()
        for c in cats:
            part, ms = search(conn, qvec, k=12, stadium=stadium, categories=[c], ef_search=G2_EF_SEARCH)
            out["retrieval_ms"] += ms
            for r in keyword_rerank(question, part, k=3):
                if r["doc_id"] not in seen:
                    seen.add(r["doc_id"])
                    rows.append(r)
    else:
        rows, out["retrieval_ms"] = search(conn, qvec, k=30, stadium=stadium, categories=cats or None,
                                           ef_search=G2_EF_SEARCH)
    for d in date_tokens(question):        # 날짜 질문: 그 날짜가 든 청크는 벡터 순위와 무관하게 후보에 넣는다
        extra, ms = search(conn, qvec, k=5, stadium=stadium, categories=cats or None,
                           ef_search=G2_EF_SEARCH, must_text=d)
        out["retrieval_ms"] += ms
        have = {r["doc_id"] for r in rows}
        rows += [r for r in extra if r["doc_id"] not in have]
    if not (service and (multi or len(cats) >= 2)):   # 복합·다구장 질문은 위에서 이미 골라 놨다
        rows = keyword_rerank(question, rows, k=5)
    if service:
        rows = drop_past_games(rows, question)        # 지난 경기 나열 방지
    system = SYSTEM_SERVICE.format(today=date.today().isoformat()) if service else SYSTEM_GUARDED
    shots = FEW_SHOT_SERVICE if service else FEW_SHOT
    past = [{"role": m["role"], "content": m["content"]} for m in (history or [])[-6:]] if service else []
    ctx = build_context(rows, max_chars=500 if len(rows) > 8 else 1200)
    raw, out["llm_ms"] = call_llm([{"role": "system", "content": system}, *shots, *past,
                                   {"role": "user", "content": f"<context>\n{ctx}\n</context>\n질문: {question}"}])
    raw = clean(raw)                       # 다른 언어 글자 등 잡음 제거
    if service:
        raw = soften(raw)                  # 남은 "~입니다" 체를 "~예요" 체로

    # 후처리: 1순위 근거가 비공식/미확인인데 경고 문구가 빠졌으면 코드가 붙인다
    final, top = raw, (grade(rows[0]) if rows else "")
    if top in WARN_PREFIX and not WARN.search(raw) and not REFUSE.search(raw):
        final = (raw + "\n" + WARN_SUFFIX[top]) if service else (WARN_PREFIX[top] + raw)
    return {**out, "answer_raw": raw, "answer": final, "rows": rows}

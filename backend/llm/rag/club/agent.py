"""[club] 구단·야구 도메인 — 순위·일정·가격·예매·좌석·반입·재입장·규칙 (담당: 형준)

rag_test/chain.py 의 서비스 모드(SV)를 Django + LangChain 으로 옮긴 것.
흐름: 후속질문 재구성 → 순위·일정 직접조회(LLM 0회) → 가드 → 구장/카테고리 필터 검색 → 키워드 재정렬
      → 근거 등급 표기 → LangChain ChatOpenAI 1회 → 경고 문구 후처리
디스패처와의 약속: answer(question, history, hint_stadium) -> {"answer", "sources", "route"} · READY
"""
import os
import re
import time
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from . import structured
from .prompts import FEW_SHOT, FIXED, SYSTEM, WARN_SUFFIX
from .retrieval import date_tokens, embed, keyword_rerank, search
from .router import PLACE_ALIAS, TEAM_ALIAS, detect_categories, detect_stadium

READY = True
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-5.6-luna"

_llm = None


def llm():
    """LangChain ChatOpenAI — 서버 기동 후 한 번만 만든다 (chat_service.py 와 같은 방식)"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=LLM_MODEL, temperature=0, timeout=25, max_retries=0, reasoning_effort="none")
    return _llm


def _to_lc(messages):
    conv = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [conv[m["role"]](content=m["content"]) for m in messages]


def call_llm(messages):
    t0 = time.perf_counter()
    out = llm().invoke(_to_lc(messages)).content
    text = out if isinstance(out, str) else "".join(p.get("text", "") for p in out if isinstance(p, dict))
    return text or "", (time.perf_counter() - t0) * 1000


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


def build_context(rows, max_chars=1200):
    return "\n".join(
        f"[{i}] (등급={grade(r)} · {'기준일=' + r['updated_at'] + ' · ' if r.get('updated_at') else ''}"
        f"doc_id={r['doc_id']}) {r['content'][:max_chars]}"
        for i, r in enumerate(rows, 1)
    )


# ── 가드 (LLM 호출 전) ─────────────────────────────────────────────────────
REFUND = re.compile(r"환불|예매\s*취소|티켓\s*취소|취소\s*수수료")
POHANG_AROUND = re.compile(r"포항.*(주차|맛집|먹거리|교통|카페|근처)|(주차|맛집|먹거리|교통|카페|근처).*포항")
NEED_STADIUM = {"TRANSPORT", "FOOD_IN", "FOOD_OUT", "CAFE", "SPOT", "FACILITY", "CONTENT",
                "SEAT", "PRICE", "REENTRY", "OPERATION", "STADIUM"}
CARRY_OVER = NEED_STADIUM | {"CARRY_IN"}   # 구장 이어받기 대상
WARN = re.compile(r"비공식|제보 기준|공식 확인 전|확인되지 않|정확하지 않을|달라질 수|다를 수|바뀔 수|재확인|방문 전.{0,6}확인|가시기 전.{0,10}확인|현장.{0,8}확인")
REFUSE = re.compile(r"확인한 자료|찾을 수 없|알 수 없|확인할 수 없|확인이 어렵|확인 불가|"
                    r"안내드리기 어렵|답변드리기 어렵|포함되어 있지 않|예매처에 문의|(자료|일정|정보|기록)[^.\n]{0,25}없")

# ── 후속 질문 재구성: "그럼 사직은?" → "사직 경기 몇대몇이야?" ────────────────────
ALL_STADIUM = re.compile(
    r"(?:다른|나머지|타|전|모든|각|딴|여러|전체|10개|열개)\s*(?:구장|구단|팀)|"
    r"구장별|구장마다|구단별|구단마다|팀별|팀마다|다른\s*데|어느\s*구장|어떤\s*구장"
)
STADIUM_CODES = ["JAMSIL", "GOCHEOK", "MUNHAK", "SUWON", "DAEJEON", "DAEGU", "GWANGJU", "SAJIK", "CHANGWON"]
_ENTITY_WORDS = sorted({w for ws in PLACE_ALIAS.values() for w in ws} | {w for ws in TEAM_ALIAS.values() for w in ws}
                       | set(structured.TEAM_SYNONYM), key=len, reverse=True)
_FILLER_WORDS = {"그럼", "그러면", "그렇다면", "근데", "그리고", "그래서", "거기", "거긴", "그쪽", "여기",
                 "어때", "어때요", "어떰", "어떄", "은", "는", "이", "가", "도", "요", "은요", "는요", "이면", "라면",
                 "알려줘", "알려주세요", "보여줘", "보여줄래", "말해줘", "궁금해", "궁금해요", "궁금", "뭐야", "뭐임",
                 "좀", "다", "전부", "또", "말고", "대해", "관해", "어떻게", "돼", "되나요", "될까", "가능해"}
_JOSA_TAIL = re.compile(r"(은요|는요|이면|라면|은데|는데|에서|에선|으로|은|는|이|가|도|요|의|에|로|서|엔)$")
_SHORT_FOLLOW = re.compile(
    r"^(어디서|어디야|어디|몇\s*시|시간은?|언제|누구랑|누구|상대는?|장소는?|어느\s*구장)"
    r"(\s*(해|해요|하나요|야|예요|이야|인가요|임|하는데|하지|되는데))?[\s?!.]*$"
)


def cats_from_history(history):
    for m in reversed(history or []):
        if m.get("role") == "user":
            c = detect_categories(m["content"])
            if c:
                return c
    return []


def _content_left(question, ents):
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


def _topic_question(history):
    for m in reversed(history or []):
        if m.get("role") != "user":
            continue
        q = ALL_STADIUM.sub("", m["content"]).strip()
        q = re.sub(r"^(그럼|그러면|근데|그리고)\s*", "", q)
        if _SHORT_FOLLOW.match(q):
            continue
        if detect_categories(q) or len(_content_left(q, [w for w in _ENTITY_WORDS if w.upper() in q.upper()])) >= 3:
            return q
    return None


def rewrite_followup(question, history):
    q = question.strip()
    if _SHORT_FOLLOW.match(q):
        topic = _topic_question(history)
        return f"{topic} {q}" if topic else q
    new_ents = [w for w in _ENTITY_WORDS if w.upper() in q.upper()]
    if not new_ents or _content_left(q, new_ents):
        return question
    prev = _topic_question(history)
    if not prev:
        return question
    new = new_ents[0]
    old_ents = [w for w in _ENTITY_WORDS if w.upper() in prev.upper() and w.upper() != new.upper()]
    if old_ents:
        pat = re.compile("|".join(re.escape(w) for w in old_ents), re.IGNORECASE)
        out = pat.sub(new, prev)
        return re.sub(rf"({re.escape(new)}\s*)+", new + " ", out).strip()
    return f"{new} {prev}"


PAST_GAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def drop_past_games(rows, question, today=None):
    """날짜를 묻지 않았는데 지난 경기 청크가 근거로 들어오면 뺀다."""
    if date_tokens(question) or re.search(r"어제|그제|지난|작년|결과|스코어|이겼|졌", question):
        return rows
    today = today or date.today().isoformat()
    keep = []
    for r in rows:
        if r.get("category") == "SCHEDULE":
            m = PAST_GAME.search(r["content"] or "")
            if m and m[1] < today:
                continue
        keep.append(r)
    return keep or rows


def slots_from_history(history, today=None):
    today = today or date.today().isoformat()
    for m in reversed(history or []):
        if m.get("role") != "user":
            continue
        st, team = detect_stadium(m["content"]), structured.team_in(m["content"])
        when = structured.date_in(m["content"], today)
        if st or team or when:
            return st, team, when
    return None, None, None


# ── 진입점 ──────────────────────────────────────────────────────────────────
def answer(question, history=None, hint_stadium=None):
    history = history or []
    today = date.today().isoformat()
    timing = {}

    prev_stadium, prev_team, prev_date = slots_from_history(history, today)
    if prev_stadium is None:
        prev_stadium = hint_stadium                  # 프론트가 넘겨준 구장 (사용자가 화면에서 고른 것)

    rewritten = rewrite_followup(question, history)
    route = []
    if rewritten != question:
        route.append(f"rewrite:{rewritten}")
        question = rewritten

    # 1. 순위·일정만 물었으면 DB 직접 조회 (LLM 0회)
    other_intent = set(detect_categories(question)) - {"SCHEDULE", "STANDING"}
    if not other_intent:
        t0 = time.perf_counter()
        fixed = structured.answer(question, today, hint_team=prev_team,
                                  hint_place=structured.STADIUM_PLACE.get(prev_stadium), hint_date=prev_date)
        timing["structured_ms"] = round((time.perf_counter() - t0) * 1000)
        if fixed:
            return {"answer": fixed, "sources": [], "route": "structured", "timing": timing}

    # 2. 슬롯 · 가드
    stadium, cats = detect_stadium(question), detect_categories(question)
    multi = bool(ALL_STADIUM.search(question))
    if not cats:
        cats = cats_from_history(history)
    if multi:
        stadium, prev_stadium = None, None
        route.append("multi_stadium")
    if stadium is None and prev_stadium and not multi and (not cats or set(cats) & CARRY_OVER):
        stadium = prev_stadium
        route.append(f"carry:{stadium}")
    guard = ("refund" if REFUND.search(question) else
             "pohang" if POHANG_AROUND.search(question) else
             "clarify" if stadium is None and not multi and set(cats) & NEED_STADIUM else "")
    if guard:
        return {"answer": FIXED[guard], "sources": [], "route": f"guard:{guard}", "timing": timing}

    # 3. 검색
    qvec = embed(question)
    retrieval_ms = 0.0
    if multi:
        rows, seen, common_kept = [], set(), False
        for st in STADIUM_CODES:
            part, ms = search(qvec, k=8, stadium=st, categories=cats or None)
            retrieval_ms += ms
            for r in keyword_rerank(question, part, k=2):
                if r["doc_id"] in seen:
                    continue
                if not r["stadium"]:
                    if common_kept:
                        continue
                    common_kept = True
                seen.add(r["doc_id"])
                rows.append(r)
    elif len(cats) >= 2:
        rows, seen = [], set()
        for c in cats:
            part, ms = search(qvec, k=12, stadium=stadium, categories=[c])
            retrieval_ms += ms
            for r in keyword_rerank(question, part, k=3):
                if r["doc_id"] not in seen:
                    seen.add(r["doc_id"])
                    rows.append(r)
    else:
        rows, retrieval_ms = search(qvec, k=30, stadium=stadium, categories=cats or None)
    for d in date_tokens(question):
        extra, ms = search(qvec, k=5, stadium=stadium, categories=cats or None, must_text=d)
        retrieval_ms += ms
        have = {r["doc_id"] for r in rows}
        rows += [r for r in extra if r["doc_id"] not in have]
    if not (multi or len(cats) >= 2):
        rows = keyword_rerank(question, rows, k=5)
    rows = drop_past_games(rows, question, today)
    timing["retrieval_ms"] = round(retrieval_ms)

    # 4. 생성 (LangChain 1회)
    ctx = build_context(rows, max_chars=500 if len(rows) > 8 else 1200)
    messages = [{"role": "system", "content": SYSTEM.format(today=today)}, *FEW_SHOT,
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": f"<context>\n{ctx}\n</context>\n질문: {question}"}]
    raw, timing["llm_ms"] = call_llm(messages)
    timing["llm_ms"] = round(timing["llm_ms"])

    # 5. 후처리: 1순위 근거가 비공식/미확인인데 경고 문구가 빠졌으면 코드가 붙인다
    top = grade(rows[0]) if rows else ""
    if top in WARN_SUFFIX and not WARN.search(raw) and not REFUSE.search(raw):
        raw = f"{raw}\n{WARN_SUFFIX[top]}"

    sources = [{"doc_id": r["doc_id"], "grade": grade(r), "category": r["category"],
                "stadium": r["stadium"], "updated_at": r.get("updated_at") or ""} for r in rows]
    route.append(f"rag:{stadium or '-'}:{','.join(cats) or '-'}")
    return {"answer": raw, "sources": sources, "route": " ".join(route), "timing": timing}

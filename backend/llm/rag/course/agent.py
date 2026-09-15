"""[course] 직관 코스 추천 — 경기 전 식사 → 관람 → 경기 후 (담당: 형준) ★ 메인 기능

흐름 (LLM 은 딱 1회, 그것도 "후보 키 고르기 + 인트로 두세 문장" 만 한다)
    ① 슬롯     구장 · 취향 · 동행 · 여유시간 · 재추천               slots.py        LLM 0회
    ② 경기     club.structured 에서 날짜·시각·상대                  club/structured LLM 0회
    ③ 후보     경기 전용 / 경기 후용 쿼리 2개를 한 번에 임베딩 →
               카테고리별 벡터 검색 → 동행 ban·취향 boost·반경으로 거름              LLM 0회
    ④ 선택     후보에 P1..Pn 과 방위("북동 900m")를 붙여 제시 → JSON 으로 키만 받음   LLM 1회
    ⑤ 동선     총 도보를 재고 너무 길면 같은 카테고리의 가까운 후보로 교체  geo.py     LLM 0회
    ⑥ 시간표   경기 시작에서 역산해 도착·출발 시각 계산                timeline.py     LLM 0회
    ⑦ 조립     키 → DB 값(이름·좌표·주소·kakao id)으로 places[] + 코스 저장 payload  LLM 0회

좌표 환각이 0 인 이유: LLM 출력에서 가져오는 건 place_key·phase·reason·intro 뿐이고
이름·좌표·주소·시각·거리는 전부 DB 값이거나 코드가 계산한 값이다.

디스패처와의 약속: answer(question, history, hint_stadium) -> {"answer","sources","route","places"} · READY

places[i] 는 프론트 RouteStop / travel.CourseStop 과 같은 키를 쓴다:
    {"phase": "BEFORE"|"GAME"|"AFTER", "name", "lat", "lng", "category": "FOOD"|"CAFE"|"SPOT"|"STADIUM",
     "placeId", "address", "placeUrl", "distance": m, "reason", "time": "16:40", "stayMin": 50}
"""
import json
import logging
import os
import re
import time
from datetime import date, datetime

from django.db import connection, transaction
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..club import structured
from ..club.retrieval import EF_SEARCH, embed_many
from ..club.router import detect_stadium
from . import geo, save, slots, timeline
from .prompts import NO_GAME, NO_PLACES, SYSTEM, USER_TEMPLATE, WARN_THIRD_PARTY

log = logging.getLogger(__name__)

READY = True
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-5.6-luna"
DEFAULT_GAME_TIME = "18:30"                     # 경기 정보가 없을 때 가정하는 시작 시각 (평일 저녁)
MAX_DISTANCE_M = 2500                           # 도보 30분 정책 (먹거리_플레이스_반경 정책 2026-09-08)
TIGHT_DISTANCE_M = 1200                         # "퇴근하고 바로" 처럼 촉박할 때 좁히는 반경
EVENING_FROM = "17:00"                          # 이 시각 이후 시작이면 야간 경기로 본다

CAT_LABEL = {"FOOD_OUT": "FOOD", "CAFE": "CAFE", "SPOT": "SPOT"}
# (카테고리, 어떤 쿼리 벡터로 찾을지, 몇 개를 LLM 에 보여줄지)
SEARCHES = [("FOOD_OUT", "meal", 8), ("FOOD_OUT", "after", 4), ("CAFE", "after", 4), ("SPOT", "after", 4)]

STADIUM_KO = {"JAMSIL": "잠실야구장", "GOCHEOK": "고척스카이돔", "MUNHAK": "인천SSG랜더스필드", "SUWON": "수원KT위즈파크",
              "DAEJEON": "대전한화생명볼파크", "DAEGU": "대구삼성라이온즈파크", "GWANGJU": "광주기아챔피언스필드",
              "SAJIK": "사직야구장", "CHANGWON": "창원NC파크"}

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)
_WARN = re.compile(r"카카오맵 기준|외부 서비스 기준|영업 여부|확인해 보세요")
_llm = None


def llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=LLM_MODEL, temperature=0, timeout=25, max_retries=0, reasoning_effort="none")
    return _llm


# ── 1. DB 조회 ────────────────────────────────────────────────────────────────
def stadium_anchor(code):
    """구장 앵커 (STADIUM 청크 metadata: stadium_name_ko · lat_y · lng_x · address). 없으면 이름만."""
    with connection.cursor() as cur:
        cur.execute("""SELECT metadata FROM llm_documentchunk
                       WHERE metadata->>'category' = 'STADIUM' AND metadata->>'stadium_code' = %s LIMIT 1""", [code])
        row = cur.fetchone()
    m = _meta(row[0]) if row else {}
    return {"key": "STADIUM", "phase": "GAME", "name": m.get("stadium_name_ko") or STADIUM_KO.get(code, code),
            "lat": _f(m.get("lat_y")), "lng": _f(m.get("lng_x")), "category": "STADIUM", "detail": "",
            "placeId": None, "address": m.get("address") or "", "placeUrl": "", "distance": 0, "doc_id": m.get("doc_id")}


def search_places(qvec, code, category, k):
    """구장·카테고리 선필터 → 벡터 상위 k (metadata 통째로 — 좌표·주소·kakao id 가 거기 있다)"""
    sql = """SELECT metadata, embedding <=> %(v)s::vector AS dist
             FROM llm_documentchunk
             WHERE metadata->>'stadium_code' = %(st)s AND metadata->>'category' = %(cat)s
             ORDER BY embedding <=> %(v)s::vector LIMIT %(k)s"""
    params = {"v": "[" + ",".join(map(str, qvec)) + "]", "st": code, "cat": category, "k": k}
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute(f"SET LOCAL hnsw.ef_search = {int(EF_SEARCH)}")
        cur.execute(sql, params)
        rows = cur.fetchall()
    rows = [(_meta(m), d) for m, d in rows]
    return [{"dist": float(d), "category": category, "name": m.get("name") or "",
             "detail": m.get("category_detail") or "", "distance": int(_f(m.get("distance_m")) or 0),
             "lat": _f(m.get("lat_y")), "lng": _f(m.get("lng_x")), "address": m.get("address") or "",
             "placeId": _kakao_id(m), "placeUrl": m.get("place_url") or "", "doc_id": m.get("doc_id")}
            for m, d in rows]


def _meta(m):
    """metadata 컬럼을 dict 로. jsonb 가 드라이버·적재 방식에 따라 문자열로 올 때가 있어 방어한다."""
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except (json.JSONDecodeError, TypeError):
            return {}
    return m if isinstance(m, dict) else {}


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _kakao_id(meta):
    v = meta.get("kakao_place_id")
    if v in (None, ""):
        return None
    s = str(v)
    return s[:-2] if s.endswith(".0") else s          # CSV 에서 float 로 읽힌 id (487584815.0) 정리


# ── 2. 후보 고르기 (LLM 전에 코드가 거른다 — 동행·취향·거리·다양성) ──────────────
def _subcat(p):
    parts = [s.strip() for s in p["detail"].split(">")]
    return parts[1] if len(parts) > 1 else (parts[0] if parts else "")


def _brand(p):
    return re.sub(r"\s.*$", "", p["name"])              # "BBQ 한강버스잠실선착장점" → "BBQ"


def pick(cands, k, sl, radius, seen_names=None):
    """벡터 순위 + 취향/동행 가산, 동행 금지 업종·반경 밖·중복 제외.

    sl          slots.parse() 결과
    radius      이번 질문에 적용할 도보 반경(m)
    seen_names  이미 다른 검색에서 뽑힌 이름 (FOOD_OUT 을 두 번 검색하므로 중복 방지)
    """
    ban, boost, prefs = sl["ban"], sl["boost"], sl["prefs"]
    exclude = {n.strip() for n in (sl.get("exclude") or set())}
    seen_names = seen_names if seen_names is not None else set()

    def score(p):
        s = 1 - p["dist"]
        if prefs and any(w in p["detail"] for w in prefs):
            s += 0.5
        if boost and any(w in p["detail"] for w in boost):
            s += 0.4
        if p["distance"]:
            s += max(0, 0.3 - p["distance"] / 5000)     # 0m → +0.3, 1500m → 0
        return s

    out, brands, subs = [], {}, {}
    for p in sorted(cands, key=score, reverse=True):
        if p["distance"] > radius or not p["lat"] or not p["lng"]:
            continue
        if p["name"] in seen_names or p["name"] in exclude:
            continue
        if ban and any(w in p["detail"] for w in ban):
            continue
        if "야구장" in p["name"] and p["category"] == "FOOD_OUT":
            continue                                    # 구장 앞 매대는 식사 후보에서 뺀다
        b, sc = _brand(p), _subcat(p)
        if brands.get(b, 0) >= 1 or subs.get(sc, 0) >= 2:
            continue
        brands[b] = brands.get(b, 0) + 1
        subs[sc] = subs.get(sc, 0) + 1
        seen_names.add(p["name"])
        out.append(p)
        if len(out) >= k:
            break
    return out


# ── 3. 경기 정보 ─────────────────────────────────────────────────────────────
def find_game(code, question, today):
    """(game | None, assumed, upcoming). 날짜가 있으면 그날, 없으면 오늘 이후 첫 홈경기."""
    place = structured.STADIUM_PLACE.get(code)
    want = structured.date_in(question, today)
    games = [g for g in structured.games() if g["place"] == place and not g.get("canceled")]
    upcoming = [g for g in games if g["date"] >= today][:3]
    if want:
        hit = [g for g in games if g["date"] == want]
        return (hit[0], False, upcoming) if hit else (None, False, upcoming)
    return (upcoming[0], False, upcoming) if upcoming else (None, True, [])


def game_time_of(game):
    return game["time"] if game else DEFAULT_GAME_TIME


def is_evening(game):
    return game_time_of(game) >= EVENING_FROM


def _game_text(game, code):
    ko = STADIUM_KO.get(code, code)
    if game:
        d = datetime.strptime(game["date"], "%Y-%m-%d")
        return (f"{d.month}월 {d.day}일 {game['time']} {ko} · {game['home']} 홈 vs {game['away']} 원정 "
                f"(상태: {game['status'] or '경기 전'})")
    return f"{ko} · 경기 정보 없음 → 평일 저녁 경기 기준 {DEFAULT_GAME_TIME} 시작으로 가정"


def _date_ko(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.month}월 {d.day}일"


# ── 4. LLM 호출 + JSON 파싱 ───────────────────────────────────────────────────
def _candidates_text(cands, anchor):
    """후보 목록. 방위를 같이 줘서 LLM 이 한쪽 방향으로 모아 고르게 한다 (동선 짧아짐)."""
    lines = []
    for p in cands:
        where = f"{geo.bearing_label(anchor, p)}쪽 {p['distance']}m" if p["distance"] else "거리 정보 없음"
        walk = f"·도보 {timeline.walk_min(p['distance'])}분" if p["distance"] else ""
        lines.append(f"{p['key']} [{CAT_LABEL[p['category']]}] {p['name']} · {p['detail'] or '-'} · 구장 {where}{walk}")
    return "\n".join(lines)


def call_llm(question, game_text, cands, anchor, sl, evening):
    user = USER_TEMPLATE.format(
        game=game_text, candidates=_candidates_text(cands, anchor), question=question,
        situation=slots.prompt_line(sl) or "(특별한 조건 없음)",
        after_hint="야식·술집·카페" if evening else "카페·명소·산책",
    )
    t0 = time.perf_counter()
    out = llm().invoke([SystemMessage(content=SYSTEM), HumanMessage(content=user)]).content
    text = out if isinstance(out, str) else "".join(p.get("text", "") for p in out if isinstance(p, dict))
    return text, (time.perf_counter() - t0) * 1000


def parse_course(text, allowed):
    """LLM 출력 → (course, intro). 후보에 없는 키·잘못된 phase 는 버린다. 실패하면 (None, None)."""
    m = _JSON_BLOCK.search(text or "")
    if not m:
        return None, None
    raw = m.group(0)
    for candidate in (raw, raw.replace("\n", " ").replace(",}", "}").replace(",]", "]")):
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            data = None
    if not data:
        return None, None
    course, seen = [], set()
    for item in data.get("course") or []:
        key = str(item.get("place_key", "")).strip()
        phase = str(item.get("phase", "")).strip().upper()
        if key in allowed and phase in ("BEFORE", "GAME", "AFTER") and key not in seen:
            seen.add(key)
            course.append({"key": key, "phase": phase, "reason": str(item.get("reason") or "").strip()[:60]})
    intro = str(data.get("intro") or data.get("answer") or "").strip()
    return (course, intro) if course else (None, None)


def fallback_course(cands, evening, sl):
    """LLM 이 실패했을 때 코드가 만드는 기본 코스 (동행 금지 업종은 이미 후보에서 빠져 있다)."""
    by = {}
    for p in cands:
        by.setdefault(p["category"], []).append(p)
    bar = [p for p in by.get("FOOD_OUT", []) if any(w in p["detail"] for w in timeline.BAR_WORDS)]
    meal = [p for p in by.get("FOOD_OUT", []) if p not in bar]

    before = meal[:1] or by.get("FOOD_OUT", [])[:1]
    if evening:
        after = bar[:1] or by.get("CAFE", [])[:1] or by.get("SPOT", [])[:1]
    else:
        after = by.get("CAFE", [])[:1] or by.get("SPOT", [])[:1] or meal[1:2]

    course = [{"key": p["key"], "phase": "BEFORE", "reason": "경기 전 식사"} for p in before]
    course.append({"key": "STADIUM", "phase": "GAME", "reason": "경기 관람"})
    course += [{"key": p["key"], "phase": "AFTER",
                "reason": "경기 후 한잔" if evening else "경기 후 여유롭게"} for p in after[:1]]
    if sl["spare"] == "long" and by.get("SPOT"):
        spot = next((p for p in by["SPOT"] if p["key"] not in {c["key"] for c in course}), None)
        if spot:
            course.insert(0, {"key": spot["key"], "phase": "BEFORE", "reason": "경기 전 산책"})
    return course


# ── 5. 답변 조립 ─────────────────────────────────────────────────────────────
def build_answer(intro, course, lookup, tl, walk, sl, assumed):
    lines = [intro] if intro else []
    lines.append("")
    lines += timeline.text_lines(course, lookup, tl)
    tail = [x for x in (walk, f"코스 전체 {tl['totalMin'] // 60}시간 {tl['totalMin'] % 60}분") if x]
    if tail:
        lines.append("")
        lines.append(" · ".join(tail))
    if assumed:
        lines.append(f"경기 일정이 자료에 없어서 평일 저녁 경기 기준({DEFAULT_GAME_TIME} 시작)으로 짰어요.")
    if sl.get("note"):
        lines.append(sl["note"])
    lines.append(WARN_THIRD_PARTY)
    return "\n".join(lines).strip()


# ── 6. 진입점 ─────────────────────────────────────────────────────────────────
def answer(question, history=None, hint_stadium=None):
    history = history or []
    today = date.today().isoformat()
    timings, route = {}, []

    # ① 슬롯: 구장 → 취향·동행·여유·재추천
    code = detect_stadium(question)
    if code is None:
        for m in reversed(history):
            if m.get("role") == "user" and (c := detect_stadium(m["content"])):
                code = c
                route.append(f"carry:{c}")
                break
    if code is None and hint_stadium:
        code = hint_stadium
        route.append(f"hint:{hint_stadium}")
    if code is None or code == "OTHER":
        from ..persona import FIXED
        return {"answer": FIXED["clarify"], "sources": [], "route": "guard:clarify", "places": [], "timing": timings}

    sl = slots.parse(question, history)
    if sl["companion"]:
        route.append(f"with:{sl['companion']}")
    if sl["retry"]:
        route.append(f"retry:-{len(sl['exclude'])}")
    if sl["spare"] != "normal":
        route.append(f"spare:{sl['spare']}")

    # ② 경기
    t0 = time.perf_counter()
    game, assumed, upcoming = find_game(code, question, today)
    timings["structured_ms"] = round((time.perf_counter() - t0) * 1000)
    if game is None and not assumed:                     # 날짜를 콕 집었는데 그날 경기가 없다
        want = structured.date_in(question, today)
        games = "\n".join(f"- {structured._fmt(g, today)}" for g in upcoming) or "- 앞으로 남은 홈경기가 자료에 없어요"
        return {"answer": NO_GAME.format(date_ko=_date_ko(want), stadium_ko=STADIUM_KO.get(code, code), games=games),
                "sources": [], "route": f"course:{code}:no_game:{want}", "places": [], "timing": timings}
    evening = is_evening(game)
    game_text = _game_text(game, code)

    # ③ 후보 — 경기 전용/경기 후용 쿼리 2개를 임베딩 API 1회로
    radius = min(sl["radius"] or MAX_DISTANCE_M, TIGHT_DISTANCE_M if sl["spare"] == "tight" else MAX_DISTANCE_M)
    pref_text = " ".join(dict.fromkeys(sl["prefs"]))
    t0 = time.perf_counter()
    vec_meal, vec_after = embed_many([
        f"{question} 경기 전 식사 {pref_text}".strip(),
        f"{question} 경기 후 {'야식 술집 맥주' if evening else '카페 산책 명소'} {pref_text}".strip(),
    ])
    timings["embed_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    cands, seen = [], set()
    for category, which, k in SEARCHES:
        if sl["spare"] == "tight" and category == "SPOT":
            continue                                     # 촉박하면 명소는 후보에서 뺀다
        raw = search_places(vec_meal if which == "meal" else vec_after, code, category, k * 3)
        cands += pick(raw, k, sl, radius, seen_names=seen)
    timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000)
    if not cands:
        msg = NO_PLACES.format(stadium_ko=STADIUM_KO.get(code, code))
        if sl["retry"]:
            msg = "앞서 추천한 곳 말고는 조건에 맞는 데를 더 못 찾았어요. 취향이나 구장을 바꿔서 말씀해 주시면 다시 찾아볼게요!"
        return {"answer": msg, "sources": [], "route": f"course:{code}:no_places", "places": [], "timing": timings}

    for i, p in enumerate(cands, 1):
        p["key"] = f"P{i}"
    anchor = stadium_anchor(code)
    lookup = {p["key"]: p for p in cands}
    lookup["STADIUM"] = anchor

    # ④ LLM 1회 — 키만 고르고 인트로만 쓴다
    course, intro = None, None
    try:
        raw, ms = call_llm(question, game_text, cands, anchor, sl, evening)
        timings["llm_ms"] = round(ms)
        course, intro = parse_course(raw, set(lookup))
    except Exception:
        log.exception("course llm failed")
    if not course:
        course = fallback_course(cands, evening, sl)
        intro = f"{game_text.split(' (')[0]} 기준으로 코스를 짜 봤어요."
        route.append("fallback")

    if not any(c["phase"] == "GAME" for c in course):     # 구장은 항상 들어간다
        course.insert(min(1, len(course)), {"key": "STADIUM", "phase": "GAME", "reason": "경기 관람"})
    if sl["spare"] == "tight":                            # 촉박하면 경기 전은 한 곳만
        before = [c for c in course if c["phase"] == "BEFORE"][:1]
        course = before + [c for c in course if c["phase"] != "BEFORE"]
    course.sort(key=lambda c: {"BEFORE": 0, "GAME": 1, "AFTER": 2}[c["phase"]])

    # ⑤ 동선 — 총 도보가 길면 같은 카테고리의 가까운 후보로 교체
    course, swapped = geo.optimize(course, lookup, cands)
    if swapped:
        route.append("geo:swap")
    points = [lookup[c["key"]] for c in course]
    walk = geo.summary(points)

    # ⑥ 시간표 — 경기 시작에서 역산
    tl = timeline.build(course, lookup, game_time_of(game), geo.leg_minutes(points))

    # ⑦ 조립 — 이름·좌표·주소는 전부 DB 값, 시각·거리는 코드가 계산한 값
    places = []
    for c, row in zip(course, tl["rows"]):
        p = lookup[c["key"]]
        places.append({
            "phase": c["phase"], "name": p["name"], "lat": p["lat"], "lng": p["lng"],
            "category": "STADIUM" if c["key"] == "STADIUM" else CAT_LABEL[p["category"]],
            "placeId": p["placeId"], "address": p["address"], "placeUrl": p["placeUrl"],
            "distance": p["distance"], "reason": c["reason"],
            "time": row["time"], "stayMin": row["stayMin"],
        })
    sources = [{"doc_id": lookup[c["key"]]["doc_id"],
                "grade": "OFFICIAL" if c["key"] == "STADIUM" else "THIRD_PARTY",
                "category": "STADIUM" if c["key"] == "STADIUM" else lookup[c["key"]]["category"], "stadium": code}
               for c in course if lookup[c["key"]].get("doc_id")]

    text = build_answer(intro, course, lookup, tl, walk, sl, assumed)
    if not _WARN.search(text):
        text = f"{text}\n{WARN_THIRD_PARTY}"

    route.append(f"course:{code}:{game['date'] + ' ' + game['time'] if game else 'assumed'}:{len(cands)}cands")
    return {
        "answer": text, "sources": sources, "route": " ".join(route), "places": places, "timing": timings,
        "coursePayload": save.course_payload(places, stadium_ko=STADIUM_KO.get(code, code), game=game,
                                             walk_summary=walk, total_min=tl["totalMin"], slots_info=sl),
    }

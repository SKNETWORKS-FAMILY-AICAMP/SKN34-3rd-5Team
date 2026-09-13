"""순위·일정은 RAG 대신 DB 직접 조회 (노션 설계의 SCHEDULE_RANK 인텐트).

검색으로 찾으면 "다음 홈경기"처럼 오늘 날짜로 계산해야 하는 질문을 못 푼다.
여기서는 청크 본문을 정규식으로 구조화한 뒤, 파이썬이 직접 고르고 정렬한다.
"""
import re
from datetime import date, datetime, timedelta

from router import PLACE_ALIAS

TEAMS = "LG|두산|키움|SSG|KT|한화|삼성|KIA|롯데|NC"
TEAM_SYNONYM = {"엘지": "LG", "트윈스": "LG", "베어스": "두산", "히어로즈": "키움", "랜더스": "SSG",
                "위즈": "KT", "이글스": "한화", "라이온즈": "삼성", "기아": "KIA", "타이거즈": "KIA",
                "자이언츠": "롯데", "다이노스": "NC"}
STADIUM_PLACE = {"JAMSIL": "잠실구장", "GOCHEOK": "고척구장", "MUNHAK": "문학구장", "SUWON": "수원구장",
                 "DAEJEON": "대전구장", "DAEGU": "대구구장", "GWANGJU": "광주구장", "SAJIK": "사직구장",
                 "CHANGWON": "창원구장", "OTHER": "포항구장"}

# "2026-09-12 17:00에 잠실구장에서 NC 원정팀과 두산 홈팀이 경기를 진행합니다. 경기 상태는 경기 전입니다."
# "... 경기 상태는 경기 종료입니다. 최종 스코어는 삼성 0 - 두산 4로 두산이 승리했습니다."
RE_GAME = re.compile(rf"(\d{{4}}-\d{{2}}-\d{{2}})\s+(\d{{2}}:\d{{2}})에\s*(\S+?)에서\s*({TEAMS})\s*원정팀과\s*({TEAMS})\s*홈팀")
RE_STATUS = re.compile(r"경기 상태는\s*(.+?)입니다")
RE_SCORE = re.compile(rf"최종 스코어는\s*({TEAMS})\s*(\d+)\s*-\s*({TEAMS})\s*(\d+)로\s*({TEAMS})\s*(?:이|가)\s*승리")
# "2026 시즌 KBO 순위에서 삼성는 1위입니다. 총 121경기를 ... 72승 46패 3무 ... 승률은 0.610이고 게임차는 0.0"
RE_RANK = re.compile(rf"({TEAMS})[는은]?\s*(\d+)위입니다.*?(\d+)경기.*?(\d+)승\s*(\d+)패\s*(\d+)무.*?승률은\s*([\d.]+).*?게임차는\s*([\d.]+)")

EXCLUDE_RANK = re.compile(r"타율|홈런|방어율|평균자책|선수|투수|타자|득점권|MVP")   # 선수 기록은 데이터에 없음 → 거절 경로
ASK_RANK = re.compile(
    r"순위|몇\s*위|승률|게임차|게임\s*차|경기\s*차|승차|선두|\d+\s*위|일위|"
    r"꼴찌|꼴지|최하위|맨\s*밑|바닥|누가\s*(더\s*)?(높|잘|위|앞)|어디가\s*(더\s*)?(높|잘|위|앞)"
)
RE_NTH = re.compile(r"(\d{1,2})\s*위")
LAST = re.compile(r"꼴찌|꼴지|꼬리|최하위|맨\s*밑|바닥|10위|십위")
ASK_GAME = re.compile(r"경기|일정|홈경기|맞대결|상대|결과|스코어|이겼|졌|어디서|몇\s*시|시간|장소")
ASK_NEXT = re.compile(r"다음|담\s|이번\s*주|언제")
ASK_SCORE = re.compile(r"몇\s*대\s*몇|몇대몇|스코어|결과|점수|이겼|졌|승리|패배")
RE_MD = re.compile(r"(?<!\d)(\d{1,2})\s*(?:월\s*|[/.\-])\s*(\d{1,2})(?:\s*일)?(?!\d)")   # 9월 12일 · 9/12 · 9.12 · 09-12


def josa(word, with_batchim, without):
    """마지막 글자에 받침이 있으면 은/이/과, 없으면 는/가/와. 영문(LG·KT)은 받침 없는 쪽으로."""
    ch = word[-1]
    has = "가" <= ch <= "힣" and (ord(ch) - ord("가")) % 28 != 0
    return with_batchim if has else without


def place_in(question):
    """장소 이름이 직접 나올 때만 구장 확정 (팀 이름으로 홈구장을 추정하면 원정 경기를 놓친다)"""
    q = question.upper()
    hit = [code for code, words in PLACE_ALIAS.items() if any(w.upper() in q for w in words)]
    return STADIUM_PLACE.get(hit[0]) if len(hit) == 1 else None


def teams_in(question):
    """질문에 나온 팀을 나온 순서대로 전부 (별칭 포함)"""
    hits = []
    for m in re.finditer(rf"{TEAMS}|" + "|".join(map(re.escape, TEAM_SYNONYM)), question, re.IGNORECASE):
        word = m.group(0)
        team = TEAM_SYNONYM.get(word) or next((t for t in TEAMS.split("|") if t.upper() == word.upper()), None)
        if team and team not in hits:
            hits.append(team)
    return hits


def team_in(question):
    q = question.upper()
    for k, v in TEAM_SYNONYM.items():
        if k.upper() in q:
            return v
    m = re.search(TEAMS, q)
    return m[0] if m else None


def date_in(question, today):
    """질문 속 날짜 → 'YYYY-MM-DD' (오늘/내일/모레/N월 N일). 없으면 None"""
    t = date.fromisoformat(today)
    if "오늘" in question:
        return today
    if "그제" in question or "그저께" in question:
        return (t - timedelta(days=2)).isoformat()
    if "어제" in question:
        return (t - timedelta(days=1)).isoformat()
    if "내일" in question:
        return (t + timedelta(days=1)).isoformat()
    if "모레" in question:
        return (t + timedelta(days=2)).isoformat()
    m = RE_MD.search(question)
    return f"{t.year}-{int(m[1]):02d}-{int(m[2]):02d}" if m else None


def _rows(conn, category):
    return conn.execute(
        """SELECT content, left(coalesce(metadata->'metadata'->>'updated_at', metadata->>'updated_at', ''), 10) AS updated_at
           FROM llm_documentchunk WHERE metadata->>'category' = %s""", (category,)).fetchall()


def standings(conn):
    out = []
    for r in _rows(conn, "STANDING"):
        m = RE_RANK.search(r["content"].replace(",", ""))
        if m:
            out.append(dict(team=m[1], rank=int(m[2]), games=int(m[3]), win=int(m[4]), lose=int(m[5]),
                            draw=int(m[6]), rate=m[7], gb=m[8], as_of=r["updated_at"]))
    return sorted(out, key=lambda x: x["rank"])


def games(conn):
    out = []
    for r in _rows(conn, "SCHEDULE"):
        m = RE_GAME.search(r["content"])
        if not m:
            continue                                   # 포스트시즌 안내문 4건은 형식이 달라 건너뜀
        st = RE_STATUS.search(r["content"])
        sc = RE_SCORE.search(r["content"])
        out.append(dict(date=m[1], time=m[2], place=m[3], away=m[4], home=m[5],
                        status=st[1] if st else "", as_of=r["updated_at"],
                        score=f"{sc[1]} {sc[2]} - {sc[3]} {sc[4]} ({sc[5]} 승)" if sc else ""))
    return sorted(out, key=lambda g: (g["date"], g["time"]))


def _fmt(g, today):
    d = datetime.strptime(g["date"], "%Y-%m-%d")
    line = f"{d.month}월 {d.day}일 {g['time']} {g['place']} · {g['home']} 홈 vs {g['away']} 원정"
    if g["score"]:
        line += f" → {g['score']}"
    elif g["date"] < today:
        line += " (지난 경기, 결과 미반영)"
    return line


def answer(conn, question, today=None, hint_team=None, hint_place=None, hint_date=None, now=None):
    """순위·일정 질문이면 DB 값으로 만든 문장을, 아니면 None (→ RAG 로 넘어감). hint_*: 직전 대화에서 이어받은 팀·구장·날짜"""
    today = today or date.today().isoformat()
    now = now or datetime.now().strftime("%H:%M")      # 오늘 경기라도 시작 시각이 지났으면 지난 경기로 본다
    q_team, q_place, q_date = team_in(question), place_in(question), date_in(question, today)
    elliptical = not (q_team or q_place or q_date or RE_NTH.search(question) or LAST.search(question))
    # "다음 경기는?", "몇대몇이야?" 처럼 팀·구장·날짜·순위를 아무것도 안 적은 후속 질문일 때만 직전 대화를 이어받는다
    if not elliptical:                                 # 뭔가 명시했으면 직전 대화 힌트는 쓰지 않는다
        hint_team = hint_place = hint_date = None

    # ── 순위 ──────────────────────────────────────────────────────────────
    if ASK_RANK.search(question) and not EXCLUDE_RANK.search(question):
        table = standings(conn)
        if not table:
            return None
        as_of, team = table[0]["as_of"], q_team or hint_team
        tail = "순위는 매일 경기 끝나면 바뀌니까, 오늘 기준은 KBO 홈페이지에서 한 번 더 확인해 보세요!"
        if LAST.search(question) and not team:          # 꼴찌
            row = table[-1]
            return (f"{as_of} 기준으로 꼴찌는 {row['team']}{josa(row['team'], '이', '')}에요. "
                    f"{row['games']}경기 {row['win']}승 {row['lose']}패 {row['draw']}무, 승률 {row['rate']}, 1위와 {row['gb']}경기 차예요.\n{tail}")
        pair = teams_in(question)
        if len(pair) >= 2 and ("차" in question or "비교" in question or "누가" in question or "높" in question):
            rows_ = [t for t in table if t["team"] in pair[:2]]
            if len(rows_) == 2:
                a, b = rows_[0], rows_[1]        # 순위 오름차순
                gap = round(float(b["gb"]) - float(a["gb"]), 1)
                lines = "\n".join(f"- {t['rank']}위 {t['team']} ({t['win']}승 {t['lose']}패 {t['draw']}무, 승률 {t['rate']})" for t in rows_)
                gap_txt = "같은 승차예요" if gap == 0 else f"{gap}경기 차예요"
                return (f"{as_of} 기준으로 {a['team']}{josa(a['team'], '과', '와')} {b['team']}{josa(b['team'], '은', '는')} {gap_txt}. "
                        f"{a['team']}{josa(a['team'], '이', '가')} {a['rank']}위, {b['team']}{josa(b['team'], '이', '가')} {b['rank']}위예요.\n{lines}\n{tail}")
        nths = sorted({int(n) for n in RE_NTH.findall(question) if 1 <= int(n) <= 10})
        if nths and not team:                           # "1위랑 2위 게임차", "3위 어디야"
            rows_ = [t for t in table if t["rank"] in nths]
            lines = "\n".join(f"- {t['rank']}위 {t['team']} ({t['win']}승 {t['lose']}패 {t['draw']}무, 승률 {t['rate']}, 1위와 {t['gb']}경기 차)" for t in rows_)
            head = f"{as_of} 기준이에요."
            if len(rows_) == 2:
                gap = round(float(rows_[1]["gb"]) - float(rows_[0]["gb"]), 1)
                head = f"{as_of} 기준으로 {rows_[0]['team']}{josa(rows_[0]['team'], '과', '와')} {rows_[1]['team']}{josa(rows_[1]['team'], '은', '는')} {gap}경기 차예요."
            return f"{head}\n{lines}\n{tail}"
        if team:
            row = next((t for t in table if t["team"] == team), None)
            if not row:
                return None
            gap = "" if row["rank"] == 1 else f", 1위와 {row['gb']}경기 차"
            return (f"{as_of} 기준으로 {row['team']}{josa(team, '은', '는')} {row['rank']}위예요{' 🥇' if row['rank'] == 1 else ''}. "
                    f"{row['games']}경기 {row['win']}승 {row['lose']}패 {row['draw']}무, 승률 {row['rate']}{gap}예요.\n{tail}")
        lines = "\n".join(f"- {t['rank']}위 {t['team']} ({t['win']}승 {t['lose']}패 {t['draw']}무, 승률 {t['rate']})"
                          for t in table[:5])
        return f"{as_of} 기준 상위 5개 팀이에요.\n{lines}\n{tail}"

    # ── 일정 ──────────────────────────────────────────────────────────────
    score_q = bool(ASK_SCORE.search(question))
    if not ASK_GAME.search(question) and not score_q:
        return None
    team, when, place = q_team or hint_team, q_date, q_place or hint_place
    if score_q and not when:                           # "몇대몇이야?" → 직전 대화의 날짜, 없으면 오늘
        when = hint_date or today
    if not when and not ASK_NEXT.search(question):
        return None                                    # "경기장 규칙" 같은 일반 질문은 RAG 로
    rows = games(conn)
    if not rows:
        return None
    as_of = max((g["as_of"] for g in rows if g["as_of"]), default="")   # 비어 있지 않은 최신 기준일
    note = f"{as_of} 기준 일정이라 비가 오면 바뀔 수 있으니 당일에 한 번 더 확인해 보세요."

    if when:                                           # 특정 날짜
        hit = [g for g in rows if g["date"] == when
               and (not team or team in (g["home"], g["away"]))
               and (not place or g["place"] == place)]
        d = datetime.strptime(when, "%Y-%m-%d")
        label = f"{d.month}월 {d.day}일" + (f" {place[:-2]}" if place else "") + (f" {team}" if team else "")
        if not hit:
            if team:                                       # 팀 조건을 빼고 다시 → 전제가 틀렸으면 실제 경기로 정정
                actual = [g for g in rows if g["date"] == when and (not place or g["place"] == place)]
                if actual:
                    head = f"앗, {d.month}월 {d.day}일{' ' + place[:-2] if place else ''} 경기는 {team} 경기가 아니에요! 그날은 이 경기가 있어요."
                    return head + "\n" + "\n".join("- " + _fmt(g, today) for g in actual) + f"\n{note}"
                elsewhere = [g for g in rows if g["date"] == when and team in (g["home"], g["away"])]
                if elsewhere:
                    g = elsewhere[0]
                    where = place[:-2] if place else "거기"
                    return (f"{d.month}월 {d.day}일 {team} 경기는 {where}{josa(where, '이', '가')} 아니라 "
                            f"{g['place']}에서 해요.\n- " + _fmt(g, today) + f"\n{note}")
            return f"{label} 경기는 제가 가진 일정표에 없네요. 월요일 같은 이동일이거나 우천 취소일 수 있어요. KBO 홈페이지에서 한 번 확인해 보세요!"
        if score_q and not any(g["score"] for g in hit):    # 결과를 물었는데 스코어가 없음 → 이유를 솔직히
            why = ("아직 시작 전이거나 한창 진행 중이에요" if when >= today else f"제 자료가 {as_of} 기준이라 결과가 아직 안 들어왔어요, 죄송해요")
            return (f"{label} 경기 결과는 {why}.\n" + "\n".join("- " + _fmt(g, today).replace(" (지난 경기, 결과 미반영)", "") for g in hit)
                    + "\n실시간 스코어는 네이버 스포츠나 KBO 홈페이지에서 바로 보실 수 있어요!")
        return f"{label} 경기는 이거예요!\n" + "\n".join("- " + _fmt(g, today) for g in hit) + f"\n{note}"

    home_only = "홈경기" in question                    # 다음 경기
    started = lambda x: x["date"] < today or (x["date"] == today and x["time"] <= now)   # 이미 시작한 경기는 제외
    mine = [x for x in rows if (not team or team in (x["home"], x["away"]))
            and (not home_only or not team or x["home"] == team)
            and (not place or x["place"] == place)]
    future = [x for x in mine if not started(x)]
    if not future:
        return (f"{today} 이후 {team or ''} 경기가 제가 가진 일정표({rows[0]['date']}~{rows[-1]['date']})에는 없네요. "
                f"KBO 홈페이지에서 확인해 보세요!")
    g = future[0]
    today_done = [x for x in mine if x["date"] == today and x["time"] <= now]
    if today_done:                                  # 오늘 경기가 이미 시작했으면 그 사실을 알려주고 다음 일정으로
        t = today_done[0]
        note = (f"오늘 {t['time']} {t['home']} vs {t['away']} 경기는 이미 시작해서 그다음 일정으로 알려드려요."
                + (f" 결과는 {t['score']}예요." if t["score"] else "") + f"\n{note}")
    d = datetime.strptime(g["date"], "%Y-%m-%d")
    role = "홈경기" if team and g["home"] == team else ("원정경기" if team else "경기")
    if team:
        opp = g["away"] if g["home"] == team else g["home"]
        head = f"{team} 다음 {role}는 {d.month}월 {d.day}일 {g['time']}, {g['place']}에서 {opp}{josa(opp, '과', '와')} 붙어요!"
    else:
        head = f"가장 가까운 경기는 {d.month}월 {d.day}일 {g['time']}, {g['place']}에서 {g['home']} vs {g['away']}예요."
    return f"{head}\n{note}"

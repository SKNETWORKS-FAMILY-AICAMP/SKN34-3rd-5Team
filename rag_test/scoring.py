"""규칙 기반 채점. 같은 답변이면 몇 번을 돌려도 같은 점수가 나온다."""
import re

# 거절 / 경고 / 되묻기 문구 — chain.py 후처리도 같은 기준을 쓴다
REFUSE = re.compile(
    r"확인한 자료|찾을 수 없|알 수 없|확인할 수 없|확인이 어렵|확인 불가|"
    r"안내드리기 어렵|답변드리기 어렵|포함되어 있지 않|예매처에 문의|"
    r"(자료|일정|정보|기록)[^.\n]{0,25}없"   # "자료에 없습니다" "제공된 일정에는 ... 없습니다" 등 표현 변형 흡수
)
WARN = re.compile(r"비공식|제보 기준|공식 확인 전|확인되지 않|정확하지 않을|달라질 수|다를 수|바뀔 수|재확인|방문 전.{0,6}확인|가시기 전.{0,10}확인|현장.{0,8}확인")
CLARIFY = re.compile(r"어느 구장|어떤 구장|어느 야구장|어떤 야구장|구장을 알려|어느 팀|어떤 팀")


# ── 검색 지표 ───────────────────────────────────────────────────────────────
def rank_of(doc_ids, gold_patterns):
    """검색 결과 doc_id 목록에서 정답이 처음 나오는 순위(1부터). 없으면 None."""
    for i, d in enumerate(doc_ids, 1):
        if any(re.fullmatch(p, d) for p in gold_patterns):
            return i
    return None


def hit_at(ranks, k):
    return sum(1 for r in ranks if r and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks):
    return sum(1 / r for r in ranks if r) / len(ranks) if ranks else 0.0


# ── 생성 지표 ───────────────────────────────────────────────────────────────
def norm(s):
    return re.sub(r"[\s,]", "", s or "")  # "1,117 면" == "1117면"


def is_correct(answer, must, must_all=None):
    """must: 하나만 맞으면 정답 (표현이 여러 가지일 때) · must_all: 전부 들어가야 정답 (복합 질문)"""
    if must_all:
        a = norm(answer)
        return all(any(norm(alt) in a for alt in (m if isinstance(m, list) else [m])) for m in must_all)
    return any(norm(m) in norm(answer) for m in must)


def number_check(answer, evidence, question):
    """답변 속 두 자리 이상 숫자가 근거(검색 문맥+정답 청크)나 질문에 있는지. (검사한 개수, 근거 없는 숫자들)"""
    pool = norm(evidence + " " + question)
    checked, bad = 0, []
    for n in re.findall(r"\d[\d,.]*", answer):
        n = norm(n).strip(".")
        if len(n.replace(".", "")) < 2:
            continue  # "1위", "2개" 같은 한 자리는 제외
        checked += 1
        if n not in pool:
            bad.append(n)
    return checked, bad


def judge(q, answer):
    """문항 1개 → OK / 오답 / 전제동조 / 오거절 / 지어냄 / 되묻기실패"""
    refused = bool(REFUSE.search(answer))
    if q["expect"] == "refuse":
        return "OK" if refused else "지어냄"
    if q["expect"] == "clarify":
        return "OK" if CLARIFY.search(answer) else "되묻기실패"
    ok = (is_correct(answer, q.get("must", []), q.get("must_all"))
          if (q.get("must") or q.get("must_all")) else not refused)
    if ok:
        return "OK"
    if refused:
        return "오거절"
    return "전제동조" if q["expect"] == "correct" else "오답"

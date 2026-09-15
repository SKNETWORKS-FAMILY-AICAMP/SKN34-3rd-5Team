"""RAG 파이프라인 진입점 — 백엔드가 부르는 파일은 이것 하나.

## 성호 ChatService 와 붙는 방법

ChatService 는 `self.chain` 에 두 가지만 요구한다.

    self.chain.invoke({"question": q, "chat_history": messages}) -> str
    self.chain.stream({"question": q, "chat_history": messages}) -> str 청크들

그래서 여기서 그 규격을 그대로 만족하는 Runnable(`chat_chain()`)을 만들어 준다.
ChatService 쪽 변경은 import 1줄 + chain 고르는 1줄이 전부다.

    from .rag.pipeline import chat_chain          # 추가
    self.chain = chat_chain() or self.get_chain() # CHAT_USE_RAG=0 이면 기존 체인 그대로

`chat_chain()` 은 CHAT_USE_RAG 가 꺼져 있으면 None 을 돌려주므로,
환경변수만 0 으로 두면 성호가 만든 예전 동작이 100% 그대로다 (테스트도 안 건드린다).

## 풍부한 결과가 필요할 때 (코스 추천 places 등)

체인은 문자열만 주므로, 장소 목록·근거·route 가 필요하면 함수를 직접 부른다.

    from llm.rag.pipeline import answer
    result = answer("잠실 주차 얼마야?", history=[...], stadium_name="잠실야구장")
    # {"answer", "sources", "route", "places", "coursePayload"}

## 입력

    question     : str   이번 질문. 프론트가 앞에 붙이는 "[선택한 구장: 잠실야구장]" 접두어는
                         여기서 떼어 stadium_name 으로 쓴다
    history      : 이전 대화 (이번 질문 제외, 오래된 것부터). 두 형식 다 받는다
                   - [{"role": "user"|"assistant", "content": "..."}, ...]   (프론트·게스트 형식)
                   - [HumanMessage(...), AIMessage(...), ...]                 (DjangoChatMessageHistory)
    stadium_name : "잠실야구장" 같은 프론트 context.stadium 값. 없으면 None
    intent       : "route" | "baseball" | "stadium". "route" 면 코스 추천. 없으면 None
                   (dispatcher 가 아직 intent 를 안 받는 버전이면 자동으로 안 넘긴다)

## 흐름

    ① history 정리 · 구장 접두어 분리                          LLM 0회
    ② dispatcher.route()   course / club / venue / both / scope  LLM 0회
    ③ 도메인 answer()      course: 경기+장소 조회 → ChatOpenAI 1회
                           club:   라우터 → 직접조회 or 검색 → ChatOpenAI 1회
                           venue:  create_agent 도구 호출 (2~3회)
    ④ persona.finalize()   말투 통일                            LLM 0회

LangSmith: backend/.env 에 LANGSMITH_TRACING=true · LANGSMITH_API_KEY · LANGSMITH_PROJECT 를 넣으면
           answer() 한 번이 트리 하나로 기록된다. env 가 없으면 오버헤드 0.
"""
import inspect
import os
import re
from typing import Any, Iterator, Optional

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig

try:                                          # langsmith 는 langchain-core 의존성이라 보통 있다
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree
except ImportError:                           # pragma: no cover
    def traceable(*_a, **_k):
        return lambda f: f

    def get_current_run_tree():
        return None

from . import dispatcher

_ROLE = {"human": "user", "ai": "assistant", "user": "user", "assistant": "assistant"}
_STADIUM_PREFIX = re.compile(r"^\s*\[선택한 구장:\s*([^\]]+)\]\s*")   # 프론트가 붙이는 접두어
# dispatcher 에 course 가 들어오기 전/후 둘 다에서 돌게 한다
_HAS_INTENT = "intent" in inspect.signature(dispatcher.answer).parameters

STREAM_CHUNK = 24          # RAG 답은 한 번에 완성되므로 이만큼씩 끊어 흘린다 (화면 타이핑 효과)


def use_rag() -> bool:
    """CHAT_USE_RAG=1 일 때만 RAG 를 쓴다. 기본값은 0 — 켜야만 동작이 바뀐다."""
    return os.getenv("CHAT_USE_RAG", "0").strip().lower() in ("1", "true", "yes", "on")


def split_stadium_prefix(question: str) -> tuple[str, Optional[str]]:
    """'[선택한 구장: 잠실야구장]\\n잠실 주차 얼마야?' → ('잠실 주차 얼마야?', '잠실야구장')"""
    m = _STADIUM_PREFIX.match(question or "")
    if not m:
        return (question or "").strip(), None
    return question[m.end():].strip(), m.group(1).strip()


def normalize_history(history) -> list[dict]:
    """LangChain 메시지든 dict 든 [{"role","content"}] 로 맞춘다.

    회원 경로는 DjangoChatMessageHistory.messages (HumanMessage/AIMessage),
    게스트 경로(GuestChatView)도 HumanMessage/AIMessage 로 만들어 넘겨준다.
    system 등 그 외 역할은 버리고, 구장 접두어도 뗀다.
    """
    out = []
    for m in history or []:
        if isinstance(m, BaseMessage):
            role, content = _ROLE.get(m.type), m.content
        elif isinstance(m, dict):
            role, content = _ROLE.get(m.get("role")), m.get("content")
        else:
            continue
        if role and isinstance(content, str):
            out.append({"role": role, "content": split_stadium_prefix(content)[0]})
    return out


def _tag(result: dict, extra: dict):
    """LangSmith 가 켜져 있으면 route 를 run metadata 로 남긴다 (꺼져 있으면 no-op)"""
    try:
        rt = get_current_run_tree()
        if rt is not None:
            rt.add_metadata({"route": result.get("route", ""),
                             "n_sources": len(result.get("sources") or []),
                             "n_places": len(result.get("places") or []), **extra})
    except Exception:
        pass


@traceable(run_type="chain", name="kbo_rag.answer")
def answer(question: str, history=None, stadium_name: Optional[str] = None,
           intent: Optional[str] = None) -> dict:
    """RAG 실행. 반환 {"answer", "sources", "route", "places", "coursePayload", "question"}

    question 키에는 구장 접두어를 뗀 질문이 들어간다 (대화 기록에 저장할 때 쓰라고).
    """
    q, prefixed = split_stadium_prefix(question)
    stadium_name = stadium_name or prefixed
    kwargs = {"intent": intent} if _HAS_INTENT else {}
    result = dispatcher.answer(q, history=normalize_history(history), stadium_name=stadium_name, **kwargs)
    result.setdefault("places", [])
    result.setdefault("coursePayload", None)
    result["question"] = q
    _tag(result, {"stadium_name": stadium_name or "", "intent": intent or ""})
    return result


# ── 성호 ChatService 의 self.chain 자리에 그대로 꽂히는 Runnable ──────────────────
class RagChatChain(Runnable[dict, str]):
    """{"question", "chat_history"} → 답변 문자열. invoke 와 stream 둘 다 지원한다.

    ChatService.invoke_with_messages 는 .invoke() 를,
    ChatService.stream_with_history 는 .stream() 을 부른다 — 둘 다 여기로 온다.

    RAG 는 답을 한 번에 만들기 때문에 .stream() 은 완성된 답을 잘라서 흘린다.
    (화면에는 똑같이 한 글자씩 찍히고, 프론트 SSE 계약도 그대로다)
    """

    name = "kbo_rag_chain"

    @staticmethod
    def _args(inputs: Any) -> dict:
        if isinstance(inputs, str):
            return {"question": inputs, "history": None, "stadium_name": None, "intent": None}
        inputs = inputs or {}
        return {
            "question": inputs.get("question") or "",
            # chat_history 는 성호 체인 키, history 는 우리 키 — 둘 다 받는다
            "history": inputs.get("chat_history") if inputs.get("chat_history") is not None
            else inputs.get("history"),
            "stadium_name": inputs.get("stadium_name"),
            "intent": inputs.get("intent"),
        }

    def detail(self, inputs: Any) -> dict:
        """places·sources 까지 필요할 때 (뷰에서 코스 저장 payload 를 쓸 때)"""
        return answer(**self._args(inputs))

    def invoke(self, input: Any, config: Optional[RunnableConfig] = None, **kwargs) -> str:
        return self.detail(input)["answer"]

    def stream(self, input: Any, config: Optional[RunnableConfig] = None,
               **kwargs) -> Iterator[str]:
        text = self.invoke(input, config, **kwargs)
        for i in range(0, len(text), STREAM_CHUNK):
            yield text[i:i + STREAM_CHUNK]


rag_chain = RagChatChain()


def chat_chain() -> Optional[RagChatChain]:
    """CHAT_USE_RAG 가 켜져 있으면 RAG 체인을, 꺼져 있으면 None 을 돌려준다.

    ChatService 는 `self.chain = chat_chain() or self.get_chain()` 한 줄로 쓴다.
    """
    return rag_chain if use_rag() else None

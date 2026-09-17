"""직접 물어보는 테스트 화면 (Streamlit, 채팅형 — 이어 묻기 가능)
실행: streamlit run rag_test\app_ui.py   →  http://localhost:8501
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # rag_test 안의 모듈 import 용

import streamlit as st

from chain import answer, grade
from common import LLM_MODEL, connect, embed, load_golden
from router import detect_categories, detect_stadium

st.set_page_config(page_title="KBO 직관 챗봇 테스트", layout="wide")


@st.cache_resource                      # DB 연결은 한 번만
def db():
    return connect()


if "chat" not in st.session_state:      # [{'role','content', 'meta'}, ...]
    st.session_state.chat = []

with st.sidebar:
    st.title("KBO 직관 안내 RAG")
    st.caption(f"모델 {LLM_MODEL} · 로컬 도커 DB")
    mode = st.radio("모드", ["SV", "G2", "G1", "G0"], index=0,
                    help="SV=서비스용(이어 묻기·순위/일정 직접조회) · G2=평가용 · G1=기본 RAG · G0=LLM만")
    golden = load_golden("golden_club.jsonl")
    pick = st.selectbox("골든셋에서 고르기", ["(직접 입력)"] + [f"{q['id']} {q['question']}" for q in golden])
    if st.button("대화 새로 시작"):
        st.session_state.chat = []
        st.rerun()

st.subheader("대화")
for m in st.session_state.chat:                              # 지난 대화 그리기
    with st.chat_message(m["role"]):
        st.markdown(m["content"].replace("\n", "  \n"))
        if m.get("meta"):
            st.caption(m["meta"])
        if m.get("rows"):
            with st.expander(f"근거 청크 {len(m['rows'])}건"):
                st.table(m["rows"])

question = st.chat_input("질문을 입력하세요 (예: 잠실 주차 얼마야? → 재입장은?)")
if not question and not pick.startswith("("):
    if st.sidebar.button("이 질문 보내기"):
        question = pick.split(" ", 1)[1]

if question:
    with st.chat_message("user"):
        st.markdown(question)
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat]
    with st.chat_message("assistant"), st.spinner("생각 중..."):
        r = answer(db(), mode, question, embed([question])[0], history=history)
        st.markdown(r["answer"].replace("\n", "  \n"))
        meta = (f"{mode} · 라우터 구장={detect_stadium(question) or '-'} 카테고리={','.join(detect_categories(question)) or '-'}"
                f" · 가드={r['guard'] or '-'} · 검색 {r['retrieval_ms']:.0f}ms · 생성 {r['llm_ms']:.0f}ms")
        st.caption(meta)
        rows = [{"순위": i, "등급": grade(x), "doc_id": x["doc_id"], "구장": x["stadium"], "카테고리": x["category"],
                 "기준일": x.get("updated_at") or "", "거리": round(x["dist"], 3), "내용": x["content"][:160]}
                for i, x in enumerate(r["rows"], 1)]
        if rows:
            with st.expander(f"근거 청크 {len(rows)}건"):
                st.table(rows)
    st.session_state.chat += [{"role": "user", "content": question},
                              {"role": "assistant", "content": r["answer"], "meta": meta, "rows": rows}]

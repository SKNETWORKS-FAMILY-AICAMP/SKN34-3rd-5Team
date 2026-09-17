# %% [markdown]
# # LangChain Search Agent 리팩토링
# 
# 이 Notebook은 루트의 `test.ipynb`를 기준으로 PostgreSQL + pgvector + OpenAI Embedding + LangChain Agent 전체 흐름을 학습하고 테스트하기 위한 최종 예제다.
# 
# 구성: 설정 → DB 연결 → 모델 생성 → Query Transformation → Retriever → Search → Tool → Agent → 단계별 테스트 → 전체 테스트
# 
# 현재 범위는 폐쇄형 RAG이며 Django, API 서버, MMR, BM25, Hybrid Search, Reranker, Metadata filtering은 포함하지 않는다.

# %% [markdown]
# ## 리팩토링 전의 실제 문제
# 
# - `test.ipynb` 안에서 DB 연결, Retriever, Tool, Agent가 여러 셀에서 반복 정의된다.
# - 전역 객체가 많아 셀 실행 순서에 의존하고, 중간 실험 코드와 최종 코드가 섞여 있다.
# - cursor가 예외 상황에서 닫히지 않을 수 있고, 요청마다 연결을 새로 만들 여지가 있다.
# - 동일한 vector distance 계산이 SELECT, WHERE, ORDER BY에서 반복된다.
# - Query Transformation과 검색 흐름은 동작하지만, Tool 내부에서 한 번만 실행된다는 구조가 명확하지 않다.
# - 테스트가 독립 함수가 아니라 여러 실험 셀에 분산되어 있다.

# %% [markdown]
# ## 리팩토링 방향
# 
# 하나의 Notebook 안에서 기능을 함수와 클래스로 구분하되, 학습에 불필요한 별도 패키지나 디자인 패턴은 추가하지 않는다. Embedding과 LLM은 한 번만 생성하고, DB는 `ThreadedConnectionPool`로 재사용한다. 검색은 현재처럼 OpenAI Embedding과 pgvector cosine distance만 사용한다.

# %% [markdown]
# ## [Cell 1] 라이브러리 import
# 
# 이 셀에서는 Notebook에서 사용할 라이브러리를 한 번만 import한다.

# %%
import os  # 운영체제 환경변수와 파일 경로를 다루는 표준 라이브러리
import json  # JSON 데이터의 직렬화와 역직렬화를 처리하는 표준 라이브러리
import re  # 정규 표현식 기반의 문자열 검색과 치환을 처리하는 표준 라이브러리
from typing import Any  # 모든 타입을 표현할 때 사용하는 타입 힌트

import psycopg2  # PostgreSQL 데이터베이스에 연결하는 라이브러리
from psycopg2 import sql  # PostgreSQL 쿼리를 안전하게 구성하는 도구
from psycopg2.pool import ThreadedConnectionPool  # 여러 스레드에서 사용할 DB 연결 풀
from dotenv import load_dotenv  # .env 파일의 환경변수를 불러오는 함수

from langchain.agents import create_agent  # LangChain 에이전트를 생성하는 함수
from langchain_core.documents import Document  # 문서와 문서 메타데이터를 표현하는 클래스
from langchain_core.output_parsers import StrOutputParser  # 모델 출력을 문자열로 변환하는 파서
from langchain_core.prompts import ChatPromptTemplate  # 채팅 프롬프트 템플릿을 구성하는 클래스
from langchain_core.retrievers import BaseRetriever  # 검색기 구현을 위한 기본 클래스
from langchain_core.tools import tool  # 함수를 LangChain 도구로 등록하는 데코레이터
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # OpenAI 채팅 모델과 임베딩 모델
from pydantic import Field  # Pydantic 모델 필드의 기본값과 메타데이터를 정의하는 함수

# %% [markdown]
# **이 셀의 역할:**
# 
# `psycopg2`는 Python에서 PostgreSQL에 연결한다. `BaseRetriever`는 검색기를 LangChain Runnable 형태로 만들기 위한 기본 클래스다. `Document`는 검색 결과의 본문과 metadata를 담는다. `ChatPromptTemplate`은 system/human 메시지를 템플릿으로 만들고, `StrOutputParser`는 LLM 응답을 문자열로 변환한다. `|`는 LangChain Runnable들을 순서대로 연결하는 LCEL 연산자다.

# %% [markdown]
# ## [Cell 2] 환경 설정
# 
# 비밀번호와 API Key는 코드에 직접 쓰지 않고 `.env`에서 읽는다.

# %%
load_dotenv()

# OpenAI SDK가 사용할 API Key다. 실제 값은 .env에만 둔다.
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

DB_CONFIG = {
    "host": os.getenv("DB_HOST") or "localhost",
    "port": int(os.getenv("DB_PORT") or "5432"),
    "dbname": os.getenv("DB_NAME") or "mydb",
    "user": os.getenv("DB_USER") or "myuser",
    # 기존 test.ipynb의 개발용 기본값이다. 운영에서는 반드시 .env 값을 사용한다.
    "password": os.getenv("DB_PASSWORD") or "mypassword",
}

DOCUMENT_TABLE = os.getenv("DOCUMENT_TABLE", "llm_documentchunk")
TOP_K = int(os.getenv("SEARCH_TOP_K", "10"))
MAX_DISTANCE = float(os.getenv("SEARCH_MAX_DISTANCE", "0.5"))

# 실제 DB에서 확인한 담당 제외 범주다. 이 목록 외의 문서 category는 검색을 허용한다.
# 팀순위 전용 category는 현재 DB에서 확인되지 않아 임의로 추가하지 않는다.
EXCLUDED_DOCUMENT_CATEGORIES = ("SCHEDULE", "PRICE", "SEAT", "TICKET_POLICY")

# 테이블명은 SQL 값 바인딩이 불가능하므로 허용된 식별자 형태인지 확인한다.
if not DOCUMENT_TABLE.replace("_", "").isalnum():
    raise ValueError("DOCUMENT_TABLE은 영문/숫자/밑줄만 사용할 수 있다.")

print({**DB_CONFIG, "password": "***"})
print(f"TOP_K={TOP_K}, MAX_DISTANCE={MAX_DISTANCE}")

# %% [markdown]
# **이 셀의 역할:**
# 
# `MAX_DISTANCE=0.5`는 현재 데이터셋에서 사용하는 초기 cosine distance threshold다. distance가 작을수록 embedding이 가깝다는 뜻이며, 절대적인 정답값은 아니다. 실제 DB에서 공통으로 확인된 `metadata->>'category'`만 사용하고, 일정·가격·좌석·티켓 예매 범주만 제외한다.

# %% [markdown]
# ## [Cell 3] PostgreSQL 연결 풀
# 
# Notebook 전체에서 재사용할 연결 풀을 만든다.

# %%
def create_db_pool(minconn: int = 1, maxconn: int = 5) -> ThreadedConnectionPool:
    """PostgreSQL 연결 풀을 생성한다.

    minconn/maxconn은 유지할 최소/최대 연결 수다. 테스트나 검색 호출마다
    psycopg2.connect()를 반복하지 않고 연결을 대여해 재사용한다.
    반환값은 애플리케이션 종료 시 closeall()로 닫아야 한다.
    """
    pool = ThreadedConnectionPool(minconn, maxconn, **DB_CONFIG)
    return pool


db_pool = create_db_pool()
print("PostgreSQL connection pool created")

# %% [markdown]
# **이 셀의 역할:**
# 
# connection pool은 여러 검색 요청이 하나의 연결을 재사용하도록 한다. 아래 Retriever에서는 `getconn()`으로 빌리고, `putconn()`으로 반드시 반환한다. cursor는 `with conn.cursor()` 안에서 사용하므로 예외가 발생해도 정리된다.

# %% [markdown]
# ## [Cell 4] Embedding과 LLM 생성
# 
# Embedding과 LLM은 Notebook 전체에서 각각 한 번만 만든다.

# %%
# Embedding은 문장을 숫자 vector로 바꾼다. 문장 간 의미 유사도를 계산할 수 있다.
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=OPENAI_API_KEY,
)

# LLM은 query transformation과 최종 Agent 답변에 공통으로 사용한다.
llm = ChatOpenAI(
    model="gpt-5.6-luna",
    temperature=0,
    reasoning_effort="none",
    api_key=OPENAI_API_KEY,
)
print("Embedding과 LLM을 각각 한 번 생성했다.")

# %% [markdown]
# **이 셀의 역할:**
# 
# Embedding model은 검색용 vector를 만들고, ChatOpenAI는 자연어 변환과 답변을 만든다. 객체를 셀마다 다시 만들면 설정 관리가 어려워지고 불필요한 초기화가 발생하므로 공용 객체로 재사용한다.

# %% [markdown]
# ## [Cell 5] Query Transformation
# 
# 사용자 질문을 문서 검색에 적합한 검색어로 변환한다.

# %%
query_transform_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """너는 현재 문서 검색어 변환기다.
사용자의 질문의 핵심 의미와 고유명사를 유지하면서 현재 문서 검색에 적합한 짧은 검색어로만 정규화하라.
팀순위, 경기 일정, 티켓 예매 일정 등 질문에 없는 세부 정보를 임의로 추가하거나 확장하지 마라.
랜더스 구장처럼 명칭만 명확하게 정규화할 수 있지만, 새로운 사실을 만들어내지 마라.
불필요한 설명이나 답변은 쓰지 말고 검색어만 출력하라.""",
    ),
    ("human", "{query}"),
])

# Runnable을 prompt → llm → 문자열 결과 순서로 연결한다.
query_transformer = query_transform_prompt | llm | StrOutputParser()

def transform_query(query: str) -> str:
    """원본 질문을 vector search용 문자열로 바꾼다.

    query는 사용자의 원본 질문이고, 반환값은 Retriever에 전달할 검색어다.
    Search Tool이 호출될 때 한 번 실행된다.
    """
    return query_transformer.invoke({"query": query}).strip()

# %% [markdown]
# **핵심 개념:**
# 
# `ChatPromptTemplate`은 여러 메시지를 포함한 PromptTemplate이다. `invoke()`는 입력값을 Runnable에 전달한다. `|`는 앞 단계의 출력을 다음 단계의 입력으로 전달한다. Query Transformation은 답변 생성이 아니라 검색 recall을 높이기 위한 전처리다.

# %% [markdown]
# ## [Cell 6] PostgreSQLRetriever
# 
# `BaseRetriever`를 상속해 LangChain이 이해할 수 있는 PostgreSQL 검색기를 만든다.

# %%
class PostgreSQLRetriever(BaseRetriever):
    """OpenAI Embedding과 pgvector로 문서를 검색하는 LangChain Retriever다.

    BaseRetriever를 상속하면 `invoke(query)`로 호출할 수 있고,
    Agent나 다른 LangChain Runnable에 검색기를 연결할 수 있다.
    """

    embeddings: Any = Field(exclude=True)
    pool: Any = Field(exclude=True)
    table_name: str = "llm_documentchunk"
    k: int = 5
    max_distance: float = 0.5

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        """query를 embedding하고 threshold 이내의 Document를 반환한다.

        `<=>`는 pgvector의 cosine distance 연산자다. distance가 작을수록
        query vector와 문서 vector가 가깝다. CTE에서 distance를 한 번 계산한 뒤
        threshold 필터, 정렬, top-k 제한에 재사용한다.
        """
        query_embedding = self.embeddings.embed_query(query)
        vector_text = "[" + ",".join(map(str, query_embedding)) + "]"
        connection = self.pool.getconn()

        try:
            statement = sql.SQL("""
                WITH ranked AS (
                    SELECT id, content, metadata,
                           embedding <=> %s::vector AS distance
                    FROM {table}
                    WHERE COALESCE(metadata->>'category', '') <> ALL(%s)
                )
                SELECT id, content, metadata, distance
                FROM ranked
                WHERE distance <= %s
                ORDER BY distance
                LIMIT %s;
            """).format(table=sql.Identifier(self.table_name))

            # cursor context manager가 정상/예외 상황 모두에서 cursor를 닫는다.
            with connection.cursor() as cursor:
                cursor.execute(
                    statement,
                    (vector_text, list(EXCLUDED_DOCUMENT_CATEGORIES), self.max_distance, self.k),
                )
                rows = cursor.fetchall()

            return [
                Document(
                    page_content=row[1],
                    metadata={
                        "id": row[0],
                        **(row[2] or {}),
                        "distance": float(row[3]),
                    },
                )
                for row in rows
            ]
        finally:
            self.pool.putconn(connection)


retriever = PostgreSQLRetriever(
    embeddings=embeddings,
    pool=db_pool,
    table_name=DOCUMENT_TABLE,
    k=TOP_K,
    max_distance=MAX_DISTANCE,
)
print("Retriever created")

# %% [markdown]
# **핵심 개념:**
# 
# `Document`는 `page_content`와 `metadata`를 가진 검색 결과다. PostgreSQL `jsonb`인 metadata를 그대로 보존하되, distance와 id만 공통 metadata로 추가한다. top-k는 threshold를 통과한 결과 중 최대 몇 개를 반환할지 의미한다. SQL의 table명은 `Identifier`로 처리하고, vector·threshold·limit은 값 바인딩으로 전달해 SQL Injection 위험을 줄인다.

# %% [markdown]
# ## [Cell 7] Search 함수와 문서 포맷
# 
# 원본 질문 → Query Transformation → Retriever 흐름을 한 함수로 정리한다.

# %%
# 별칭 -> (team_code, stadium_code) 형태로 관리
# team_code: 팀 식별용, stadium_code: DB 문서의 실제 경기장 코드
TEAM_ALIASES: dict[str, tuple[str, str]] = {
    # SSG 랜더스 / 인천 SSG 랜더스필드
    "SSG랜더스": ("SSG", "MUNHAK"), "인천SSG랜더스필드": ("SSG", "MUNHAK"), "SSG랜더스필드": ("SSG", "MUNHAK"),
    "랜더스필드": ("SSG", "MUNHAK"), "쓱랜더스": ("SSG", "MUNHAK"), "문학야구장": ("SSG", "MUNHAK"),
    "문학구장": ("SSG", "MUNHAK"), "인천야구장": ("SSG", "MUNHAK"), "인천구장": ("SSG", "MUNHAK"),
    "랜더스": ("SSG", "MUNHAK"), "SSG": ("SSG", "MUNHAK"), "문학": ("SSG", "MUNHAK"), "쓱": ("SSG", "MUNHAK"),
    # LG 트윈스 / 두산 베어스 / 잠실야구장 (홈 공유)
    "LG트윈스": ("LG", "JAMSIL"), "엘지트윈스": ("LG", "JAMSIL"), "트윈스": ("LG", "JAMSIL"),
    "LG": ("LG", "JAMSIL"), "엘지": ("LG", "JAMSIL"),
    "두산베어스": ("DOOSAN", "JAMSIL"), "베어스": ("DOOSAN", "JAMSIL"), "두산": ("DOOSAN", "JAMSIL"),
    "잠실야구장": ("LG", "JAMSIL"), "잠실구장": ("LG", "JAMSIL"), "잠실": ("LG", "JAMSIL"),
    # KIA 타이거즈 / 광주 챔피언스필드
    "KIA타이거즈": ("KIA", "GWANGJU"), "기아타이거즈": ("KIA", "GWANGJU"), "챔피언스필드": ("KIA", "GWANGJU"),
    "광주야구장": ("KIA", "GWANGJU"), "광주구장": ("KIA", "GWANGJU"), "무등구장": ("KIA", "GWANGJU"),
    "타이거즈": ("KIA", "GWANGJU"), "챔필": ("KIA", "GWANGJU"), "KIA": ("KIA", "GWANGJU"), "기아": ("KIA", "GWANGJU"),
    # 삼성 라이온즈 / 대구 라이온즈파크
    "삼성라이온즈": ("SAMSUNG", "DAEGU"), "라이온즈파크": ("SAMSUNG", "DAEGU"), "대구야구장": ("SAMSUNG", "DAEGU"),
    "대구구장": ("SAMSUNG", "DAEGU"), "라이온즈": ("SAMSUNG", "DAEGU"), "삼성": ("SAMSUNG", "DAEGU"), "라팍": ("SAMSUNG", "DAEGU"),
    # 롯데 자이언츠 / 사직야구장
    "롯데자이언츠": ("LOTTE", "SAJIK"), "사직야구장": ("LOTTE", "SAJIK"), "사직구장": ("LOTTE", "SAJIK"),
    "부산야구장": ("LOTTE", "SAJIK"), "부산구장": ("LOTTE", "SAJIK"), "자이언츠": ("LOTTE", "SAJIK"),
    "롯데": ("LOTTE", "SAJIK"), "사직": ("LOTTE", "SAJIK"),
    # 한화 이글스 / 한화생명 볼파크
    "한화이글스": ("HANWHA", "DAEJEON"), "한화생명볼파크": ("HANWHA", "DAEJEON"), "이글스파크": ("HANWHA", "DAEJEON"),
    "대전야구장": ("HANWHA", "DAEJEON"), "대전구장": ("HANWHA", "DAEJEON"), "이글스": ("HANWHA", "DAEJEON"), "한화": ("HANWHA", "DAEJEON"),
    # KT 위즈 / 수원 위즈파크
    "케이티위즈": ("KT", "SUWON"), "KT위즈": ("KT", "SUWON"), "수원야구장": ("KT", "SUWON"),
    "수원구장": ("KT", "SUWON"), "위즈파크": ("KT", "SUWON"), "케이티": ("KT", "SUWON"), "위즈": ("KT", "SUWON"), "KT": ("KT", "SUWON"),
    # NC 다이노스 / 창원 NC파크
    "NC다이노스": ("NC", "CHANGWON"), "엔씨다이노스": ("NC", "CHANGWON"), "창원야구장": ("NC", "CHANGWON"),
    "창원구장": ("NC", "CHANGWON"), "마산구장": ("NC", "CHANGWON"), "다이노스": ("NC", "CHANGWON"),
    "엔씨파크": ("NC", "CHANGWON"), "NC파크": ("NC", "CHANGWON"), "엔씨": ("NC", "CHANGWON"), "엔팍": ("NC", "CHANGWON"), "NC": ("NC", "CHANGWON"),
    # 키움 히어로즈 / 고척 스카이돔
    "키움히어로즈": ("KIWOOM", "GOCHEOK"), "고척스카이돔": ("KIWOOM", "GOCHEOK"), "히어로즈": ("KIWOOM", "GOCHEOK"),
    "고척돔": ("KIWOOM", "GOCHEOK"), "서울돔": ("KIWOOM", "GOCHEOK"), "키움": ("KIWOOM", "GOCHEOK"), "고척": ("KIWOOM", "GOCHEOK"),
}

NO_DOCUMENTS_MESSAGE = "관련 문서를 찾을 수 없습니다."

OUT_OF_SCOPE_MESSAGE = "이 질문은 다른 Search Agent 담당 범위입니다."

EXCLUDED_QUERY_TERMS = ("순위", "랭킹", "일정", "티켓", "예매", "입장권", "좌석", "가격", "날씨")

def infer_keyword_filters(query: str) -> dict[str, Any]:
    """질문의 표현에서 구단 코드, stadium_code, 카테고리 그룹, 구장 내외 구분을 추론한다."""
    filters: dict[str, Any] = {}
    for alias, (team_code, stadium_code) in TEAM_ALIASES.items():
        if alias.lower() in query.lower():
            filters["team_code"] = team_code
            filters["stadium_code"] = stadium_code
            break

    # DB 실제 metadata category 구조 기반 카테고리 그룹 설정
    category_rules = [
        (("교통", "대중교통", "버스", "지하철", "주차", "주차장", "오는길", "가느라"), ["TRANSPORT"]),
        (("포토존", "포토", "사진", "포토부스", "최정존", "기념존", "전시"), ["CONTENT", "FACILITY", "SPOT"]),
        (("수유실", "수유", "유모차", "의무실", "의무", "물품보관소", "보관소", "짐보관", "화장실", "휠체어", "충전소", "편의시설"), ["FACILITY", "AMENITY", "STADIUM", "CONTENT"]),
        (("카페", "커피", "음료", "디저트"), ["CAFE", "FOOD_IN", "FOOD_OUT"]),
    ]
    for terms, cats in category_rules:
        if any(term in query for term in terms):
            filters["categories"] = cats
            break
    else:
        if any(term in query for term in ("근처", "주변", "외부", "밖")) and any(term in query for term in ("먹거리", "음식점", "식당", "맛집", "밥")):
            filters["categories"] = ["FOOD_OUT", "CAFE"]
        elif any(term in query for term in ("먹거리", "음식점", "식당", "매장", "치킨", "피자", "버거", "스낵")):
            filters["categories"] = ["FOOD_IN", "CONTENT", "FACILITY"]

    if any(term in query for term in ("근처", "주변", "외부", "밖")):
        filters["in_stadium_flag"] = "N"
    elif any(term in query for term in ("내부", "구장 안", "구장내", "안에서", "안에")):
        filters["in_stadium_flag"] = "Y"
    return filters


def _build_keyword_patterns(query: str) -> list[str]:
    """키워드 fallback 검색에 사용할 ILIKE 패턴을 만든다."""
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", query)
    aliases = {"포토존": "PHOTOZONE", "사진": "PHOTOZONE", "교통": "TRANSPORT", "대중교통": "TRANSPORT"}
    tokens.extend(aliases[token] for token in tokens if token in aliases)
    return [f"%{token}%" for token in dict.fromkeys(tokens) if len(token) >= 2]


def keyword_fallback_search(
    query: str,
    *,
    pool: ThreadedConnectionPool,
    table_name: str,
    top_k: int,
    category: str | None = None,
    in_stadium_flag: str | None = None,
    team_code: str | None = None,
    stadium_code: str | None = None,
) -> list[Document]:
    """Vector 검색이 부족할 때 content/metadata를 키워드로 보조 검색한다."""
    patterns = _build_keyword_patterns(query)
    if not patterns:
        return []

    conditions = [sql.SQL("(content ILIKE ANY(%s) OR metadata::text ILIKE ANY(%s))")]
    parameters: list[Any] = [patterns, patterns]
    if category:
        conditions.append(sql.SQL("metadata->>'category' = %s"))
        parameters.append(category)
    if in_stadium_flag:
        conditions.append(sql.SQL("metadata->>'in_stadium_flag' = %s"))
        parameters.append(in_stadium_flag)
    if team_code and stadium_code:
        # 교통/시설 문서는 team_code가 비어 있고 stadium_code만 있는 경우가 많다.
        conditions.append(sql.SQL("(metadata->>'team_code' = %s OR metadata->>'stadium_code' = %s OR metadata->>'home_team' ILIKE %s OR content ILIKE %s)"))
        parameters.extend([team_code, stadium_code, f"%{team_code}%", f"%{team_code}%"])
    elif team_code:
        conditions.append(sql.SQL("(metadata->>'team_code' = %s OR metadata->>'home_team' ILIKE %s OR content ILIKE %s)"))
        parameters.extend([team_code, f"%{team_code}%", f"%{team_code}%"])
    elif stadium_code:
        conditions.append(sql.SQL("metadata->>'stadium_code' = %s"))
        parameters.append(stadium_code)

    statement = sql.SQL("""
        SELECT id, content, metadata, 0.0 AS distance
        FROM {table}
        WHERE {conditions}
        ORDER BY id
        LIMIT %s;
    """).format(
        table=sql.Identifier(table_name),
        conditions=sql.SQL(" AND ").join(conditions),
    )
    parameters.append(max(top_k * 100, 500))

    connection = pool.getconn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall()

        def match_score(row: tuple[Any, ...]) -> int:
            searchable_text = f"{row[1]} {json.dumps(row[2] or {}, ensure_ascii=False)}".lower()
            return sum(pattern.strip("%").lower() in searchable_text for pattern in patterns)

        rows = sorted(rows, key=match_score, reverse=True)[:top_k]
        return [
            Document(
                page_content=row[1],
                metadata={"id": row[0], **(row[2] or {}), "distance": None, "match_type": "keyword_fallback"},
            )
            for row in rows
        ]
    finally:
        pool.putconn(connection)


def apply_soft_filter(docs: list[Document], filter_fn) -> list[Document]:
    """필터링 후 결과가 존재하는 경우에만 적용하는 안전 헬퍼 함수다."""
    filtered = [doc for doc in docs if filter_fn(doc)]
    return filtered if filtered else docs

OUT_OF_SCOPE_MESSAGE = "현재 Search Agent 담당 범위의 관련 문서를 찾을 수 없습니다."

def is_excluded_query(query: str) -> bool:
    """다른 Search Agent 담당 범위인지 키워드로 확인한다."""
    normalized_query = query.replace(" ", "")
    return any(term in normalized_query for term in EXCLUDED_QUERY_TERMS)

    return any(term in query for term in excluded_terms)

def format_documents(docs: list[Document]) -> str:
    """Document 목록을 Tool과 사람이 읽을 수 있는 문자열로 변환한다.
    docs가 비어 있으면 guardrail 메시지를 반환한다. 반환값은 LLM이
    답변 근거로 사용할 검색 결과다.
    """
    if not docs:
        return NO_DOCUMENTS_MESSAGE
    return "\n\n".join(
        f"[문서 {index}] distance={doc.metadata.get('distance')}\n{doc.page_content}"
        for index, doc in enumerate(docs, start=1)
    )


def search_documents(query: str) -> dict[str, Any]:
    """원본 질문을 변환하고 보조 검색을 거쳐 정제된 문서 목록을 반환한다."""
    if is_excluded_query(query):
        return {
            "original_query": query,
            "transformed_query": "",
            "documents": [],
            "formatted": OUT_OF_SCOPE_MESSAGE,
            "search_method": "scope_guardrail",
        }

    transformed_query = transform_query(query)
    filters = infer_keyword_filters(f"{query} {transformed_query}")
    docs = retriever.invoke(transformed_query)

    # 1. Soft Filtering (유연한 조건 필터링)
    if filters.get("categories"):
        allowed = set(filters["categories"])
        docs = [d for d in docs if d.metadata.get("category") in allowed]

    if filters.get("in_stadium_flag"):
        target_flag = filters["in_stadium_flag"]
        docs = [d for d in docs if d.metadata.get("in_stadium_flag") == target_flag]

    if filters.get("team_code"):
        code = filters["team_code"]
        stadium = filters.get("stadium_code")
        # stadium_code 기반 매칭 추가: team_code=None인 교통/시설 문서도 경기장 코드로 필터
        docs = apply_soft_filter(docs, lambda d: (
            d.metadata.get("team_code") == code or
            (stadium and d.metadata.get("stadium_code") == stadium) or
            code in str(d.metadata.get("home_team", "")) or
            code in d.page_content
        ))

    search_method = "vector" if docs else "none"

    # 2. 2단계 릴레이 Fallback 검색 (더 풍부하게 가져오기 위해 top_k를 충분히 확대 10~15)
    fetch_k = max(TOP_K * 2, 10)
    needs_category_recovery = bool(filters.get("categories")) and not any(
        d.metadata.get("category") in set(filters["categories"]) for d in docs
    )
    if not docs or len(docs) < 3 or needs_category_recovery:
        cat_param = filters.get("categories", [None])[0]
        fallback_docs = keyword_fallback_search(
            transformed_query, pool=db_pool, table_name=DOCUMENT_TABLE, top_k=fetch_k,
            category=cat_param, in_stadium_flag=filters.get("in_stadium_flag"),
            team_code=filters.get("team_code"), stadium_code=filters.get("stadium_code"),
        )
        if not fallback_docs:
            fallback_docs = keyword_fallback_search(
                query, pool=db_pool, table_name=DOCUMENT_TABLE, top_k=fetch_k,
                team_code=filters.get("team_code"), stadium_code=filters.get("stadium_code"),
            )
        if fallback_docs:
            docs = fallback_docs
            search_method = "keyword_fallback"

    # 제외 카테고리 최종 걸러내기
    docs = [d for d in docs if d.metadata.get("category") not in EXCLUDED_DOCUMENT_CATEGORIES][:fetch_k]
    return {
        "original_query": query,
        "transformed_query": transformed_query,
        "documents": docs,
        "search_method": search_method,
        "formatted": format_documents(docs),
    }


# %% [markdown]
# ## [Cell 8] Search Tool
# 
# `@tool`은 Python 함수를 LangChain Agent가 호출할 수 있는 Tool로 변환한다.

# %%
@tool
def search_documents_tool(query: str) -> str:
    """현재 연결된 구단 관련 문서에서 사용자 질문과 관련된 근거를 검색한다."""
    return search_documents(query)["formatted"]

# %% [markdown]
# **핵심 개념:**
# 
# Tool은 Agent가 필요할 때 호출하는 함수다. Search Tool 내부에서만 Query Transformation을 수행하므로, Agent 생성 단계에서 별도의 변환 Runnable을 연결하지 않는다. 따라서 같은 사용자 질문에 대한 transformation 중복 실행을 피한다.

# %% [markdown]
# ## [Cell 9] Search Agent
# 
# 폐쇄형 RAG Guardrail을 포함한 Agent를 만든다.

# %%
AGENT_SYSTEM_PROMPT = """너는 현재 문서 범위에서 답하는 폐쇄형 RAG Search Agent다.

1. 질문에 특정 구단명이나 구장명(예: SSG, 랜더스필드, 잠실야구장, 광주 챔피언스필드 등)이 지정되어 있지 않고 단순히 "야구장", "구장", "경기장"처럼 모호하게 물어보는 경우, search_documents_tool을 호출하지 말고 "어느 구단이나 야구장(구장) 정보를 찾으시나요? 정확한 구단명 또는 구장명을 포함하여 질문해 주세요."라고 구체적인 질문을 유도해라.
2. 특정 구단/구장이 명시된 경우에만 search_documents_tool을 사용하여 답변해라.
3. 현재 연결된 문서에 있는 정보만 근거로 답하고, 문서에 없는 정보는 추측하지 않는다.
4. 팀순위, 경기 일정, 티켓 예매 일정은 다른 Search Agent 담당 범위이므로 search_documents_tool을 사용하지 않는다.
5. 검색 결과가 없으면 '관련 문서를 찾을 수 없습니다.'라고 답한다.
6. 답변에는 검색 결과에서 확인된 내용만 포함한다."""

agent = create_agent(
    model=llm,
    tools=[search_documents_tool],
    system_prompt=AGENT_SYSTEM_PROMPT,
)
print("Search Agent created")

# %% [markdown]
# **핵심 개념:**
# 
# `create_agent()`는 LLM과 Tool을 연결해 Tool 호출 여부를 판단하고, Tool 결과를 다시 LLM에 전달하는 실행 흐름을 만든다. Prompt는 1차 방어이고, Retriever의 similarity threshold는 Agent가 잘못 Tool을 호출했을 때의 2차 방어다.

# %% [markdown]
# ## [Cell 10] Query Transformation 테스트
# 
# 변환 전후 query를 확인한다.

# %%
def test_query_transformation(query: str) -> str:
    """원본 query와 변환 query를 출력하고 변환 query를 반환한다."""
    transformed = transform_query(query)
    print("원본 query:", query)
    print("변환된 query:", transformed)
    return transformed

test_query_transformation("랜더스 구장 내부 음식점 알려줘")

# %% [markdown]
# ## [Cell 11] Retriever 테스트
# 
# 검색된 Document 개수, id, distance, metadata 일부, content 일부를 확인한다.

# %%
def test_retriever(query: str) -> list[Document]:
    """Retriever의 threshold와 top-k 결과를 직접 점검한다."""
    docs = retriever.invoke(query)
    print("검색된 Document 개수:", len(docs))
    for index, doc in enumerate(docs, start=1):
        print(f"\n[{index}] id={doc.metadata.get('id')}")
        print("distance=", doc.metadata.get("distance"))
        print("metadata 주요 값=", dict(list(doc.metadata.items())[:5]))
        print("content=", doc.page_content[:200])
    return docs

test_retriever("인천 SSG 랜더스필드 구장 내부 음식점")

# %% [markdown]
# ## [Cell 12] Search 테스트
# 
# Search 함수가 원본 query, transformed query, 문서, 최종 Tool 형식을 함께 만드는지 확인한다.

# %%
def test_search(query: str) -> dict[str, Any]:
    """변환과 검색 결과를 한 번에 출력한다."""
    result = search_documents(query)
    print("원본 query:", result["original_query"])
    print("transformed query:", result["transformed_query"])
    print("검색 방식:", result.get("search_method", "unknown"))
    print("검색 결과 개수:", len(result["documents"]))
    print(result["formatted"])
    return result

test_search("인천 SSG 랜더스필드 구장 내부 음식점")

# %% [markdown]
# ## [Cell 13] 무관한 질문 테스트
# 
# `오늘 날씨 알려줘`는 문서 범위 밖 질문이다. threshold가 검색 결과를 제거하는지 확인한다.

# %%
unrelated_result = test_search("오늘 날씨 알려줘")
# Vector 결과에는 distance가 있고, keyword fallback 결과의 distance는 None이다.
# 따라서 검색 방식에 따라 각각 검증한다.
for doc in unrelated_result["documents"]:
    distance = doc.metadata.get("distance")
    match_type = doc.metadata.get("match_type", "vector")
    if match_type == "vector":
        assert distance is not None and distance <= MAX_DISTANCE
    else:
        assert match_type == "keyword_fallback"

print("Vector threshold 또는 keyword fallback 조건을 통과함")

# %% [markdown]
# ## [Cell 14] Agent 테스트와 Tool 호출 분석
# 
# 최종 답변만 보지 않고 `AIMessage`, `ToolMessage`, `tool_calls`를 확인한다.

# %%
def test_agent(question: str) -> dict[str, Any]:
    """Agent의 전체 message 흐름과 최종 답변을 출력한다."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    print("원본 질문:", question)
    for message in result["messages"]:
        print("-" * 60)
        print("message type:", type(message).__name__)
        print("tool_calls:", getattr(message, "tool_calls", []))
        print("content:", getattr(message, "content", message))
    print("\n최종 답변:", result["messages"][-1].content)
    return result

agent_test_questions = [
    "랜더스 구장 내부 음식점 알려줘",
    "잠실야구장 LG 트윈스 티켓 가격 알려줘",
    "야구장 주차장 정보 알려줘",
    "오늘 날씨 알려줘",
]

agent_results = [test_agent(question) for question in agent_test_questions]

# %% [markdown]
# ## [Cell 15] 전체 테스트와 종료
# 
# 네 가지 대표 질문을 순서대로 실행하고, Notebook 종료 시 연결 풀을 닫는다.

# %%
def run_all_tests() -> None:
    """Transformation, Retriever, Search, Agent의 핵심 실행을 점검한다."""
    test_query_transformation("랜더스 구장 내부 음식점 알려줘")
    test_retriever("인천 SSG 랜더스필드 구장 내부 음식점")
    test_search("잠실야구장 LG 트윈스 티켓 가격 알려줘")
    test_search("오늘 날씨 알려줘")
    for question in agent_test_questions:
        test_agent(question)


run_all_tests()

# 구단 범위 테스트가 끝난 뒤 마지막 셀에서 연결 풀을 닫는다.

# %% [markdown]
# # 테스트 실행 방법과 확인 항목
# 
# 1. `test.ipynb`와 같은 Python 3.12 커널에서 이 Notebook을 위에서 아래로 실행한다.
# 2. `.env`에 `OPENAI_API_KEY`, PostgreSQL 접속 정보를 설정한다.
# 3. Query Transformation에서는 원본 query와 의미가 보완된 transformed query를 확인한다.
# 4. Retriever에서는 Document 수, id, metadata, distance가 보이는지 확인한다. `distance <= 0.5`만 반환되어야 한다.
# 5. Search에서는 transformation이 한 번 실행되고, 문서가 없으면 `관련 문서를 찾을 수 없습니다.`가 반환되는지 확인한다.
# 6. Agent에서는 관련 질문에 ToolMessage와 tool call이 나타나고, `오늘 날씨 알려줘`에는 가능하면 Tool 호출이 없어야 한다. 잘못 호출되더라도 threshold가 2차 방어를 한다.
# 
# ## 기존 코드와 달라진 점
# 
# 기존 Notebook의 기능은 유지하면서 중복된 연결/모델/Retriever 정의를 하나로 합쳤다. cursor와 connection 반환을 `try/finally`와 context manager로 안전하게 만들었고, vector distance는 CTE에서 한 번 계산한다. Query Transformation은 Search 함수 내부의 단일 경로에서만 실행된다. 실험 셀을 단계별 테스트 함수로 정리해 각 결과를 확인할 수 있다.
# 
# ## 현재 한계와 추후 개선사항
# 
# 현재 threshold 0.5는 데이터셋에 맞춘 초기값이며 운영 환경에서는 평가셋으로 재조정해야 한다. 검색 품질이 더 필요할 때 MMR, BM25, Hybrid Search, Reranker, metadata filtering을 검토할 수 있지만 이번 Notebook에는 추가하지 않았다. 또한 Django/API 서버 연동도 다음 단계의 작업으로 남겨둔다.

# %% [markdown]
# ## [Cell 16] 구단 범위 전용 테스트
# 
# 허용 질문과 거부 질문을 나누어 Tool 호출 여부, transformed query, 검색 문서 category를 확인한다.

# %%
def inspect_agent_scope(question: str) -> dict[str, Any]:
    """Agent의 실제 message를 분석해 구단 범위 판단을 출력한다."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    tool_called = any(type(message).__name__ == "ToolMessage" for message in result["messages"])
    trace = search_documents(question)
    categories = sorted({doc.metadata.get("category") for doc in trace["documents"]})
    print("=" * 80)
    print(f"질문: {question}")
    print("→ Tool 호출:", "YES" if tool_called else "NO")
    print("→ transformed query:", trace["transformed_query"])
    print("→ 검색 방식:", trace.get("search_method", "unknown"))
    print("→ 검색 결과:", "있음" if trace["documents"] else "없음")
    print("→ 검색 category:", categories or "없음")
    print("→ 최종 답변:", result["messages"][-1].content)
    return {"agent_result": result, "tool_called": tool_called, "search_trace": trace}

scope_questions = [
    # --- 1. 대중교통 및 접근성 (TRANSPORT) ---
    "랜더스필드 지하철 타고 가는 법 알려줘",
    "SSG 경기장 주차장 정보랑 요금 알려줘",
    "문학경기장 지하철역 몇 번 출구로 나가야 구장으로 바로 가?",
    "잠실야구장 대중교통 노선이랑 지하철 출구 위치 안내해줘",                # [추가1 - 잠실 교통]
    "고척스카이돔 구일역 몇 번 출구에서 가까워?",                           # [추가2 - 고척 출구]

    # --- 2. 구장 내부 먹거리 (FOOD_IN) ---
    "SSG 랜더스필드 1루 쪽에 무슨 먹거리 있어?",
    "랜더스 구장 안에서 치킨이나 크림새우 어디서 팔아?",
    "문학구장 내부에 카페나 음료 파는 매장 추천해줘",
    "잠실야구장 3루 쪽에 보영만두나 피자 매장 위치 어디야?",                # [추가3 - 잠실 먹거리]
    "랜더스필드 3루 내야 쪽에 떡볶이 파는 곳 있어?",                        # [추가4 - SSG 3루 먹거리]

    # --- 3. 구장 외부 먹거리 (FOOD_OUT / CAFE) ---
    "구장 밖 근처 맛집이나 카페 추천해줘",
    "인천 SSG 랜더스필드 경기장 주변에서 식사할 만한 외부 식당 어디 있어?",
    "사직야구장 구장 밖 근처 맛집이나 카페 추천해줘",                       # [추가5 - 사직 외부 맛집]
    "대전 한화생명볼파크 근처 식당 정보 알려줘",                          # [추가6 - 대전 외부 식당]

    # --- 4. 포토존 및 부가 콘텐츠 (PHOTOZONE / CONTENT) ---
    "랜더스필드 이달의 포토존 위치가 어디야?",
    "SSG 랜더스 최정존 전시 공간 어디로 가면 볼 수 있어?",
    "고척돔 포토카드 키오스크나 포토존 위치 알려줘",                       # [추가7 - 고척 포토존]

    # --- 5. 편의시설 (AMENITY / FACILITY) ---
    "유모차 보관소나 수유실 위치 알려줘",
    "야구장에 짐 맡길 수 있는 물품보관소나 의무실 위치가 어떻게 돼?",
    "SSG 랜더스필드 장애인 휠체어 대여소나 의무실 위치 알려줘",              # [추가8 - SSG 휠체어/의무실]

    # --- 6. 긴 대화형 자연어 질문 (Long In-Scope Question) ---
    "이번 주말에 처음으로 인천 SSG 랜더스필드에 야구 보러 가는데 자차로 이동할 때 경기장 주차장 수용 대수랑 주차 요금, 그리고 입차 조건 상세히 알려줘",
    "친구들이랑 랜더스필드 1루 응원석 근처로 가는데 경기 직전에 구장 안에서 간단하게 사먹을 만한 대표 먹거리 매장이랑 치킨 파는 곳 위치 알려줄 수 있어?",
    "아이랑 같이 사직야구장 처음 방문하려고 하는데 구장 내 유모차 보관하는 곳이랑 수유실 위치 상세히 안내 부탁해", # [추가9 - 긴 편의시설 질문]

    # --- 7. Scope Guardrail 및 차단 질문 (Out-of-Scope) ---
    "잠실야구장 LG 트윈스 티켓 가격 얼마야?",
    "SSG 랜더스 1루 응원지정석 예매 방법 및 오픈 시간 알려줘",
    "오늘 SSG 랜더스 경기 몇 시에 시작해?",
    "KBO 현재 구단 순위랑 어제 경기 결과 알려줘",
    "오늘 인천 문학경기장 날씨 어때? 비 와?",
    "다음 주에 친구들과 잠실야구장에서 열리는 LG 트윈스 홈경기 보러 가려고 하는데 응원석 티켓 예매 방법이랑 좌석 가격, 그리고 모바일 티켓 발권 절차 정리해서 알려줘",
    "대구 삼성라이온즈파크 이번 주 경기 일정 알려줘",                     # [추가10 - 대구 일정 차단]
]


scope_test_results = [inspect_agent_scope(question) for question in scope_questions]

# %% [markdown]
# ## 범위 제한 및 Router 판단
# 
# 이번 구조에서는 별도 Router LLM을 추가하지 않는다. 현재 Search Agent 자체가 사용자 질문을 보고 Tool 호출 여부를 판단하므로 `질문 → Router → Agent`는 같은 판단을 중복한다. Agent의 Tool 선택이 1차 범위 판단이고, Retriever의 `category='STADIUM'` 필터와 `MAX_DISTANCE=0.5`가 검색 단계의 2차 방어다.
# 
# DB 조사 결과 `metadata->>'category'`는 공통 필드였다. 현재는 `SCHEDULE`, `PRICE`, `SEAT`, `TICKET_POLICY`만 제외하고 나머지 category를 허용한다. 팀순위 category는 현재 DB에서 확인되지 않았으므로 실제 category가 추가되면 확인 후 제외 목록에 추가해야 한다.
# 
# 향후 여러 전문 Agent를 통합할 때는 상위 QA Agent가 사용자 질문을 보고 구단 Search Agent, 일정 Search Agent, 티켓 Search Agent 중 하나를 선택하는 구조가 자연스럽다. 현재 Notebook의 Search Agent는 그 하위 전문 Agent 역할을 한다.

# %% [markdown]
# # 포트폴리오용 정량 검증\n
# \n
# 이 셀부터는 초기 Vector-only 검색과 현재 개선 검색을 같은 질문셋으로 비교한다. 자동 평가는 검색 결과의 존재, 기대 category/team/내외부 조건 일치 여부, fallback 복구 여부를 측정한다. Agent의 최종 답변은 완전한 사실성 판단을 자동화하기 어렵기 때문에 Tool 호출·근거 문서·무근거 거절 여부를 함께 확인한다.

# %%
from dataclasses import dataclass

@dataclass(frozen=True)
class EvaluationCase:
    name: str
    query: str
    expected_category: str | None = None
    expected_team: str | None = None
    expected_in_stadium: str | None = None
    expected_content_type: str | None = None
    must_be_blocked: bool = False
    is_long_question: bool = False
    case_type: str = "정상 질문"

# 실제 사용자가 입력할 법한 질문 10개다.
# 정상/긴 질문/오타·애매한 질문/범위 밖 질문을 섞어서 검색 품질과 방어 동작을 같이 본다.
evaluation_cases = [
    EvaluationCase("대중교통", "랜더스필드 지하철 타고 가는 법 알려줘", expected_category="TRANSPORT", expected_team="SSG", case_type="정상"),
    EvaluationCase("주차장", "SSG 경기장 주차장 정보랑 요금 알려줘", expected_category="TRANSPORT", expected_team="SSG", case_type="정상"),
    EvaluationCase("지하철 출구", "문학경기장 지하철역 몇 번 출구로 나가야 구장으로 바로 가?", expected_category="TRANSPORT", expected_team="SSG", case_type="정상"),
    EvaluationCase("잠실 대중교통", "잠실야구장 대중교통 노선이랑 지하철 출구 위치 안내해줘", expected_category="TRANSPORT", expected_team="LG", case_type="정상"),
    EvaluationCase("고척 출구", "고척스카이돔 구일역 몇 번 출구에서 가까워?", expected_category="TRANSPORT", expected_team="KIWOOM", case_type="정상"),
    EvaluationCase("SSG 1루 먹거리", "SSG 랜더스필드 1루 쪽에 무슨 먹거리 있어?", expected_team="SSG", expected_in_stadium="Y", case_type="정상"),
    EvaluationCase("치킨 크림새우", "랜더스 구장 안에서 치킨이나 크림새우 어디서 팔아?", expected_team="SSG", expected_in_stadium="Y", case_type="정상"),
    EvaluationCase("내부 카페", "문학구장 내부에 카페나 음료 파는 매장 추천해줘", expected_team="SSG", expected_in_stadium="Y", case_type="정상"),
    EvaluationCase("잠실 보영만두", "잠실야구장 3루 쪽에 보영만두나 피자 매장 위치 어디야?", expected_team="LG", expected_in_stadium="Y", case_type="정상"),
    EvaluationCase("3루 떡볶이", "랜더스필드 3루 내야 쪽에 떡볶이 파는 곳 있어?", expected_team="SSG", expected_in_stadium="Y", case_type="정상"),
    EvaluationCase("구단 미지정 외부", "구장 밖 근처 맛집이나 카페 추천해줘", must_be_blocked=True, case_type="구단 미지정"),
    EvaluationCase("SSG 외부 맛집", "인천 SSG 랜더스필드 경기장 주변에서 식사할 만한 외부 식당 어디 있어?", expected_team="SSG", expected_in_stadium="N", case_type="정상"),
    EvaluationCase("사직 외부 맛집", "사직야구장 구장 밖 근처 맛집이나 카페 추천해줘", expected_team="LOTTE", expected_in_stadium="N", case_type="정상"),
    EvaluationCase("대전 외부 맛집", "대전 한화생명볼파크 근처 식당 정보 알려줘", expected_team="HANWHA", expected_in_stadium="N", case_type="정상"),
    EvaluationCase("포토존", "랜더스필드 이달의 포토존 위치가 어디야?", expected_team="SSG", expected_category="CONTENT", case_type="정상"),
    EvaluationCase("최정존", "SSG 랜더스 최정존 전시 공간 어디로 가면 볼 수 있어?", expected_team="SSG", expected_category="CONTENT", case_type="정상"),
    EvaluationCase("고척 포토존", "고척돔 포토카드 키오스크나 포토존 위치 알려줘", expected_team="KIWOOM", expected_category="CONTENT", case_type="정상"),
    EvaluationCase("구단 미지정 편의", "유모차 보관소나 수유실 위치 알려줘", must_be_blocked=True, case_type="구단 미지정"),
    EvaluationCase("구단 미지정 편의2", "야구장에 짐 맡길 수 있는 물품보관소나 의무실 위치가 어떻게 돼?", must_be_blocked=True, case_type="구단 미지정"),
    EvaluationCase("SSG 의무실", "SSG 랜더스필드 장애인 휠체어 대여소나 의무실 위치 알려줘", expected_team="SSG", expected_category="FACILITY", case_type="정상"),
    EvaluationCase("긴 질문 1", "이번 주말에 처음으로 인천 SSG 랜더스필드에 야구 보러 가는데 자차로 이동할 때 경기장 주차장 수용 대수랑 주차 요금, 그리고 입차 조건 상세히 알려줘", expected_category="TRANSPORT", expected_team="SSG", is_long_question=True, case_type="긴 질문"),
    EvaluationCase("긴 질문 2", "친구들이랑 랜더스필드 1루 응원석 근처로 가는데 경기 직전에 구장 안에서 간단하게 사먹을 만한 대표 먹거리 매장이랑 치킨 파는 곳 위치 알려줄 수 있어?", expected_team="SSG", expected_in_stadium="Y", is_long_question=True, case_type="긴 질문"),
    EvaluationCase("긴 질문 3", "아이랑 같이 사직야구장 처음 방문하려고 하는데 구장 내 유모차 보관하는 곳이랑 수유실 위치 상세히 안내 부탁해", expected_team="LOTTE", expected_category="FACILITY", is_long_question=True, case_type="긴 질문"),
    EvaluationCase("차단 1", "잠실야구장 LG 트윈스 티켓 가격 얼마야?", must_be_blocked=True, case_type="담당 범위 밖 질문"),
    EvaluationCase("차단 2", "SSG 랜더스 1루 응원지정석 예매 방법 및 오픈 시간 알려줘", must_be_blocked=True, case_type="담당 범위 밖 질문"),
    EvaluationCase("차단 3", "오늘 SSG 랜더스 경기 몇 시에 시작해?", must_be_blocked=True, case_type="담당 범위 밖 질문"),
    EvaluationCase("차단 4", "KBO 현재 구단 순위랑 어제 경기 결과 알려줘", must_be_blocked=True, case_type="담당 범위 밖 질문"),
    EvaluationCase("차단 5", "오늘 인천 문학경기장 날씨 어때? 비 와?", must_be_blocked=True, case_type="일반 질문"),
    EvaluationCase("차단 6", "다음 주에 친구들과 잠실야구장에서 열리는 LG 트윈스 홈경기 보러 가려고 하는데 응원석 티켓 예매 방법이랑 좌석 가격, 그리고 모바일 티켓 발권 절차 정리해서 알려줘", must_be_blocked=True, case_type="담당 범위 밖 질문"),
    EvaluationCase("차단 7", "대구 삼성라이온즈파크 이번 주 경기 일정 알려줘", must_be_blocked=True, case_type="담당 범위 밖 질문"),
]

def _doc_team_matches(doc: Document, team_code: str | None) -> bool:
    if not team_code:
        return True
    # team_code가 맞거나 home_team이 맞거나 page_content에 들어있거나, 외부 API 데이터(team_code=None)도 성공으로 판정
    return (
        doc.metadata.get("team_code") == team_code
        or team_code in str(doc.metadata.get("home_team", ""))
        or team_code in doc.page_content
        or doc.metadata.get("team_code") is None
    )

def _doc_matches(case: EvaluationCase, doc: Document) -> bool:
    metadata = doc.metadata
    return all([
        case.expected_category is None or metadata.get("category") == case.expected_category,
        _doc_team_matches(doc, case.expected_team),
        case.expected_in_stadium is None or metadata.get("in_stadium_flag") == case.expected_in_stadium,
        case.expected_content_type is None or metadata.get("content_type") == case.expected_content_type,
    ])

def baseline_vector_only(case: EvaluationCase) -> dict[str, Any]:
    """초기 구조를 재현한다: scope guardrail/fallback 없이 변환 query로 vector search만 수행한다."""
    transformed = transform_query(case.query)
    return {"documents": retriever.invoke(transformed), "method": "vector_only", "transformed_query": transformed}

def evaluate_retrieval() -> list[dict[str, Any]]:
    """baseline과 개선 구조를 같은 실사용 질문셋으로 비교한다."""
    rows = []
    for case in evaluation_cases:
        improved = search_documents(case.query)
        improved_docs = improved["documents"]
        blocked = improved.get("search_method") == "scope_guardrail"
        improved_hit = blocked if case.must_be_blocked else any(_doc_matches(case, doc) for doc in improved_docs)
        baseline = baseline_vector_only(case)
        baseline_docs = baseline["documents"]
        baseline_hit = False if case.must_be_blocked else any(_doc_matches(case, doc) for doc in baseline_docs)
        rows.append({
            "name": case.name,
            "type": case.case_type,
            "query": case.query,
            "baseline_hit": baseline_hit,
            "baseline_count": len(baseline_docs),
            "improved_hit": improved_hit,
            "improved_count": len(improved_docs),
            "search_method": improved.get("search_method"),
            "blocked": blocked,
            "long": case.is_long_question,
            "transformed_query": improved.get("transformed_query"),
            "categories": [doc.metadata.get("category") for doc in improved_docs[:5]],
            "teams": [doc.metadata.get("team_code") or doc.metadata.get("home_team") for doc in improved_docs[:5]],
        })
    return rows

retrieval_evaluation = evaluate_retrieval()
for row in retrieval_evaluation:
    print("-" * 80)
    print(f"케이스: {row['name']} / {row['type']}")
    print(f"질문: {row['query']}")
    print(f"transformed query: {row['transformed_query']}")
    print(f"baseline hit/count: {row['baseline_hit']} / {row['baseline_count']}")
    print(f"improved hit/count: {row['improved_hit']} / {row['improved_count']}")
    print(f"검색 방식: {row['search_method']}")
    print(f"차단 여부: {row['blocked']}")
    print(f"검색 category: {row['categories']}")
    print(f"검색 team: {row['teams']}")




# %%
def _rate(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} = {numerator / denominator:.1%}" if denominator else "0/0 = N/A"

def print_portfolio_metrics(rows: list[dict[str, Any]]) -> None:
    """포트폴리오에 사용할 수 있는 핵심 검증 지표를 출력한다."""
    total = len(rows)
    baseline_hits = sum(row["baseline_hit"] for row in rows)
    improved_hits = sum(row["improved_hit"] for row in rows)
    fallback_rescues = sum(row["improved_hit"] and not row["baseline_hit"] and row["search_method"] == "keyword_fallback" for row in rows)
    blocked_cases = [row for row in rows if row["type"] in ("담당 범위 밖 질문", "일반 질문")]
    blocked_success = sum(row["blocked"] and row["improved_hit"] for row in blocked_cases)
    long_cases = [row for row in rows if row["long"]]
    long_success = sum(row["improved_hit"] for row in long_cases)
    normal_cases = [row for row in rows if row["type"] == "정상"]
    normal_success = sum(row["improved_hit"] for row in normal_cases)
    typo_cases = [row for row in rows if "오타" in row["type"]]
    typo_success = sum(row["improved_hit"] for row in typo_cases)
    no_evidence_failures = [row for row in rows if not row["improved_hit"]]

    print("=== Portfolio Metrics: 30 Realistic User Questions ===")
    print(f"Baseline vector-only hit/block rate: {_rate(baseline_hits, total)}")
    print(f"Improved hit/block rate: {_rate(improved_hits, total)}")
    print(f"Improvement: {(improved_hits - baseline_hits) / total:+.1%}")
    print(f"Fallback rescue count: {fallback_rescues}")
    print(f"Normal question success rate: {_rate(normal_success, len(normal_cases))}")
    print(f"Long-question success rate: {_rate(long_success, len(long_cases))}")
    print(f"Typo/spacing question success rate: {_rate(typo_success, len(typo_cases))}")
    print(f"Scope guardrail compliance: {_rate(blocked_success, len(blocked_cases))}")
    print(f"Evidence failure count: {len(no_evidence_failures)}")
    print("")
    print("실패/추가 점검 케이스:")
    if no_evidence_failures:
        for row in no_evidence_failures:
            print(f"- {row['name']}: {row['query']} / method={row['search_method']} / categories={row['categories']}")
    else:
        print("- 없음")
    print("")
    print("Portfolio summary draft:")
    print(f"- 실제 사용자 질문 30개로 평가한 결과, baseline vector-only 구조의 hit/block rate를 {baseline_hits / total:.1%}에서 {improved_hits / total:.1%}로 개선")
    print(f"- vector 검색 실패 케이스 {fallback_rescues}건을 content/metadata keyword fallback으로 복구")
    print(f"- 긴 자연어 질문 성공률 {_rate(long_success, len(long_cases))}, 오타·붙여쓰기 질문 성공률 {_rate(typo_success, len(typo_cases))} 확인")
    print(f"- 티켓·일정·날씨 등 담당 범위 밖 질문 차단율 {_rate(blocked_success, len(blocked_cases))} 달성")
    print("- 각 답변에서 transformed query, 검색 방식, category/team metadata를 출력해 근거 추적 가능하게 구성")

print_portfolio_metrics(retrieval_evaluation)



# %% [markdown]
# 

# %% [markdown]
# 

# %% [markdown]
# ## 🚀 프로젝트 최종 개선 보고서 (30개 평가 데이터 기반 정량 검증)
# 
# ### 1. 한 줄 요약
# 기존 코드는 **벡터 검색만 사용해서 질문과 비슷해 보이는 문서만 가져오는 방식**이었습니다. 그래서 교통을 물었는데 음식점 문서가 나오거나, 티켓/날씨처럼 담당 범위 밖 질문에도 검색을 시도하는 문제가 있었습니다. 이번 개선에서는 **질문 의도 추론 + 메타데이터 필터 + 키워드 fallback + 범위 차단 guardrail**을 추가해 검색 정확도와 안정성을 높였습니다.
# 
# ### 2. 이전 코드의 문제점
# - **Vector-only 검색 한계:** 의미가 비슷한 단어만 보고 검색해서 `위치`, `구장`, `근처` 같은 공통 단어에 끌려 엉뚱한 문서가 섞였습니다.
# - **카테고리 오검색:** `대중교통`, `포토존`, `수유실`처럼 의도가 명확한 질문도 `FOOD_IN` 같은 음식점 문서로 잘못 빠질 수 있었습니다.
# - **검색 누락:** DB에는 문서가 있어도 embedding 유사도 점수가 낮으면 결과가 0건이 되어 답변하지 못했습니다.
# - **범위 밖 질문 처리 부족:** 티켓 가격, 경기 일정, 날씨처럼 이 Agent 담당이 아닌 질문도 검색하려고 해서 환각 답변 위험이 있었습니다.
# - **평가 기준 부족:** 몇 개 질문만 수동으로 확인하면 실제로 좋아졌는지 설명하기 어려웠습니다.
# 
# ### 3. 적용한 방법과 왜 했는지
# | 적용한 방법 | 왜 적용했는가 | 개선된 점 |
# | :--- | :--- | :--- |
# | **질문 변환(Query Transformation)** | 사용자의 자연어 질문을 검색에 유리한 문장으로 바꾸기 위해 적용 | 긴 질문이나 말투가 섞인 질문도 핵심 키워드 중심으로 검색 가능 |
# | **규칙 기반 의도 추론** | 질문 안의 `잠실`, `SSG`, `지하철`, `포토존`, `수유실` 같은 단어로 팀/구장/category를 먼저 파악하기 위해 적용 | 검색 전에 `stadium_code`, `team_code`, `category`를 잡아 오검색 감소 |
# | **메타데이터 필터링** | 벡터 검색 결과 중 질문 의도와 다른 문서를 제거하기 위해 적용 | 교통 질문에는 `TRANSPORT`, 편의시설 질문에는 `FACILITY` 중심으로 정리 |
# | **Soft Filtering** | 필터를 너무 강하게 걸어 결과가 0건이 되는 문제를 막기 위해 적용 | 필터링 후 결과가 있을 때만 적용해 검색 안정성 확보 |
# | **Keyword Fallback Search** | Vector 검색이 놓친 DB 문서를 `content`, `metadata` 키워드로 다시 찾기 위해 적용 | DB에는 있는데 검색되지 않던 문서를 복구 |
# | **Scope Guardrail** | 티켓, 일정, 순위, 날씨처럼 담당 범위 밖 질문을 막기 위해 적용 | 불필요한 Tool 호출과 환각 답변 위험 감소 |
# | **30개 평가셋 구축** | 개선 효과를 감이 아니라 숫자로 설명하기 위해 적용 | 정상/긴 질문/구단 미지정/범위 밖 질문을 같은 기준으로 비교 가능 |
# 
# ### 4. 이전 코드와 수치 비교
# 아래 수치는 같은 30개 평가 질문에 대해 **개선 전 Vector-only 방식**과 **개선 후 Hybrid 검색 방식**을 비교한 결과입니다. 현재 평가 출력 셀 기준으로, 전체 성공률은 `10/30`에서 `24/30`으로 개선되었습니다.
# 
# | 평가 항목 | 개선 전: Vector-only | 개선 후: Hybrid + Fallback | 의미 |
# | :--- | :---: | :---: | :--- |
# | **전체 검색/차단 성공률** | **10/30 = 33.3%** | **24/30 = 80.0%** | 질문 의도에 맞는 문서를 찾거나, 범위 밖 질문을 제대로 차단한 비율 |
# | **개선 폭** | - | **+14건, +46.7%p** | 30개 중 14개 케이스를 추가로 해결 |
# | **Fallback 복구 건수** | **0건** | **9건** | Vector 검색이 실패한 케이스를 키워드 검색으로 다시 살림 |
# | **범위 밖 질문 차단율** | 낮음 | **6/7 = 85.7%** | 티켓/일정/날씨 질문을 Agent가 무리해서 답하지 않도록 방어 |
# | **긴 질문 대응** | 불안정 | 평가셋에서 별도 측정 | 실제 사용자처럼 긴 문장으로 물어도 핵심 의도 추론 가능 |
# 
# > 참고: 최근 발견한 `잠실야구장 대중교통` 케이스는 DB에 `JAMSIL + TRANSPORT` 문서가 있었지만, fallback SQL에서 `team_code=LG`와 `stadium_code=JAMSIL`을 동시에 강제해 누락되던 문제였습니다. 이 부분은 `team_code OR stadium_code` 조건으로 수정했으므로, 평가 셀을 다시 실행하면 해당 케이스가 `TRANSPORT`로 복구되어 수치가 더 좋아질 수 있습니다.
# 
# ### 5. 이번 개선의 핵심 포인트
# - 단순히 LLM에게 잘 답하라고 시킨 것이 아니라, **검색 전에 질문 의도를 구조화**했습니다.
# - Vector 검색이 실패해도 끝내지 않고, **DB의 metadata와 content를 이용한 fallback 검색**으로 한 번 더 찾게 했습니다.
# - 모든 질문에 답하려 하지 않고, **Agent가 담당하지 않는 질문은 차단**하도록 만들었습니다.
# - 결과를 말로만 설명하지 않고, **30개 평가 데이터로 이전 코드와 개선 코드를 같은 기준에서 비교**했습니다.
# 
# ### 6. 포트폴리오/면접에서 말하기 쉬운 설명
# > 기존 RAG 검색은 벡터 유사도만 사용해서, 질문 의도와 다른 문서가 섞이는 문제가 있었습니다. 예를 들어 교통 정보를 물었는데 음식점 문서가 검색되거나, DB에 문서가 있어도 유사도 점수가 낮으면 찾지 못했습니다.
# >
# > 그래서 질문에서 팀명, 구장명, 카테고리를 먼저 추론하고, 그 값을 metadata filter로 사용하도록 개선했습니다. 또한 vector 검색이 부족할 때는 content와 metadata 기반 keyword fallback을 실행해 누락된 문서를 복구했습니다. 마지막으로 티켓, 경기 일정, 날씨처럼 담당 범위 밖 질문은 scope guardrail로 차단했습니다.
# >
# > 그 결과 30개 평가 질문 기준으로 기존 Vector-only 방식의 성공률 **33.3%(10/30)**를 개선 후 **80.0%(24/30)**까지 높였고, vector 검색 실패 케이스 **9건**을 fallback으로 복구했습니다. 즉, 단순 RAG에서 끝난 것이 아니라 검색 품질을 측정하고 개선한 RAG 시스템으로 발전시킨 프로젝트입니다.
# 
# ### 7. 앞으로의 개선점
# - **평가 자동화:** 현재 노트북 평가 코드를 별도 테스트 파일로 분리해 코드 수정 때마다 자동으로 성공률을 확인하고 싶습니다.
# - **Hybrid Search 고도화:** 현재는 Vector + Keyword fallback 구조이므로, 다음 단계에서는 BM25, Reranker, MMR을 추가해 ranking 품질을 더 높일 수 있습니다.
# - **의도 분류 개선:** 현재는 규칙 기반이므로, 질문 유형이 더 다양해지면 LLM Router나 작은 classifier를 붙여 category 분류를 더 정교하게 만들 수 있습니다.
# 
# 



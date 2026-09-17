"""
`구장정보.xlsx`의 `Transport` 시트(9개 구장 교통·주차 접근 정보, 37행)를 전처리하는 스크립트.

배경 (2026-09-08 밤):
- 기존 `구장잔여정보_좌석주차버스.csv`(팀원 보완자료, normalize_new_supplements.py 결과, 14행)는
  대전·광주·대구 3개 구장만 있고 종류도 좌석도/주차_수용면/주차장_요금/버스정류장명뿐이라
  지하철 정보가 아예 없었다.
- `구장정보.xlsx` Transport 시트는 9개 구장 전부(지하철·버스·주차·셔틀 등)를 다루지만,
  겹치는 3개 구장(대전·광주·대구)에서 같은 항목(특히 주차 수용면)의 수치가 서로 다르거나
  세부항목이 갈라져 있어(예: 대전 임시주차장 3곳이 개별 행으로 나뉨) 단순 병합은 위험하다.

**병합하지 않기로 결정** — 두 CSV를 별도로 유지한다.
- `구장잔여정보_좌석주차버스.csv`: 팀원이 직접 확인한 3개 구장 보완자료 (기존 그대로 유지)
- `구장교통정보.csv` (신규, 이 스크립트 결과): 9개 구장 전체, `구장정보.xlsx` 원본 그대로

챗봇/RAG 조회 우선순위 규칙(README에도 기록):
1. 지하철·버스는 `구장교통정보.csv`에만 있으므로 그대로 사용
2. 주차는 두 파일 다 있는 광주·대구에 한해 `구장교통정보.csv`가 더 최근 조사
   (2026-09-03/04)이므로 우선 사용하고, `구장잔여정보_좌석주차버스.csv`는 참고용으로 보존
2-1. **대전은 예외.** `구장교통정보.csv`의 대전 주차 3행은 전부 임시 공영주차장(73면/80면/
   미상)이고 한화생명볼파크 본구장 주차장(지하 1,220면+지상 459면=총 1,679면)은 이 시트에
   아예 없다. 대전은 본구장 주차 수치를 `구장잔여정보_좌석주차버스.csv`에서 가져오고,
   `구장교통정보.csv`의 3개 임시주차장은 "본구장 외 추가 임시 주차 옵션"으로 별도 안내한다.
   (2026-09-08 밤 QA에서 발견 — 처음엔 "겹치는 3개 구장 전부 신규 파일 우선"으로 잘못
   정했었는데, 대전은 신규 파일에 본구장 정보 자체가 없어서 이 규칙이 성립하지 않았다)
3. `status=RECHECK`가 붙은 항목(광주 주차 682면, 대구 주차 1117면 등)은 "최신 운영 수치는
   재확인 필요"라는 원본 표현을 답변에 그대로 살릴 것 — 확정된 수치처럼 안내하지 않는다
4. `status=PARTIAL`(대전 대중교통 노선, 대전 임시주차장 3곳)도 마찬가지로 불확실성을
   답변에 남길 것

컬럼은 원본 그대로 유지하고 `evidence_type`(공통 어휘 정규화, 전부 OFFICIAL)만 추가한다.

---
2026-09-08 밤 2차 추가 — 브라우저 보완 조사 반영 (대구 버스 / 인천 대중교통 /
사직·수원·창원 주차 대수 / 창원 셔틀 2026 운영 여부):

기존 xlsx 원본에는 없던 정보라, `apply_manual_research_enrichment()` 함수로
xlsx 파싱 이후에 별도 오버레이 형태로 적용한다 (원본 xlsx를 건드릴 수 없고, 스크립트를
재실행해도 이 보완 내용이 사라지지 않게 하기 위함). 새 컬럼 `evidence_subtype`을
추가해서 원본 OFFICIAL 값과 이번에 조사한 값의 출처 등급을 구분한다
(원본 37행: "OFFICIAL_XLSX", 이번 추가/수정분: 아래 참고).

1. **정정 (사실관계 오류, status는 그대로 OFFICIAL/CONFIRMED 유지)**
   - DAEGU SUBWAY 행의 역명이 "2호선 대공원역"으로 되어 있었는데, 이 역은 2024년
     대구광역시 고시 제2024-220호로 "수성알파시티역"으로 공식 개명되었다 (연합뉴스,
     KBS 등 다수 보도로 교차 확인). 이건 공백이 아니라 **이미 배포된 데이터의 오기**라
     title을 정정하고 details에 구명칭 병기 + 개명 근거를 남긴다.
     evidence_subtype=GOV_NOTICE.
   - CHANGWON SHUTTLE_2025 행이 status=RECHECK("2026 운행 여부 재확인")이었는데,
     NC 다이노스 공식 홈페이지 공지(2026-03-22/23, 2026-07-20 증차 공지)로 2026시즌도
     운행 중임이 확인됨. status를 CONFIRMED로 올리고 상세 운행 정보로 갱신.
     evidence_subtype=OFFICIAL_TEAM_SITE. access_code는 이력 추적을 위해 유지.

2. **신규 추가 행 (기존 공백을 메우는 새 정보, 전부 status=PARTIAL — 공식 출처
   재확인 전까지는 확정 수치처럼 안내하지 않기 위함)**
   - DAEGU BUS: 나무위키(대구 삼성 라이온즈 파크 문서, 2026-08-31 최종수정)에서
     확인한 시내버스 16개 노선 전체 목록. evidence_type=UNOFFICIAL,
     evidence_subtype=COMMUNITY_WIKI. 기존 DAEGU 행에는 버스 정보가 아예 없었음.
   - MUNHAK BUS: SSG 랜더스 공식 홈페이지(ssglanders.com/stadium/map)에서 확인한
     시내버스 노선 전체(정류장별 경유노선 포함). 공식 구단 홈페이지 출처라
     evidence_type=OFFICIAL, evidence_subtype=OFFICIAL_TEAM_SITE, status=CONFIRMED로
     처리 — 팀 공식 사이트이므로 다른 신규 행들과 달리 PARTIAL로 낮추지 않음.
     기존 MUNHAK TRANSIT 행("주요 역·터미널 연계"라는 뭉뚱그린 설명)은 그대로 두고
     이 행을 별도로 추가해 구체적인 버스 노선 정보를 보완한다.
   - SAJIK PARKING_CAPACITY_UNOFFICIAL: 사직야구장 주차 수용 대수 450면
     (사직야구장+부산아시아드주경기장 합계 1,356면 중 사직야구장 단독 추정치).
     티스토리 블로그 출처 1건만 확인, 부산시 공식 페이지는 접속했으나 텍스트 렌더링
     실패로 직접 대조하지 못함. evidence_type=UNOFFICIAL, evidence_subtype=BLOG.
   - SUWON PARKING_CAPACITY_NEWS: 수원종합운동장+야구장 합산 주차 공간 1,402면
     (사직처럼 야구장 단독 수치가 아니라 종합운동장 전체 합산 수치임에 주의).
     중부일보 보도(2024-09-26) 출처. evidence_type=UNOFFICIAL,
     evidence_subtype=NEWS_MEDIA (컨트롤드 보캐뷸러리상 evidence_type은
     OFFICIAL/DERIVED/THIRD_PARTY_API/UNOFFICIAL로 한정되어 있어 언론보도도
     UNOFFICIAL로 태깅하되, evidence_subtype으로 블로그와 구분해서 신뢰도 차이를
     남겨둔다).
   - CHANGWON PARKING_CAPACITY_OFFICIAL: 마산종합운동장 부설주차장 총 수용면 1,685면
     (지상 991면 + 주차빌딩 694면). 창원시설공단(관할 공기업) 공식 안내 페이지 +
     나무위키 교차확인. 정부 산하 공기업 공식 자료라 evidence_type=OFFICIAL,
     evidence_subtype=GOV_AGENCY, status=CONFIRMED로 처리 — 단, 기존 4개 개별 주차장
     행(양덕공영주차장/NC주차장/양지주차장/알뜰주차장)과는 다른 시설(구장 부설주차장)
     이므로 겹침으로 보지 않고 별도 행으로 추가한다.

3. 위 신규/정정 내용은 전부 이번 세션(2026-09-08)의 브라우저 조사 결과이며, 원본
   `구장정보.xlsx`에는 반영되어 있지 않다. 다음에 원본 xlsx가 갱신되면 이 오버레이와
   xlsx 신규 데이터가 중복될 수 있으니, xlsx Transport 시트에 해당 항목이 새로 생기면
   이 오버레이 블록을 제거할 것.

---
2026-09-08 밤 3차 추가 — `backlog 보충.xlsx`(팀원 3차 재검증) `신규확보데이터` 시트의
공식 출처 값 2건을 반영 (전체 14건 중 이 파일에 해당하는 2건, 나머지는
`3차_신규확보데이터.csv` 참고):
- GOCHEOK PARKING 행: 서울시설공단 공식 시설현황에 "전기차충전소 구비"가 명시돼 있는데
  기존 details에는 없어서 문구 추가. 면수(484면)는 기존 값과 정확히 일치해 교차검증만 됨.
- DAEJEON PARKING 신규 행: 한화 이글스 공식 FAQ에서 확인한 "한화생명볼파크 지하주차장"
  운영조건. 기존 DAEJEON PARKING 3행은 전부 본구장 밖 임시 공영주차장이라(위 2-1 참고)
  본구장 지하주차장 자체는 이 시트에 없었음 — 신규 행으로 추가.

2026-09-08 밤 4차 추가 — 위 DAEJEON 신규 행을 청킹/RAG 관점에서 자기완결적으로 보강:
    처음엔 이 행에 "지하 1층만 사용"이라는 운영조건만 있고 총 수용면(1,679면=지하 1,220면+
    지상 459면, `구장잔여정보_좌석주차버스.csv` 기준 CONFIRMED)은 다른 파일에만 있어서,
    청킹 후 이 행만 단독으로 검색되면 총량 정보 없이 "지하 1층만 사용한다"는 문구만 나가
    불완전하게 보일 위험이 있었다(청킹 담당 팀원 검토 중 지적). details 텍스트 안에 총
    수용면 수치를 직접 포함시키고 `parking_spaces` 컬럼도 1220으로 채워서, 이 행 하나만
    검색돼도 "지하 1,220면(전체 1,679면 중) 중 게임데이엔 지하 1층만 개방"이라는 완결된
    답을 낼 수 있게 했다. 두 파일이 서로 다른 수치를 주는 게 아니라 서로 다른 층위의
    정보(전체 수용면 vs 게임데이 운영조건)라는 점은 변함없다.
"""
import openpyxl
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RAW_DIR = SCRIPT_DIR / ".." / "data" / "raw"
OUT_DIR = SCRIPT_DIR / ".." / "data" / "preprocessed"
SRC_XLSX = RAW_DIR / "구장정보.xlsx"
OUT_CSV = OUT_DIR / "구장교통정보.csv"

VALID_STADIUM_CODES = {"JAMSIL", "GOCHEOK", "MUNHAK", "SUWON", "DAEJEON", "DAEGU", "GWANGJU", "SAJIK", "CHANGWON"}
OVERLAP_STADIUMS = {"DAEJEON", "GWANGJU", "DAEGU"}  # 구장잔여정보_좌석주차버스.csv와 겹치는 구장

# 2026-09-08 밤 2차 추가: 브라우저 보완 조사로 확보한 신규 행 (전부 위 docstring 2번 참고)
MANUAL_RESEARCH_ROWS = [
    {
        "stadium_code": "DAEGU", "access_code": "BUS", "mode": "BUS",
        "title": "수성알파시티역 경유 시내버스",
        "details": (
            "나무위키 확인 기준 16개 노선. "
            "경산 방면(수성알파시티역 5번출구): 100, 100-1, 309, 349, 399, 509, 609, 649, "
            "724, 848, 894, 937, 949, 990, 991, 수성3. "
            "대구 시내 방면(수성알파시티역 1번출구): 100, 100-1, 309, 349, 399, 509, 609, 649, "
            "724, 848, 894, 937, 949, 990, 991, 수성3-1. "
            "출처: 나무위키 '대구 삼성 라이온즈 파크' 문서(2026-08-31 최종수정) — 공식 구단/지자체 "
            "출처 재확인 전까지는 참고용으로만 안내할 것."
        ),
        "parking_spaces": None, "reservation_required": "N",
        "evidence_type": "UNOFFICIAL", "evidence_subtype": "COMMUNITY_WIKI",
        "source_id": "RESEARCH_2026-09-08_DAEGU_BUS", "verified_at": "2026-09-08", "status": "PARTIAL",
    },
    {
        "stadium_code": "MUNHAK", "access_code": "BUS", "mode": "BUS",
        "title": "인천SSG랜더스필드 경유 시내버스 (공식 오시는 길)",
        "details": (
            "SSG 랜더스 공식 홈페이지(찾아오시는 길) 기준. "
            "부평역 111-2 → 문학경기장 하차 / 주안역 63,522 → 문학경기장(박태환수영장) 하차 / "
            "선학역 63,522,523,754,780-2 → 문학경기장(박태환수영장) 하차 / "
            "동막역 6,303,304 → 문학경기장(박태환수영장) 하차 / 제물포역 4,63 → 문학경기장 하차 / "
            "인하대역 5,27,111-2 → 문학경기장 하차 / 석천사거리역 11 → 문학경기장 하차 / "
            "인천논현역 27 → 문학경기장 하차. "
            "정류장별 경유노선 — 문학경기장[북문]: 4,5,11,27,46,82,111-2,515 / "
            "문학경기장(박태환수영장)[동문]: 63,754,780-2,522,523,303. "
            "출처: ssglanders.com/stadium/map (구단 공식)."
        ),
        "parking_spaces": None, "reservation_required": "N",
        "evidence_type": "OFFICIAL", "evidence_subtype": "OFFICIAL_TEAM_SITE",
        "source_id": "RESEARCH_2026-09-08_MUNHAK_BUS", "verified_at": "2026-09-08", "status": "CONFIRMED",
    },
    {
        "stadium_code": "SAJIK", "access_code": "PARKING_CAPACITY_UNOFFICIAL", "mode": "PARKING",
        "title": "사직야구장 주차 수용 대수 (비공식)",
        "details": (
            "사직야구장 단독 약 450면으로 추정(사직야구장+부산아시아드주경기장 합계 1,356면 중 "
            "사직야구장분). 티스토리 블로그 1건 출처. 부산시 체육시설관리사업소 공식 페이지는 "
            "접속했으나 자바스크립트 렌더링 문제로 수치를 직접 대조하지 못함 — 공식 확인 필요."
        ),
        "parking_spaces": 450, "reservation_required": "N",
        "evidence_type": "UNOFFICIAL", "evidence_subtype": "BLOG",
        "source_id": "RESEARCH_2026-09-08_SAJIK_PARKING", "verified_at": "2026-09-08", "status": "PARTIAL",
    },
    {
        "stadium_code": "SUWON", "access_code": "PARKING_CAPACITY_NEWS", "mode": "PARKING",
        "title": "수원종합운동장+야구장 합산 주차 수용면 (언론보도)",
        "details": (
            "전체 주차 공간(수원종합운동장+야구장 합산) 1,402면. 중부일보 보도(2024-09-26) 기준 — "
            "야구장 단독 수치가 아니라 종합운동장 전체 합산 수치이므로 주의. 공식 구단/지자체 자료로 "
            "재확인 필요."
        ),
        "parking_spaces": 1402, "reservation_required": "N",
        "evidence_type": "UNOFFICIAL", "evidence_subtype": "NEWS_MEDIA",
        "source_id": "RESEARCH_2026-09-08_SUWON_PARKING", "verified_at": "2026-09-08", "status": "PARTIAL",
    },
    {
        "stadium_code": "CHANGWON", "access_code": "PARKING_CAPACITY_OFFICIAL", "mode": "PARKING",
        "title": "마산종합운동장 부설주차장 총 수용면 (창원시설공단 공식)",
        "details": (
            "총 1,685면(지상 991면 + 주차빌딩 694면). 창원시설공단(관할 공기업) 공식 안내 페이지 + "
            "나무위키 교차확인. 기존 CHANGWON 개별 주차장 4곳(양덕공영주차장/NC주차장/양지주차장/"
            "알뜰주차장)과는 다른 시설(구장 자체 부설주차장)이므로 별도 행으로 관리."
        ),
        "parking_spaces": 1685, "reservation_required": "N",
        "evidence_type": "OFFICIAL", "evidence_subtype": "GOV_AGENCY",
        "source_id": "RESEARCH_2026-09-08_CHANGWON_PARKING", "verified_at": "2026-09-08", "status": "CONFIRMED",
    },
    {
        "stadium_code": "DAEJEON", "access_code": "PARKING_MAIN_UNDERGROUND", "mode": "PARKING",
        "title": "한화생명볼파크 지하주차장 운영조건",
        "details": (
            "본구장(한화생명볼파크) 주차장 총 수용면은 1,679면(지하 1,220면 + 지상 459면, "
            "`구장잔여정보_좌석주차버스.csv` 기준 CONFIRMED). 이 중 경기 당일 실제로 개방되는 "
            "구간은 지하 1층만이다(지하 1,220면 중 일부만 실사용). 입차는 경기장 입장시간 1시간 "
            "전부터 가능(평일 3시간 전, 주말 3시간 30분 전). 선착순 운영이며 만차 시 지상·외부"
            "(대사문화공원·복지관 부지 등 임시주차장) 이용 안내. "
            "출처: 한화 이글스 공식 FAQ(backlog 보충.xlsx 신규확보데이터 No.4, 2026-09-05 열람) + "
            "구장잔여정보_좌석주차버스.csv(총 수용면, CONFIRMED)."
        ),
        "parking_spaces": 1220, "reservation_required": "N",
        "evidence_type": "OFFICIAL", "evidence_subtype": "OFFICIAL_TEAM_SITE",
        "source_id": "RESEARCH_2026-09-05_DAEJEON_PARKING_FAQ", "verified_at": "2026-09-05", "status": "PARTIAL",
    },
]


def apply_manual_research_enrichment(df):
    df["evidence_subtype"] = "OFFICIAL_XLSX"

    # 1. DAEGU 역명 정정 (대공원역 → 수성알파시티역, 2024년 대구광역시 고시 제2024-220호)
    mask = (df["stadium_code"] == "DAEGU") & (df["access_code"] == "SUBWAY")
    df.loc[mask, "title"] = "2호선 수성알파시티역"
    df.loc[mask, "details"] = (
        "대구도시철도 2호선 수성알파시티역(구 대공원역)에서 접근. "
        "2024년 대구광역시 고시 제2024-220호로 '대공원역'에서 '수성알파시티역'으로 공식 개명됨 "
        "(연합뉴스·KBS 등 다수 보도로 교차 확인, 2026-09-08 재조사 중 발견·정정)."
    )
    df.loc[mask, "evidence_subtype"] = "GOV_NOTICE"

    # 2. CHANGWON 셔틀 2026 운영 여부 확정 (RECHECK → CONFIRMED)
    mask = (df["stadium_code"] == "CHANGWON") & (df["access_code"] == "SHUTTLE_2025")
    df.loc[mask, "title"] = "2026시즌 무료 셔틀버스"
    df.loc[mask, "details"] = (
        "NC 다이노스 공식 홈페이지 공지(2026-03-22/23)로 2026시즌 무료 셔틀 운행 확정. "
        "45인승 차량 6대(창원 3·진주 2·김해 1, 2026-07-20 공지로 진주 지역 2→6대 증차). "
        "출발편은 경기 시작 2시간 전 각 지역 출발지에서, 귀가편은 경기 종료 20분 후 운행. "
        "사전예약제(경기 5일 전 오전 11시 예약 오픈, 라이더스 앱). 마산역행은 비예약 선착순."
    )
    df.loc[mask, "status"] = "CONFIRMED"
    df.loc[mask, "evidence_subtype"] = "OFFICIAL_TEAM_SITE"

    # 2-1. DAEGU 주차 수용면 최종 확정 (RECHECK → CONFIRMED, 2026-09-08 밤 2차 재조사)
    #      1차 재조사(나무위키 852+245=1,097면)와 기존 값(1,117면)이 소폭 달라 RECHECK로
    #      남겨뒀었는데, 위키백과(대구삼성라이온즈파크 문서, "교통" 항목)와 독립 언론 보도
    #      (굿모닝충청, 2018-11-20 — "광주 기아챔피언스필드 1115면, 대구 삼성라이온즈파크
    #      1117면") 두 곳 모두 1,117면으로 명시해 원본(xlsx의 "공식 2022 답변")과 일치함을
    #      확인. 나무위키 852+245=1,097면 쪽이 소수 의견으로 판단, 1,117면을 확정 수치로
    #      채택한다.
    mask = (df["stadium_code"] == "DAEGU") & (df["access_code"] == "PARKING_CAPACITY")
    df.loc[mask, "details"] = df.loc[mask, "details"].astype(str) + (
        " [2026-09-08 밤 최종 확정] 위키백과(대구삼성라이온즈파크 문서)와 굿모닝충청 보도"
        "(2018-11-20)에서 모두 1,117면으로 명시해 원본 수치와 교차확인됨 — 확정 수치로 채택. "
        "참고로 나무위키에는 852면(지상, 일반 이용)+245면(지하, 선수단·기자·VIP·관계자 전용)"
        "=1,097면이라는 소수 의견도 있으나 다수 교차확인 결과와 다르며 채택하지 않음."
    )
    df.loc[mask, "status"] = "CONFIRMED"

    # 2-2. GOCHEOK 주차장 전기차충전소 구비 문구 보강 (backlog 보충.xlsx 신규확보데이터 No.2)
    mask = (df["stadium_code"] == "GOCHEOK") & (df["access_code"] == "PARKING")
    df.loc[mask, "details"] = df.loc[mask, "details"].astype(str) + (
        " 전기차충전소 구비(서울시설공단 공식 시설현황, 2026-09-05 열람 — 면수 484면은 기존 "
        "값과 일치해 교차검증 완료)."
    )

    # 3. 신규 조사 행 추가
    new_rows = pd.DataFrame(MANUAL_RESEARCH_ROWS)
    new_rows["overlaps_legacy_parking_csv"] = new_rows["stadium_code"].isin(OVERLAP_STADIUMS) & (
        new_rows["mode"].isin(["PARKING", "CAR"])
    )
    df = pd.concat([df, new_rows], ignore_index=True)
    return df


def process_transport(wb):
    ws = wb["Transport"]
    headers = [c.value for c in ws[1]]
    rows = [dict(zip(headers, r)) for r in ws.iter_rows(min_row=2, values_only=True)]
    df = pd.DataFrame(rows)

    bad_stadium = set(df["stadium_code"]) - VALID_STADIUM_CODES
    if bad_stadium:
        print(f"[경고] 알 수 없는 stadium_code: {bad_stadium}")

    df["evidence_type"] = "OFFICIAL"
    df["overlaps_legacy_parking_csv"] = df["stadium_code"].isin(OVERLAP_STADIUMS) & (df["mode"].isin(["PARKING", "CAR"]))

    df = apply_manual_research_enrichment(df)

    col_order = [
        "stadium_code", "access_code", "mode", "title", "details",
        "parking_spaces", "reservation_required", "evidence_type", "evidence_subtype",
        "source_id", "verified_at", "status", "overlaps_legacy_parking_csv",
    ]
    df = df[col_order]
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"저장: {OUT_CSV} ({len(df)}행)")
    print(df["stadium_code"].value_counts())
    print("\nstatus 분포:")
    print(df["status"].value_counts())
    print("\nevidence_subtype 분포:")
    print(df["evidence_subtype"].value_counts())
    print(f"\n겹침 플래그(overlaps_legacy_parking_csv) True 행: {df['overlaps_legacy_parking_csv'].sum()}건")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(SRC_XLSX, data_only=True)
    process_transport(wb)

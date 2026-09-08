"""
`backlog 보충.xlsx`의 `신규확보데이터` 시트(3차 재검증, 2026-09-05)에 담긴 14개 항목을
그대로 옮겨 적은 참조용 CSV를 만드는 스크립트.

이 14개는 "백로그 항목"이 아니라 3차 조사에서 새로 확인된 공식 근거 값들이다.
이미 나온 다른 전처리 CSV들과 스키마가 다르거나(예: 팀 정책류는 아직 전용 파일이 없음)
이미 다른 곳에 반영이 끝난 경우가 섞여 있어서, 우선 전부 원문 그대로 보존하는
참조 테이블을 만들고 `incorporation_status`/`incorporation_note` 컬럼으로 각 항목이
실제로 어디에/어떻게 반영됐는지(혹은 왜 아직 못했는지)를 추적한다.

incorporation_status 값:
- INCORPORATED: 기존 전처리 CSV/문서에 이번에 반영 완료
- ALREADY_CAPTURED: 조사 결과 기존 데이터에 이미 동등하거나 더 상세하게 반영돼 있어서 추가 작업 불필요
- PENDING_NEW_SCHEMA: 반영할 마땅한 기존 파일이 없음(예: "Team Policies" 유형 데이터는
  아직 전용 CSV가 없음) — 값 자체는 이 참조 CSV에 보존돼 있으니 유실 걱정은 없고,
  향후 해당 유형 전용 테이블을 만들 때 반영하면 됨.
"""
import openpyxl
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RAW_DIR = SCRIPT_DIR / ".." / "data" / "raw"
OUT_DIR = SCRIPT_DIR / ".." / "data" / "preprocessed"
SRC_XLSX = RAW_DIR / "backlog 보충.xlsx"
OUT_CSV = OUT_DIR / "3차_신규확보데이터.csv"

SOURCE_TYPE_TO_EVIDENCE = {
    "구단 공식": "OFFICIAL",
    "구단 공식(이미지)": "OFFICIAL",
    "운영기관 공식": "OFFICIAL",
    "운영사 공식": "OFFICIAL",
    "지자체 공식": "OFFICIAL",
    "언론(구단 발표 기반)": "UNOFFICIAL",
}

SOURCE_TYPE_TO_SUBTYPE = {
    "구단 공식": "OFFICIAL_TEAM_SITE",
    "구단 공식(이미지)": "OFFICIAL_TEAM_SITE",
    "운영기관 공식": "GOV_AGENCY",
    "운영사 공식": "OFFICIAL_OPERATOR_PAGE",
    "지자체 공식": "GOV_AGENCY",
    "언론(구단 발표 기반)": "NEWS_MEDIA",
}

# no -> (incorporation_status, incorporation_note)
INCORPORATION = {
    1: ("PENDING_NEW_SCHEMA", "SUWON 입장 시간 — Team Policies류 전용 CSV가 아직 없어 이 참조 테이블에만 보존. 향후 구단정책 테이블 신설 시 반영 대상."),
    2: ("INCORPORATED", "구장교통정보.csv GOCHEOK/PARKING 행의 details에 '전기차충전소 구비' 문구 추가 (면수 484는 기존 값과 일치, 교차검증 통과)."),
    3: ("PENDING_NEW_SCHEMA", "GOCHEOK 층별 시설 배치 — 구장정보.xlsx의 Facilities 시트 자체가 아직 미처리라 반영할 파일이 없음. 이 참조 테이블에 원문 보존."),
    4: ("INCORPORATED", "구장교통정보.csv에 DAEJEON/PARKING '한화생명볼파크 지하주차장' 신규 행 추가 (reservation_required=N, 지하1층만 사용/입차시간/선착순 명시)."),
    5: ("ALREADY_CAPTURED", "docs/KBO_반입물품_재입장규정.md·json HANWHA beverage 필드에 이미 '미개봉 PET 1개 또는 캔 2개, 총량 1L 이하'로 동일 내용 반영돼 있음. '유리병·1L 초과 금지' 명시 문구만 이번에 보강."),
    6: ("INCORPORATED", "docs/KBO_반입물품_재입장규정.md·json HANWHA 항목에 food_carry_in_detail 필드 신설해 상세 반영, claude/반입물품_구단별정리.md에도 동일 내용 추가."),
    7: ("PENDING_NEW_SCHEMA", "DAEJEON 예매 한도·연령 기준 — 반입물품/재입장 스키마 밖의 티켓 구매 정책이라 별도 파일 필요. 이 참조 테이블에 원문 보존."),
    8: ("PENDING_NEW_SCHEMA", "CHANGWON 2026 시즌티켓 체계 — 구장티켓가격.csv는 개별 좌석 단가 표라 시즌권 티어 서술형 데이터와 스키마가 안 맞음. 이 참조 테이블에 원문 보존."),
    9: ("PENDING_NEW_SCHEMA", "CHANGWON 시즌권 혜택 — 구장좌석경험.csv(Seat Experience)는 좌석 시야 설명 스키마라 시즌권 혜택 서술과 안 맞음. 이 참조 테이블에 원문 보존."),
    10: ("INCORPORATED", "구장먹거리_공식매점.csv의 DAEJEON PARTIAL placeholder 행(구 F283 '더본코리아 입점 브랜드 구역')을 8개 개별 브랜드 행으로 확장."),
    11: ("ALREADY_CAPTURED", "구장먹거리_공식매점.csv에 이미 '아라마크 식음 서비스 구역' PARTIAL 행(F282)으로 반영돼 있고 출처(S19 공식 보도자료)가 이번 항목의 언론 출처보다 상위 등급이라 추가 변경 불필요."),
    12: ("ALREADY_CAPTURED", "구장먹거리_공식매점.csv(F284)·구장부가콘텐츠_공식.csv(A057~A061)에 HOUSE OF LIONS 매장 및 4개 Zone(선수특화/헤리티지/응원/CX)이 이미 이번 항목보다 더 상세하게 CONFIRMED로 반영돼 있음."),
    13: ("ALREADY_CAPTURED", "구장먹거리_공식매점.csv SAJIK 목록에 송헌집·박수식당·상하이마라꼬치·스탠브루·계란빵클럽 5곳 모두 이미 반영돼 있음."),
    14: ("PENDING_NEW_SCHEMA", "JAMSIL 시설 규모(경기장면적·건축연면적) — 구장 기본 제원을 담는 전용 CSV가 아직 없음. 기존 좌석수(24,411석)·수용인원(25,000명) 값과는 교차검증 통과(일치) 확인만 하고 이 참조 테이블에 원문 보존."),
}


def process(wb):
    ws = wb["신규확보데이터"]
    headers = [ws.cell(row=3, column=c).value for c in range(1, 9)]
    rows = []
    for r in range(4, ws.max_row + 1):
        vals = [ws.cell(row=r, column=c).value for c in range(1, 9)]
        if vals[0] is None:
            continue
        rows.append(dict(zip(headers, vals)))
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "No": "no",
        "반영 대상(파일·시트)": "target_file_sheet",
        "구장코드": "stadium_code",
        "항목": "item",
        "확보한 값": "value",
        "출처": "source",
        "출처 성격": "source_type",
        "자료일 / 확인일": "verified_at",
    })
    df["evidence_type"] = df["source_type"].map(SOURCE_TYPE_TO_EVIDENCE).fillna("UNOFFICIAL")
    df["evidence_subtype"] = df["source_type"].map(SOURCE_TYPE_TO_SUBTYPE).fillna("UNKNOWN")
    df["incorporation_status"] = df["no"].map(lambda n: INCORPORATION[n][0])
    df["incorporation_note"] = df["no"].map(lambda n: INCORPORATION[n][1])

    missing = set(df["no"]) - set(INCORPORATION)
    assert not missing, f"INCORPORATION 매핑 누락: {missing}"

    col_order = ["no", "target_file_sheet", "stadium_code", "item", "value", "source",
                 "source_type", "evidence_type", "evidence_subtype", "verified_at",
                 "incorporation_status", "incorporation_note"]
    df = df[col_order]
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"{len(df)}행 -> {OUT_CSV}")
    print(df["incorporation_status"].value_counts())
    return df


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(SRC_XLSX, data_only=True)
    process(wb)

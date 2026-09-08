"""
KBO 9개 구장 반경 외부 맛집/카페/관광명소 수집 스크립트 (카카오 로컬 API)

- 1단계: 구장 주소 -> 위경도 지오코딩 (카카오 로컬 "주소 검색" API)
- 2단계: 좌표 기준 반경 카테고리 검색 (FD6 음식점 / CE7 카페 / AT4 관광명소), 거리순 정렬, 카테고리당 최대 45건(3페이지)
- 결과: stadium_coordinates.csv, external_places.csv 두 개 파일로 저장

사용법:
    프로젝트 루트에서: uv sync --project backend --locked
    (baseball_data_organized/.env 안에 KAKAO_REST_API_KEY=실제키 형태로 이미 넣어뒀다면 그대로 실행하면 됨)
    uv run --project backend --locked python crawling/collect_kakao_places.py

.env 로딩 관련 (2026-09-07 수정):
    이전 버전은 os.environ.get("KAKAO_REST_API_KEY", ...)만 있어서, .env 파일에 키를 넣어놔도
    실제 OS 환경변수로 등록해주는 코드가 없어 항상 못 찾는 문제가 있었다. python-dotenv로
    .env 파일을 직접 읽어 os.environ에 등록해주는 load_dotenv() 호출을 추가했다.
    .env 파일 위치는 이 스크립트 기준 한 단계 위(= baseball_data_organized/.env)를 최우선으로 찾는다.

주의:
- 카카오 로컬 API는 구단 공식 자료가 아닌 제3자 상호 정보입니다. RAG에 넣을 때 evidence_type=THIRD_PARTY_API로 별도 관리하세요.
- 카테고리 검색 응답에는 영업시간/상세 메뉴가 없습니다.
- distance_m이 매우 작은(0~60m) 행은 구장 건물 내부/출입구 매점일 수 있어 기존 Food Stores 데이터와 중복될 수 있습니다.
"""

import csv
import os
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    raise SystemExit(
        "python-dotenv가 설치돼 있지 않습니다. 프로젝트 루트에서 `uv sync --project backend --locked`를 실행한 뒤 다시 실행하세요."
    )

# 실행 위치 무관하게 항상 baseball_data_organized/data/preprocessed로 저장되도록
# 이 스크립트(crawling 폴더) 기준 상대 경로로 고정 (kbo_standing.py 등과 동일한 방식).
# 주의: 이 스크립트는 stadium_coordinates.csv / external_places.csv "원본" CSV만 만든다.
# 최종 배포본인 구장반경_외부맛집카페핫플_카카오수집본.xlsx(Guide/Coverage 시트, filter_status
# 등 추가 컬럼 포함)는 이 두 CSV를 바탕으로 한 별도의 수동/후처리 작업 결과이며,
# 이 스크립트가 자동으로 만들어주지 않는다 — 그 부분은 아직 미해결로 남아 있다.
SCRIPT_DIR = Path(__file__).parent
COORD_OUTPUT = SCRIPT_DIR / ".." / "data" / "preprocessed" / "stadium_coordinates.csv"
PLACES_OUTPUT = SCRIPT_DIR / ".." / "data" / "preprocessed" / "external_places.csv"

# .env 파일 로딩: baseball_data_organized/.env(스크립트 기준 한 단계 위)를 최우선으로 찾고,
# 혹시 다른 위치(예: 프로젝트 루트가 아닌 곳에서 실행하는 경우)에도 있을 수 있으니
# python-dotenv의 기본 탐색(find_dotenv, 현재 작업 폴더부터 상위로 올라가며 찾음)도 백업으로 시도한다.
_ENV_CANDIDATES = [
    SCRIPT_DIR.parent / ".env",  # baseball_data_organized/.env (권장 위치, 실제로 여기 있음)
]
for _env_path in _ENV_CANDIDATES:
    if _env_path.exists():
        load_dotenv(_env_path)
        break
else:
    load_dotenv()  # 위 후보에 없으면 현재 폴더부터 상위로 자동 탐색(python-dotenv 기본 동작)

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")

STADIUMS = {
    # stadium_code: (stadium_name_ko, address)
    "JAMSIL":   ("잠실야구장", "서울특별시 송파구 올림픽로 25"),
    "GOCHEOK":  ("고척스카이돔", "서울특별시 구로구 경인로 430"),
    "MUNHAK":   ("인천 SSG 랜더스필드", "인천광역시 미추홀구 매소홀로 618"),
    "SUWON":    ("수원 KT 위즈 파크", "경기도 수원시 장안구 경수대로 893"),
    "DAEJEON":  ("대전 한화생명 볼파크", "대전광역시 중구 대종로 373"),
    "DAEGU":    ("대구 삼성 라이온즈 파크", "대구광역시 수성구 야구전설로 1"),
    "GWANGJU":  ("광주-KIA 챔피언스 필드", "전남광주통합특별시 북구 서림로 10"),
    "SAJIK":    ("사직야구장", "부산광역시 동래구 사직로 45"),
    "CHANGWON": ("창원 NC 파크", "경상남도 창원시 마산회원구 삼호로 63"),
}

CATEGORY_MAP = {
    "FD6": ("음식점", 1000),
    "CE7": ("카페", 1000),
    "AT4": ("관광명소", 1500),
}

HEADERS = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}


def geocode_address(address: str):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    res = requests.get(url, headers=HEADERS, params={"query": address}, timeout=10)
    res.raise_for_status()
    docs = res.json().get("documents", [])
    if not docs:
        return None, None
    return docs[0]["x"], docs[0]["y"]  # (lng, lat)


def search_category(x: str, y: str, category_group_code: str, radius: int):
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    out = []
    for page in range(1, 4):
        params = {
            "category_group_code": category_group_code,
            "x": x, "y": y, "radius": radius,
            "sort": "distance", "page": page, "size": 15,
        }
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        j = res.json()
        docs = j.get("documents", [])
        if not docs:
            break
        out.extend(docs)
        if j.get("meta", {}).get("is_end"):
            break
        time.sleep(0.15)
    return out


def main():
    if not KAKAO_REST_API_KEY:
        raise SystemExit(
            "KAKAO_REST_API_KEY를 찾지 못했습니다. baseball_data_organized/.env 파일 안에 "
            "KAKAO_REST_API_KEY=실제키 형태로 등호 앞뒤 공백 없이 들어있는지 확인하세요."
        )

    coord_rows = []
    place_rows = []

    for stadium_code, (name, address) in STADIUMS.items():
        x, y = geocode_address(address)
        if x is None:
            print(f"[WARN] {stadium_code} 지오코딩 실패: {address}")
            continue
        coord_rows.append({
            "stadium_code": stadium_code, "stadium_name_ko": name, "address": address,
            "lng_x": x, "lat_y": y, "geocode_source": "KAKAO_LOCAL_ADDRESS_SEARCH",
        })
        print(f"{stadium_code}: ({x}, {y})")

        seq = 0
        for cat_code, (cat_ko, radius) in CATEGORY_MAP.items():
            docs = search_category(x, y, cat_code, radius)
            for d in docs:
                seq += 1
                dist = int(d["distance"]) if d.get("distance") else None
                place_rows.append({
                    "attraction_id": f"KKO_{stadium_code}_{seq:03d}",
                    "stadium_code": stadium_code,
                    "stadium_name": name,
                    "category": cat_ko,
                    "category_group_code": cat_code,
                    "name": d["place_name"],
                    "category_detail": d["category_name"],
                    "address": d.get("road_address_name") or d.get("address_name"),
                    "lng_x": d["x"], "lat_y": d["y"],
                    "distance_m": dist,
                    "phone": d.get("phone", ""),
                    "place_url": d.get("place_url", ""),
                    "kakao_place_id": d.get("id", ""),
                    "in_stadium_flag": "Y" if (dist is not None and dist <= 60) else "N",
                    "source": "KAKAO_LOCAL_API",
                })
        time.sleep(0.2)

    with open(COORD_OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(coord_rows[0].keys()))
        w.writeheader()
        w.writerows(coord_rows)

    with open(PLACES_OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(place_rows[0].keys()))
        w.writeheader()
        w.writerows(place_rows)

    print(f"완료: 구장 {len(coord_rows)}곳, 장소 {len(place_rows)}건 -> {COORD_OUTPUT} / {PLACES_OUTPUT}")


if __name__ == "__main__":
    main()

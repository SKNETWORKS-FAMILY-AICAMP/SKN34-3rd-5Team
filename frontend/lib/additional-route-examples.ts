import type { TripRoute } from "./routes";

// Fictional courses: non-stadium stops are explicitly labelled custom candidate points.
export const additionalRouteExamples: TripRoute[] = [
  {
    "id": "fan-sajik-friends",
    "title": "사직 가는 날, 친구들이랑 밥부터 먹는 코스",
    "stadium": "사직야구장",
    "description": "표만 잡아놓고 약속 장소를 못 정해서 일단 지도부터 찍어봤어요.",
    "content": "표만 잡아놓고 약속 장소를 못 정해서 일단 지도부터 찍어봤어요.\n\n식사는 구장 남쪽에서 해결하고 만나는 장소는 조금 떨어뜨렸습니다. 경기 끝나고는 바로 해산하는 일정이에요. 메뉴는 당일에 정하려고요ㅋㅋ.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "친구와",
      "식사"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-day.jpg",
    "stops": [
      {
        "name": "친구들과 만날 지점",
        "lat": 35.1883668,
        "lng": 129.06290089,
        "category": "직접 지정",
        "placeId": "sample:sajik-friends:0"
      },
      {
        "name": "식사 후보 지점",
        "lat": 35.1903668,
        "lng": 129.06090089,
        "category": "직접 지정",
        "placeId": "sample:sajik-friends:1"
      },
      {
        "name": "사직야구장",
        "lat": 35.1943668,
        "lng": 129.05990089,
        "category": "경기 관람",
        "placeId": "stadium:SAJIK"
      }
    ],
    "author": "사직약속잡는중",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:00:00.000Z"
  },
  {
    "id": "fan-changwon-solo",
    "title": "창원 혼관은 커피 한 잔 들고 느긋하게",
    "stadium": "창원 NC 파크",
    "description": "누구 기다릴 필요 없는 날이라 출발 시간을 넉넉히 잡았습니다.",
    "content": "누구 기다릴 필요 없는 날이라 출발 시간을 넉넉히 잡았습니다.\n\n커피를 마실 곳부터 찾아보고 구장에 들어가려고요. 끝나고는 들어왔던 방향 대신 반대쪽으로 빠져나가는 걸로 찍어봤어요.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "혼자",
      "카페"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-night.jpg",
    "stops": [
      {
        "name": "커피 마실 후보 지점",
        "lat": 35.21898486,
        "lng": 128.57458012,
        "category": "직접 지정",
        "placeId": "sample:changwon-solo:0"
      },
      {
        "name": "창원 NC 파크",
        "lat": 35.22198486,
        "lng": 128.57958012,
        "category": "경기 관람",
        "placeId": "stadium:CHANGWON"
      },
      {
        "name": "귀가 동선 확인 지점",
        "lat": 35.22598486,
        "lng": 128.58258012,
        "category": "직접 지정",
        "placeId": "sample:changwon-solo:2"
      }
    ],
    "author": "혼관연습중",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:01:00.000Z"
  },
  {
    "id": "fan-gwangju-family",
    "title": "부모님이랑 챔필 갈 땐 이동 욕심 줄이기",
    "stadium": "광주-KIA 챔피언스 필드",
    "description": "여러 군데 보여드릴까 하다가 경기 전에 지칠 것 같아서 줄였어요.",
    "content": "여러 군데 보여드릴까 하다가 경기 전에 지칠 것 같아서 줄였어요.\n\n근처에서 만나 한 번 쉬고 들어가는 일정입니다. 중간 지점은 잠깐 앉아 쉴 장소를 찾아보려고 표시해둔 거예요.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "가족과",
      "짧은 동선"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-sunset.jpg",
    "stops": [
      {
        "name": "가족 만남 지점",
        "lat": 35.16642496,
        "lng": 126.89080547,
        "category": "직접 지정",
        "placeId": "sample:gwangju-family:0"
      },
      {
        "name": "쉬어갈 후보 지점",
        "lat": 35.16792496,
        "lng": 126.88980547,
        "category": "직접 지정",
        "placeId": "sample:gwangju-family:1"
      },
      {
        "name": "광주-KIA 챔피언스 필드",
        "lat": 35.16942496,
        "lng": 126.88880547,
        "category": "경기 관람",
        "placeId": "stadium:GWANGJU"
      }
    ],
    "author": "가족표담당",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:02:00.000Z"
  },
  {
    "id": "fan-gocheok-after",
    "title": "고척은 야구부터 보고 저녁 먹으러",
    "stadium": "고척스카이돔",
    "description": "이번에는 경기 전에 이것저것 하지 말고 바로 들어가려고 합니다.",
    "content": "이번에는 경기 전에 이것저것 하지 말고 바로 들어가려고 합니다.\n\n끝난 뒤 남쪽으로 걸어가면서 식당을 고르는 쪽이에요. 경기 종료가 늦으면 식사는 빼고 귀가할 생각입니다.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "경기 후 식사",
      "둘이서"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-day.jpg",
    "stops": [
      {
        "name": "고척스카이돔",
        "lat": 37.49821257,
        "lng": 126.86708874,
        "category": "경기 관람",
        "placeId": "stadium:GOCHEOK"
      },
      {
        "name": "저녁 식사 후보 지점",
        "lat": 37.49421257,
        "lng": 126.86508874,
        "category": "직접 지정",
        "placeId": "sample:gocheok-after:1"
      },
      {
        "name": "해산 지점",
        "lat": 37.49221257,
        "lng": 126.86608874,
        "category": "직접 지정",
        "placeId": "sample:gocheok-after:2"
      }
    ],
    "author": "늦은저녁파",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:03:00.000Z"
  },
  {
    "id": "fan-daegu-photo",
    "title": "라팍 사진은 입장 전에 찍어두려고요",
    "stadium": "대구 삼성 라이온즈 파크",
    "description": "끝나고 사진 찍자고 하면 다들 집 가기 바쁘더라고요.",
    "content": "끝나고 사진 찍자고 하면 다들 집 가기 바쁘더라고요.\n\n이번에는 만나자마자 구장 주변에서 사진부터 남기기로 했습니다. 지도에 찍어둔 곳은 구도를 살펴볼 후보 지점이고 현장에서 조정하려고요.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "사진",
      "첫 방문"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-night.jpg",
    "stops": [
      {
        "name": "사진 약속 지점",
        "lat": 35.84412892,
        "lng": 128.67823637,
        "category": "직접 지정",
        "placeId": "sample:daegu-photo:0"
      },
      {
        "name": "구장 전경 촬영 후보",
        "lat": 35.84262892,
        "lng": 128.67973637,
        "category": "직접 지정",
        "placeId": "sample:daegu-photo:1"
      },
      {
        "name": "대구 삼성 라이온즈 파크",
        "lat": 35.84112892,
        "lng": 128.68123637,
        "category": "경기 관람",
        "placeId": "stadium:DAEGU"
      }
    ],
    "author": "사진한장더",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:04:00.000Z"
  },
  {
    "id": "fan-daejeon-dessert",
    "title": "대전에서는 간식 사고 야구 보러 가는 걸로",
    "stadium": "대전 한화생명 볼파크",
    "description": "식사 약속은 따로 있어서 이번 동선에는 간식만 넣었습니다.",
    "content": "식사 약속은 따로 있어서 이번 동선에는 간식만 넣었습니다.\n\n친구가 고른 빵이랑 제가 고른 음료를 나눠 먹을 예정이에요. 가게는 아직 못 골라서 후보 구역만 찍어놨습니다.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "간식",
      "친구와"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-sunset.jpg",
    "stops": [
      {
        "name": "간식 고를 후보 지점",
        "lat": 36.320337,
        "lng": 127.43201382,
        "category": "직접 지정",
        "placeId": "sample:daejeon-dessert:0"
      },
      {
        "name": "친구와 합류할 지점",
        "lat": 36.318337,
        "lng": 127.43001382,
        "category": "직접 지정",
        "placeId": "sample:daejeon-dessert:1"
      },
      {
        "name": "대전 한화생명 볼파크",
        "lat": 36.317337,
        "lng": 127.42801382,
        "category": "경기 관람",
        "placeId": "stadium:DAEJEON"
      },
      {
        "name": "귀가 전 정리할 지점",
        "lat": 36.315337,
        "lng": 127.43101382,
        "category": "직접 지정",
        "placeId": "sample:daejeon-dessert:3"
      }
    ],
    "author": "간식은별도",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:05:00.000Z"
  },
  {
    "id": "fan-munhak-reunion",
    "title": "문학에서 각자 도착해서 구장 앞에서 합류",
    "stadium": "인천 SSG 랜더스필드",
    "description": "다들 출발지가 달라서 역에서 모이는 건 포기했어요.",
    "content": "다들 출발지가 달라서 역에서 모이는 건 포기했어요.\n\n구장 서쪽에서 합류하고 경기가 끝나면 북쪽에서 다시 인원 확인하려고 합니다. 단체로 다니니까 헤어질 장소까지 정하는 게 마음 편하네요.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "모임",
      "합류"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-day.jpg",
    "stops": [
      {
        "name": "일행 합류 지점",
        "lat": 37.43608198,
        "lng": 126.68675983,
        "category": "직접 지정",
        "placeId": "sample:munhak-reunion:0"
      },
      {
        "name": "인천 SSG 랜더스필드",
        "lat": 37.43508198,
        "lng": 126.69075983,
        "category": "경기 관람",
        "placeId": "stadium:MUNHAK"
      },
      {
        "name": "경기 후 재집결 지점",
        "lat": 37.43908198,
        "lng": 126.68975983,
        "category": "직접 지정",
        "placeId": "sample:munhak-reunion:2"
      }
    ],
    "author": "따로출발같이응원",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:06:00.000Z"
  },
  {
    "id": "fan-suwon-lunch",
    "title": "수원은 점심 약속 끝나고 바로 위팍으로",
    "stadium": "수원 KT 위즈 파크",
    "description": "지난번엔 산책까지 넣었다가 시간 계산을 계속 했어요.",
    "content": "지난번엔 산책까지 넣었다가 시간 계산을 계속 했어요.\n\n이번에는 동쪽에서 점심 먹고 바로 구장으로 향하는 두 지점짜리 코스입니다. 돌아가는 일정은 경기 보고 정하려고요.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "점심",
      "간단한 코스"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-night.jpg",
    "stops": [
      {
        "name": "점심 식사 후보 지점",
        "lat": 37.29884289,
        "lng": 127.0173481,
        "category": "직접 지정",
        "placeId": "sample:suwon-lunch:0"
      },
      {
        "name": "수원 KT 위즈 파크",
        "lat": 37.29784289,
        "lng": 127.0113481,
        "category": "경기 관람",
        "placeId": "stadium:SUWON"
      }
    ],
    "author": "밥먹고위팍",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:07:00.000Z"
  },
  {
    "id": "fan-jamsil-return",
    "title": "잠실에서 만나 잠깐 나갔다 다시 돌아오기",
    "stadium": "잠실야구장",
    "description": "만남은 구장으로 정했는데 친구가 일찍 도착할 수 있다고 하네요.",
    "content": "만남은 구장으로 정했는데 친구가 일찍 도착할 수 있다고 하네요.\n\n표 확인하고 잠깐 서쪽으로 나가 쉬었다가 입장하는 동선으로 그려봤어요. 출발과 도착을 같은 곳으로 둔 코스입니다.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "왕복 코스",
      "재방문"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-sunset.jpg",
    "stops": [
      {
        "name": "잠실야구장",
        "lat": 37.51619878,
        "lng": 127.07594059,
        "category": "경기 관람",
        "placeId": "stadium:JAMSIL"
      },
      {
        "name": "잠깐 쉬어갈 후보 지점",
        "lat": 37.51419878,
        "lng": 127.07194059,
        "category": "직접 지정",
        "placeId": "sample:jamsil-return:1"
      },
      {
        "name": "잠실야구장",
        "lat": 37.51619878,
        "lng": 127.07594059,
        "category": "경기 관람",
        "placeId": "stadium:JAMSIL"
      }
    ],
    "author": "잠실에서만나요",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:08:00.000Z"
  },
  {
    "id": "fan-sajik-date",
    "title": "사직 둘이 가는 날은 경기 후 짧은 산책",
    "stadium": "사직야구장",
    "description": "경기 전에는 바로 입장하고 끝난 뒤에 조금 걸으려고요.",
    "content": "경기 전에는 바로 입장하고 끝난 뒤에 조금 걸으려고요.\n\n아쉬운 경기여도 걸으면서 얘기하면 기분이 풀리더라고요. 길게 걷기보다 북쪽으로 짧게 돌아 나오는 정도로 정했습니다.\n\n지도에 표시한 후보 지점은 예시로 직접 찍은 위치입니다. 실제 매장과 통행 가능 여부는 방문 전에 확인해 주세요.",
    "tags": [
      "둘이서",
      "경기 후 산책"
    ],
    "duration": "경기 전후",
    "cover": "/images/stadium-day.jpg",
    "stops": [
      {
        "name": "사직야구장",
        "lat": 35.1943668,
        "lng": 129.05990089,
        "category": "경기 관람",
        "placeId": "stadium:SAJIK"
      },
      {
        "name": "산책 후보 지점",
        "lat": 35.1973668,
        "lng": 129.05790089,
        "category": "직접 지정",
        "placeId": "sample:sajik-date:1"
      },
      {
        "name": "마무리 지점",
        "lat": 35.1993668,
        "lng": 129.05990089,
        "category": "직접 지정",
        "placeId": "sample:sajik-date:2"
      }
    ],
    "author": "구회말까지",
    "likes": 0,
    "isSample": true,
    "createdAt": "2026-09-13T08:09:00.000Z"
  }
];

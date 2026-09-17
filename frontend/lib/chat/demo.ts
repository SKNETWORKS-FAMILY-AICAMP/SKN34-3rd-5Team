import type { ChatRequest } from "./types";

export function createDemoReply(request: ChatRequest): string {
  const question = request.messages.at(-1)!.content;
  const history = request.messages.filter(message => message.role === "user").map(message => message.content).join(" ");
  const stadium = request.context?.stadium || history.match(/잠실|고척|인천|수원|대전|대구|광주|사직|창원/)?.[0];
  const place = stadium || "선택한 구장";
  if (/일정|오늘.*경기|내일.*경기|결과|순위|스코어/.test(question)) {
    return "경기 일정 질문에 대한 예시 답변이에요.\n\n현재 실제 경기 일정과 결과는 조회하지 않고 있어요. 메인의 경기 카드는 화면 구성을 위한 예시예요.\n방문할 구장과 날짜를 정해두면, 경기 전후에 어떤 활동을 넣을지 코스 초안을 함께 구성할 수 있어요.";
  }
  if (/규칙|이닝|아웃|스트라이크|야구.*처음|야구.*알려/.test(question) || request.context?.intent === "baseball") {
    return "야구 입문 질문에 대한 예시 답변이에요.\n\n공격하는 팀은 주자가 베이스를 돌아 홈에 들어오면 점수를 얻어요. 수비 팀이 아웃 3개를 잡으면 공격과 수비가 바뀌어요. 양 팀이 한 번씩 공격하면 1이닝이에요.\n처음 관람할 때는 전광판의 이닝·점수·아웃 수부터 살펴보면 경기를 따라가기 편해요. 더 궁금한 규칙을 물어보세요.";
  }
  if (/준비|입장|구장.*정보|구장.*알려|주차|교통/.test(question) || request.context?.intent === "stadium") {
    return `${place} 방문 준비를 위한 예시 답변이에요.\n\n1. 예매 내역과 좌석, 입장 게이트를 확인해요.\n2. 경기 당일 교통편과 귀가 방법을 미리 정해요.\n3. 날씨에 맞는 옷과 응원할 때 필요한 물품을 챙겨요.\n\n구장별 반입 규정과 주차 운영은 실제 방문 전에 구단 안내에서 확인해 주세요.`;
  }
  if (/코스|루트|맛집|카페|산책|직관|친구|가족/.test(question) || request.context?.intent === "route") {
    return `${place}에서 보내는 하루를 이렇게 구성해볼 수 있어요. 아래는 미리 준비된 코스 예시예요.\n\n1. 경기 전: 구장 주변에서 식사하며 오늘의 계획을 나눠요.\n2. 경기 관람: 입장 시간을 확인하고 여유 있게 좌석을 찾아가요.\n3. 경기 후: 가까운 산책 공간이나 카페에서 여운을 나눠요.\n\n동행인과 머무를 시간을 정하면 루트 작성 화면에서 나에게 맞는 장소와 순서를 채울 수 있어요.`;
  }
  return "지금은 준비된 예시 답변으로 대화 화면을 체험하고 있어요.\n\n직관 코스, 구장 방문 준비, 야구 기본 규칙을 물어보세요. 예를 들어 ‘잠실에서 친구와 보낼 직관 코스를 추천해줘’처럼 질문할 수 있어요. 실제 AI 연결 후에는 입력한 질문과 대화 맥락에 맞춰 답변해요.";
}

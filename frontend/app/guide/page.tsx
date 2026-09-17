import Link from "next/link";

const baseballQuestions = [
  { question: "야구는 어떤 흐름으로 진행되나요?", answer: "두 팀이 공격과 수비를 번갈아 하며 점수를 겨루는 경기예요. 공격 팀은 타격 후 1루, 2루, 3루를 거쳐 홈으로 돌아오면 득점해요. 수비 팀이 아웃 3개를 잡으면 공수가 바뀌고, 양 팀이 한 번씩 공격하면 한 이닝이 끝나요." },
  { question: "전광판의 B, S, O는 무슨 뜻인가요?", answer: "B는 볼, S는 스트라이크, O는 아웃을 나타내요. 타자는 볼 4개면 볼넷으로 1루에 나가고, 스트라이크 3개면 삼진이 돼요. 파울과 낫아웃 등 상황별 예외가 있으니 처음에는 현재 볼·스트라이크·아웃 수를 따라가 보세요." },
  { question: "전광판의 R, H, E는 무엇인가요?", answer: "R은 득점, H는 안타, E는 실책이에요. 팀의 현재 점수는 R에서 확인할 수 있어요. 안타가 더 많은 팀이 항상 앞서는 것은 아니어서, 점수와 주자 상황을 함께 보면 경기가 더 재미있어져요." },
  { question: "어느 팀을 응원해야 할지 모르겠어요.", answer: "처음에는 살고 있는 지역의 팀, 좋아하는 선수의 팀, 함께 가는 사람이 응원하는 팀부터 살펴봐도 좋아요. 꼭 한 팀을 정하지 않아도 괜찮아요. 구장 분위기와 경기 자체를 즐기면서 마음이 가는 팀을 찾아보세요." },
];
const visitQuestions = [
  { question: "음식이나 음료를 가져갈 수 있나요?", answer: "반입 가능한 용기, 음식, 음료의 종류와 수량은 구장·구단의 운영 방침에 따라 달라질 수 있어요. 방문할 구단의 공식 관람 안내에서 최신 반입 규정을 확인해 주세요. 이 가이드에서는 모든 구장에 동일한 반입 기준을 적용하지 않아요." },
  { question: "비가 오면 경기가 취소되나요?", answer: "강수량, 그라운드 상태, 구장의 특성 등에 따라 경기 진행 여부가 달라져요. 일기예보만으로 취소를 단정하지 말고 구단·리그의 공식 경기 공지를 확인해 주세요. 취소 시 티켓 처리 방법은 구매처 안내를 확인하면 돼요." },
  { question: "구장에는 언제 도착하는 게 좋나요?", answer: "티켓 확인, 입장 대기, 좌석 찾기, 먹거리 구매 시간을 생각해 여유 있게 일정을 잡아 보세요. 입장 시작 시각과 출입구는 구장 및 경기별로 다를 수 있으니 방문일의 공식 안내를 확인해 주세요." },
  { question: "직관 코스는 어떻게 만들어요?", answer: "‘AI 루트 작성’에서 방문할 구장을 고르고 경기 전후에 가고 싶은 장소를 추가해 보세요. 지도에서 순서를 확인하고 본문에 방문 메모를 적으면 돼요. 첫 코스가 고민된다면 다른 사람들이 공유한 코스도 참고할 수 있어요." },
];

export default function GuidePage() {
  return (
    <main className="info-page">
      <section className="info-hero"><div className="container page-intro"><p className="eyebrow">YOUR FIRST GAME</p><h1>첫 직관도, 어렵지 않아요.</h1><p>알고 가면 더 즐거운 야구.<br className="info-mobile-break" /> 함께 차근차근 준비해 볼까요?</p></div></section>
      <div className="container info-guide-layout">
        <aside className="info-guide-sidebar"><p>직관 가이드</p><nav aria-label="가이드 목차"><a href="#baseball">01 <span>야구, 이것부터</span></a><a href="#checklist">02 <span>떠나기 전 체크</span></a><a href="#visit">03 <span>자주 묻는 질문</span></a></nav><div className="info-guide-tip"><span aria-hidden="true">✦</span><strong>나만의 하루를 그려 보세요</strong><p>경기 전 식사부터 경기 후 산책까지, 직관의 즐거움은 구장 밖에서도 이어져요.</p><Link href="/routes/new">코스 만들러 가기 →</Link></div></aside>
        <div className="info-guide-content">
          <section id="baseball" className="info-guide-section"><p className="eyebrow">01 · BASEBALL BASICS</p><h2>야구, 이것부터 알아봐요</h2><p className="info-guide-description">처음에는 모든 규칙을 몰라도 괜찮아요.</p><div className="info-faq-list">{baseballQuestions.map((item, index) => <details className="info-faq" key={item.question} open={index === 0}><summary><span className="info-question-mark">Q</span><span>{item.question}</span><span className="info-faq-toggle" aria-hidden="true">+</span></summary><p>{item.answer}</p></details>)}</div></section>
          <section id="checklist" className="info-guide-section"><p className="eyebrow">02 · BEFORE YOU GO</p><h2>떠나기 전, 한 번만 체크!</h2><p className="info-guide-description">작은 준비가 더 편안한 하루를 만들어 줘요.</p><div className="info-checklist">{[{ title: "티켓과 좌석", body: "경기 날짜, 구장, 좌석과 입장 방법 확인" }, { title: "교통과 동선", body: "갈 때와 돌아올 때의 이동 방법 준비" }, { title: "날씨와 준비물", body: "방문일 날씨에 맞는 옷과 준비물 챙기기" }, { title: "구장 운영 안내", body: "방문할 구단의 최신 반입·입장 공지 확인" }].map((item, index) => <div className="info-checklist-item" key={item.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{item.title}</h3><p>{item.body}</p></div><span className="info-checklist-check" aria-hidden="true">✓</span></div>)}</div></section>
          <section id="visit" className="info-guide-section"><p className="eyebrow">03 · GOOD TO KNOW</p><h2>구장 가기 전 궁금한 것들</h2><div className="info-faq-list">{visitQuestions.map((item) => <details className="info-faq" key={item.question}><summary><span className="info-question-mark">Q</span><span>{item.question}</span><span className="info-faq-toggle" aria-hidden="true">+</span></summary><p>{item.answer}</p></details>)}</div></section>
        </div>
      </div>
      <section className="container info-help-banner"><div><p className="eyebrow">MAKE IT YOUR DAY</p><h2>이제, 나만의 직관을 시작해 볼까요?</h2><p>가고 싶은 구장을 고르고 하루의 코스를 만들어 보세요.</p></div><Link href="/stadiums" className="button button-primary">구장 둘러보기 <span aria-hidden="true">→</span></Link></section>
    </main>
  );
}

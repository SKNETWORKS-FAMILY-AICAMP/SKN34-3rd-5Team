"use client";

import { Suspense, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Icon } from "@/components/icons";
import { RouteNumber } from "@/components/route-number";
import { formatRouteDate } from "@/components/route-card";
import { RouteBoardSkeleton, RouteListSkeleton } from "@/components/route-skeleton";
import { useLikedRoutes, useRoutes, useRoutesReady, useRouteViews } from "@/lib/routes";
import { routeContentToText } from "@/lib/route-content";
import { CommunityBoardTabs, TeamCommunityBoard } from "@/components/team-community-board";

const stadiums = ["전체", "잠실", "고척", "인천", "수원", "대전", "대구", "광주", "사직", "창원"];
type SearchField = "all" | "title" | "content" | "author";
const normalize = (value: string) => value.replace(/\s/g, "").toLocaleLowerCase("ko");

function CommunityBoard({ initialQuery, initialStadium, deleted }: { initialQuery: string; initialStadium: string; deleted: boolean }) {
  const [query, setQuery] = useState(initialQuery);
  const [searchInput, setSearchInput] = useState(initialQuery);
  const [searchField, setSearchField] = useState<SearchField>("all");
  const [activeSearchField, setActiveSearchField] = useState<SearchField>("all");
  const [stadium, setStadium] = useState(initialStadium);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sort, setSort] = useState("newest");
  const [showDeleted, setShowDeleted] = useState(deleted);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const routes = useRoutes();
  const ready = useRoutesReady();
  const liked = useLikedRoutes();
  const views = useRouteViews();
  const filtered = routes.filter(route => {
    if (stadium !== "전체" && !normalize(route.stadium).includes(normalize(stadium))) return false;
    const content = routeContentToText(route.content, route.contentFormat);
    const fields = {
      all: [route.title, route.author, route.stadium, route.description, content, ...route.tags, ...route.stops.map(stop => stop.name)].join(" "),
      title: route.title,
      content: [route.description, content, ...route.stops.map(stop => stop.name)].join(" "),
      author: route.author,
    };
    return normalize(fields[activeSearchField]).includes(normalize(query));
  });
  const sorted = [...filtered].sort((a, b) => {
    const newest = b.createdAt.localeCompare(a.createdAt);
    if (sort === "likes") return (b.likes + Number(liked.includes(b.id))) - (a.likes + Number(liked.includes(a.id))) || newest;
    if (sort === "views") return ((b.views ?? 0) + (views[b.id] ?? 0)) - ((a.views ?? 0) + (views[a.id] ?? 0)) || newest;
    return newest;
  });
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const visible = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const firstPage = Math.max(1, Math.min(currentPage - 2, pageCount - 4));
  const pageNumbers = Array.from({ length: Math.min(5, pageCount) }, (_, index) => firstPage + index);
  const writeHref = stadium === "전체" ? "/routes/new" : `/routes/new?stadium=${encodeURIComponent(stadium)}`;

  function focusResults() {
    resultsHeading.current?.focus({ preventScroll: true });
    resultsHeading.current?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }
  function changePage(nextPage: number) { setPage(nextPage); focusResults(); }
  function resetFilters() {
    setQuery(""); setSearchInput(""); setSearchField("all"); setActiveSearchField("all"); setStadium("전체"); setPage(1);
  }

  return (
    <main className="container community-page">
      <nav className="community-breadcrumb" aria-label="현재 위치"><Link href="/">홈</Link><Icon name="chevron" size={12}/><span aria-current="page">커뮤니티</span></nav>
      <header className="community-header">
        <div><p className="eyebrow">KBO COMMUNITY</p><h1>팬 커뮤니티</h1><p className="community-description">다른 팬들의 하루를 만나고, 나만의 직관 코스를 나눠보세요.</p></div>
        <Link href={writeHref} className="button button-primary community-write"><Icon name="book" size={18}/>글쓰기</Link>
      </header>

      <CommunityBoardTabs active="routes"/>

      <div className="community-layout">
        <section className="community-board" aria-labelledby="community-board-heading">
          <div className="community-board-heading"><h2 id="community-board-heading" ref={resultsHeading} tabIndex={-1}>직관 루트 공유</h2><span>우리의 야구, 우리의 하루</span></div>
          {showDeleted && <div className="route-feedback" role="status"><span>게시글을 삭제했어요.</span><button type="button" aria-label="삭제 안내 닫기" onClick={() => setShowDeleted(false)}>×</button></div>}

          <div className="community-stadiums" role="group" aria-label="구장으로 필터">
            {stadiums.map(item => <button type="button" key={item} className={stadium === item ? "is-active" : ""} aria-pressed={stadium === item} onClick={() => { setStadium(item); setPage(1); }}>{item}</button>)}
          </div>
          <div className="community-toolbar">
            <p>전체 <strong>{ready ? sorted.length : "…"}</strong>개 <span className="community-page-count">{currentPage} / {pageCount} 페이지</span></p>
            <div className="community-sort">
              <label><span className="sr-only">게시글 정렬</span><select value={sort} onChange={event => { setSort(event.target.value); setPage(1); }}><option value="newest">최신순</option><option value="likes">좋아요순</option><option value="views">조회순</option></select></label>
              <label><span className="sr-only">페이지당 게시글 수</span><select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }}><option value={5}>5개씩</option><option value={10}>10개씩</option><option value={20}>20개씩</option></select></label>
            </div>
          </div>
          {query && <div className="community-search-result"><span>‘{query}’ 검색 결과</span><button type="button" onClick={() => { setQuery(""); setSearchInput(""); setPage(1); }}>검색 해제 <Icon name="close" size={13}/></button></div>}
          <p className="sr-only" role="status">{ready ? `게시글 ${sorted.length}개, ${currentPage}페이지` : "게시글을 불러오고 있어요."}</p>

          {!ready ? <RouteBoardSkeleton/> : <table className="community-table">
            <caption className="sr-only">팬들이 남긴 직관 루트. 제목을 선택하면 본문과 지도를 볼 수 있습니다.</caption>
            <colgroup><col className="community-col-number"/><col/><col className="community-col-author"/><col className="community-col-metric"/><col className="community-col-metric"/><col className="community-col-date"/></colgroup>
            <thead><tr><th scope="col">번호</th><th scope="col" className="community-title-column">제목</th><th scope="col">글쓴이</th><th scope="col">좋아요</th><th scope="col">조회</th><th scope="col">작성일</th></tr></thead>
            <tbody>{visible.length ? visible.map((route) => {
              const likeCount = route.likes + Number(liked.includes(route.id));
              const viewCount = (route.views ?? 0) + (views[route.id] ?? 0);
              const shortStadium = stadiums.slice(1).find(item => route.stadium.includes(item)) ?? route.stadium;
              return <tr key={route.id}>
                <td className="community-number"><RouteNumber route={route} /></td>
                <td className="community-post">
                  <Link href={`/routes/${encodeURIComponent(route.id)}`} className="community-post-link">
                    <span className="community-post-labels"><span className="community-stadium-label">{shortStadium}</span><span className="community-sample-label">{route.isSample ? "샘플" : "내 글"}</span></span>
                    <span className="community-post-title">{route.title}</span>
                  </Link>
                  <div className="community-mobile-meta"><span className="community-mobile-author">{route.author}</span><time dateTime={route.createdAt}>{formatRouteDate(route.createdAt)}</time><span>조회 {viewCount}</span><span className={liked.includes(route.id) ? "is-liked" : ""}><Icon name="heart" size={12}/><span className="sr-only">좋아요 </span>{likeCount}</span></div>
                </td>
                <td className="community-author"><span>{route.author}</span></td>
                <td className={liked.includes(route.id) ? "community-metric is-liked" : "community-metric"}>{likeCount}</td>
                <td className="community-metric">{viewCount}</td>
                <td className="community-date"><time dateTime={route.createdAt}>{formatRouteDate(route.createdAt)}</time></td>
              </tr>;
            }) : <tr><td colSpan={6} className="community-empty"><Icon name="search" size={32}/><h3>{query ? "검색 결과가 없어요" : "아직 등록된 글이 없어요"}</h3><p>{query ? "다른 검색어를 입력하거나 구장 필터를 바꿔보세요." : `${stadium === "전체" ? "나만의" : stadium} 직관 코스를 첫 글로 남겨보세요.`}</p><div><button type="button" className="button button-secondary" onClick={resetFilters}>전체 글 보기</button><Link href={writeHref} className="button button-primary">글쓰기</Link></div></td></tr>}</tbody>
          </table>}

          <div className="community-board-bottom">
            {ready && sorted.length > 0 && <nav className="route-pagination community-pagination" aria-label="커뮤니티 게시판 페이지">
              <button type="button" aria-label="처음 페이지" disabled={currentPage === 1} onClick={() => changePage(1)}>«</button>
              <button type="button" aria-label="이전 페이지" disabled={currentPage === 1} onClick={() => changePage(currentPage - 1)}>‹</button>
              {pageNumbers.map(number => <button type="button" key={number} aria-label={`${number}페이지`} aria-current={currentPage === number ? "page" : undefined} className={currentPage === number ? "is-active" : ""} onClick={() => changePage(number)}>{number}</button>)}
              <button type="button" aria-label="다음 페이지" disabled={currentPage === pageCount} onClick={() => changePage(currentPage + 1)}>›</button>
              <button type="button" aria-label="마지막 페이지" disabled={currentPage === pageCount} onClick={() => changePage(pageCount)}>»</button>
            </nav>}
          </div>
          <form className="community-search" role="search" aria-label="커뮤니티 게시글 검색" onSubmit={event => { event.preventDefault(); setQuery(searchInput.trim()); setActiveSearchField(searchField); setPage(1); focusResults(); }}>
            <label><span className="sr-only">검색 범위</span><select value={searchField} onChange={event => setSearchField(event.target.value as SearchField)}><option value="all">전체</option><option value="title">제목</option><option value="content">내용</option><option value="author">글쓴이</option></select></label>
            <label className="community-search-input"><span className="sr-only">게시글 검색어</span><input type="search" placeholder="궁금한 직관 코스를 검색해보세요" maxLength={150} value={searchInput} onChange={event => setSearchInput(event.target.value)}/></label>
            <button type="submit" aria-label="게시글 검색"><Icon name="search" size={18}/><span>검색</span></button>
          </form>
          <p className="community-storage-note">샘플 글이 포함되어 있습니다. 현재 내 글·좋아요·조회 수는 이 브라우저에만 저장됩니다.</p>
        </section>

        <aside className="community-sidebar" aria-label="커뮤니티 안내">
          <div className="community-welcome"><span className="community-welcome-icon"><Icon name="route" size={26}/></span><p className="eyebrow">SHARE YOUR DAY</p><h2>나의 직관이<br/>누군가의 좋은 코스로.</h2><p>경기 전 들른 맛집부터<br/>경기 후 여운이 남는 산책길까지.<br/>나만의 하루를 기록해보세요.</p><Link href={writeHref} className="button button-primary">내 루트 작성하기<Icon name="arrow" size={16}/></Link></div>
          <nav className="community-quick-links" aria-label="직관 준비 바로가기"><h2>직관 준비하기</h2><Link href="/stadiums"><Icon name="stadium" size={20}/><span>구장 정보</span><Icon name="chevron" size={14}/></Link><Link href="/guide"><Icon name="book" size={20}/><span>첫 직관 가이드</span><Icon name="chevron" size={14}/></Link></nav>
        </aside>
      </div>
    </main>
  );
}

function RoutesQuery() {
  const params = useSearchParams();
  if (params.get("board") === "free") return <TeamCommunityBoard key={params.toString()} teamCode={params.get("team") ?? ""} postId={params.get("post") ?? ""}/>;
  const requestedStadium = params.get("stadium") ?? "전체";
  const initialStadium = stadiums.find(stadium => normalize(requestedStadium).includes(stadium)) ?? "전체";
  return <CommunityBoard key={params.toString()} initialQuery={params.get("q") ?? ""} initialStadium={initialStadium} deleted={params.get("deleted") === "1"}/>;
}

export default function RoutesPage() {
  return <Suspense fallback={<RouteListSkeleton/>}><RoutesQuery/></Suspense>;
}

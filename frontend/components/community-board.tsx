"use client";

import Link from "next/link";
import { CommunityPostBottom } from "./community-post-bottom";
import { PostCategory } from "./post-category";
import { PostReportButton } from "./post-report-button";
import { PostCommentCount } from "./post-comment-count";
import { useRef, useState } from "react";
import { getTeamBoard, getTeamBoardHref, teamBoards } from "@/lib/team-community";
import { retryCommunityPosts, useCommunityPosts } from "@/lib/community-api";
import { useCommunityVotes } from "@/lib/community-votes";
import styles from "./community-board.module.css";

const boards = [
  { id: "free", title: "자유 게시판", href: "/community", description: "응원하는 팀에 관계없이 모든 야구팬과 자유롭게 이야기를 나눠보세요." },
  { id: "teams", title: "팀 게시판", href: "/community/teams", description: "응원하는 팀을 골라 같은 팀 팬들과 야구 이야기를 나눠보세요." },
  { id: "predictions", title: "승부 예측", href: "/community/predictions", description: "전체 또는 팀별로 경기 결과를 예상하고 서로의 생각을 나눠보세요." },
] as const;

export function CommunityBoard({ section, teamCode = "", postId = "" }: { section: typeof boards[number]["id"]; teamCode?: string; postId?: string }) {
  const writeDialog = useRef<HTMLDialogElement>(null);
  const { votes, toggle } = useCommunityVotes();
  const [voteError, setVoteError] = useState("");
  const board = boards.find((item) => item.id === section)!;
  const team = section === "free" ? undefined : getTeamBoard(teamCode);
  const community = useCommunityPosts(section !== "predictions");
  const allPosts = section === "predictions" ? [] : community.posts.filter(post => post.board === section);
  const searchContext = `${section}:${teamCode}:${postId}`;
  const [search, setSearch] = useState({ context: searchContext, team: team?.code ?? "all", field: "all", query: "" });
  const activeSearch = search.context === searchContext ? search : { team: team?.code ?? "all", field: "all", query: "" };
  const query = activeSearch.query.trim().toLocaleLowerCase("ko-KR");
  const posts = allPosts.filter(post => {
    if (activeSearch.team !== "all" && post.teamCode !== activeSearch.team) return false;
    const text = activeSearch.field === "author" ? post.author : activeSearch.field === "title" ? post.title : `${post.title} ${post.content}`;
    return text.toLocaleLowerCase("ko-KR").includes(query);
  });
  const selectedPost = allPosts.find(post => post.id === postId);
  const scope = JSON.stringify([searchContext, activeSearch.team, activeSearch.field, query]);
  const [pagination, setPagination] = useState({ scope, page: 1 });
  const pageCount = Math.max(1, Math.ceil(posts.length / 20));
  const page = pagination.scope === scope ? Math.min(pagination.page, pageCount) : 1;
  const visiblePosts = posts.slice((page - 1) * 20, page * 20);
  const pageStart = Math.floor((page - 1) / 5) * 5 + 1;
  const pages = Array.from({ length: Math.min(5, pageCount - pageStart + 1) }, (_, index) => pageStart + index);
  const changePage = (nextPage: number) => setPagination({ scope, page: nextPage });
  const postHref = (code: string, id: string) => section === "free" ? `/community?post=${encodeURIComponent(id)}` : getTeamBoardHref(code, id);
  const boardHref = (href: string) => team ? `${href}?team=${team.code}` : href;
  return <main className={`container ${styles.page}`}>
    <p className="eyebrow">COMMUNITY</p>
    <h1>{board.title}</h1>
    <nav className={styles.tabs} aria-label="커뮤니티 게시판">
      {boards.map((item) => <Link key={item.id} href={item.id === "free" ? item.href : boardHref(item.href)} aria-current={item.id === section ? "page" : undefined}>{item.title}</Link>)}
    </nav>
    {section === "teams" && <nav className={styles.teamTabs} aria-label="팀 게시판 선택">
      <Link href={getTeamBoardHref()} aria-current={!team ? "page" : undefined}>전체</Link>
      {teamBoards.map(item => <Link key={item.code} href={getTeamBoardHref(item.code)} aria-current={team?.code === item.code ? "page" : undefined}>{item.shortName}</Link>)}
    </nav>}
    {section !== "predictions" && community.error && community.posts.length > 0 && <p role="alert">{community.error} <button type="button" onClick={() => void retryCommunityPosts()}>다시 시도</button></p>}
    {section !== "predictions" && community.loading && community.posts.length === 0 ? <p role="status">게시글을 불러오고 있어요.</p> : section !== "predictions" && community.error && community.posts.length === 0 ? <p role="alert">{community.error} <button type="button" onClick={() => void retryCommunityPosts()}>다시 시도</button></p> : <section aria-label={`${board.title} 글 목록`}>
      {selectedPost && <article className={styles.postDetail}>
        <header className={styles.postHeader}>
          <h2 className={styles.postHeading}>{section !== "free" && <strong>{getTeamBoard(selectedPost.teamCode)?.shortName}</strong>}<PostCategory category={selectedPost.category} freeBoard={section === "free"} /><span>{selectedPost.title}<PostCommentCount count={selectedPost.commentCount} /></span></h2>
          <div className={styles.postMeta}>
            <div className={styles.postMetaInfo}>
              <span aria-label={`게시글 번호 ${selectedPost.postNumber}`}>{selectedPost.postNumber}</span>
              <span>{selectedPost.author}</span>
              {selectedPost.createdAt ? <time dateTime={selectedPost.createdAt}>{new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Seoul" }).format(new Date(selectedPost.createdAt))}</time> : <span aria-label="작성일 없음">—</span>}
            </div>
            <div className={styles.postMetrics}><span>조회 <b>{selectedPost.views}</b></span><span>추천 <b>{selectedPost.recommendations + Number(votes[selectedPost.id] === "up")}</b></span><span>댓글 <b>{selectedPost.commentCount ?? 0}</b></span></div>
          </div>
        </header>
        <div className={`${styles.postBody} ${styles.teamPostBody} ${styles.reportableBody}`}><div>{selectedPost.content}</div><PostReportButton key={selectedPost.id} postNumber={selectedPost.postNumber} /></div>
        <div className={styles.postVotes} role="group" aria-label="게시글 추천과 비추천">
          {(["up", "down"] as const).map(vote => <button key={vote} type="button" aria-pressed={votes[selectedPost.id] === vote} className={vote === "up" ? styles.voteUp : styles.voteDown} onClick={() => { try { toggle(selectedPost.id, vote); setVoteError(""); } catch { setVoteError("선택을 저장하지 못했어요. 다시 시도해 주세요."); } }}><span>{vote === "up" ? "추천" : "비추천"}</span><b>{vote === "up" ? selectedPost.recommendations + Number(votes[selectedPost.id] === "up") : Number(votes[selectedPost.id] === "down")}</b></button>)}
        </div>
        {voteError && <p role="alert">{voteError}</p>}
        <CommunityPostBottom key={selectedPost.id} post={selectedPost} posts={posts} teamCode={team?.code} isFree={section === "free"} />
      </article>}
      <div className={styles.listWriteActions}><button type="button" onClick={() => writeDialog.current?.showModal()}>글쓰기</button></div>
      <div className={styles.tableScroll} role="region" aria-label={`${board.title} 목록, 좁은 화면에서는 좌우로 스크롤`} tabIndex={0}>
        <table className={styles.boardTable}>
          <caption className="sr-only">{board.title} 게시글 목록. 구분은 게시글 고유 번호입니다.</caption>
          <colgroup><col className={styles.numberCol} />{section !== "free" && <col className={styles.teamCol} />}<col /><col className={styles.authorCol} /><col className={styles.dateCol} /><col className={styles.countCol} /><col className={styles.countCol} /></colgroup>
          <thead><tr>{["구분", ...(section !== "free" ? ["팀"] : []), "제목", "글쓴이", "작성일", "조회", "추천"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>{visiblePosts.length ? visiblePosts.map(post => <tr key={post.id} className={post.id === postId ? styles.selectedRow : undefined}>
            <td>{post.postNumber}</td>
            {section !== "free" && <td className={styles.teamCell}>{getTeamBoard(post.teamCode)?.shortName}</td>}
            <td className={styles.titleCell}><Link href={postHref(post.teamCode, post.id)} aria-current={post.id === postId ? "page" : undefined}><PostCategory category={post.category} freeBoard={section === "free"} /> {post.title}<PostCommentCount count={post.commentCount} /></Link></td>
            <td>{post.author}</td>
            <td>{post.createdAt ?? "—"}</td>
            <td>{post.views}</td>
            <td>{post.recommendations + Number(votes[post.id] === "up")}</td>
          </tr>) : <tr><td colSpan={section === "free" ? 6 : 7} className={styles.emptyCell}>{query || activeSearch.team !== "all" ? "검색 결과가 없어요." : "등록된 게시글이 없어요."}</td></tr>}</tbody>
        </table>
      </div>
      <div className={styles.listWriteActions}><button type="button" onClick={() => writeDialog.current?.showModal()}>글쓰기</button></div>
      <dialog ref={writeDialog} className={styles.reportDialog} aria-label="글쓰기 안내"><form method="dialog"><h2>글쓰기</h2><p>게시글 작성은 서버 연결 후 이용할 수 있어요.</p><button type="submit">닫기</button></form></dialog>
      {pageCount > 1 && <nav className={styles.pagination} aria-label="게시판 페이지">
        <button type="button" aria-label="이전 페이지" disabled={page === 1} onClick={() => changePage(page - 1)}>‹</button>
        {pages.map(number => <button type="button" key={number} aria-label={`${number}페이지`} aria-current={page === number ? "page" : undefined} onClick={() => changePage(number)}>{number}</button>)}
        <button type="button" aria-label="다음 페이지" disabled={page === pageCount} onClick={() => changePage(page + 1)}>›</button>
      </nav>}
      <form key={searchContext} className={styles.searchForm} role="search" aria-label="게시글 검색" onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        setSearch({ context: searchContext, team: String(data.get("team") ?? "all"), field: String(data.get("field") ?? "all"), query: String(data.get("query") ?? "") });
        setPagination({ scope: "", page: 1 });
      }}>
        {section !== "free" && <select name="team" aria-label="검색할 팀" defaultValue={team?.code ?? "all"}>
          <option value="all">전체 팀</option>
          {teamBoards.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}
        </select>}
        <select name="field" aria-label="검색 옵션" defaultValue="all">
          <option value="all">제목+본문</option><option value="title">제목</option><option value="author">닉네임</option>
        </select>
        <input name="query" type="search" aria-label="검색어" placeholder="검색어를 입력하세요" />
        <button type="submit">검색</button>
      </form>
    </section>}
  </main>;
}

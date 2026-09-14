"use client";

import Link from "next/link";
import { PostCategory } from "./post-category";
import { PostCommentCount } from "./post-comment-count";
import { useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { TeamLogo } from "@/components/team-logo";
import { getTeamBoard, getTeamBoardHref, getTeamBoardPosts, teamBoards } from "@/lib/team-community";
import "@/styles/team-community.css";

export function CommunityBoardTabs({ active }: { active: "routes" | "free" }) {
  return (
    <nav className="community-board-tabs" aria-label="커뮤니티 게시판">
      <Link href="/routes" aria-current={active === "routes" ? "page" : undefined}>직관 루트 공유</Link>
      <Link href={getTeamBoardHref()} aria-current={active === "free" ? "page" : undefined}>팀별 자유게시판</Link>
    </nav>
  );
}

export function TeamCommunityBoard({ teamCode, postId }: { teamCode: string; postId: string }) {
  const team = getTeamBoard(teamCode);
  const posts = team ? getTeamBoardPosts(team.code) : teamBoards.flatMap(item => getTeamBoardPosts(item.code));
  const selectedPost = postId ? posts.find(post => post.id === postId) : undefined;
  const selectedPostTeam = selectedPost ? getTeamBoard(selectedPost.teamCode) : undefined;
  const [page, setPage] = useState(1);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const pageSize = 20;
  const pageCount = Math.max(1, Math.ceil(posts.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const visiblePosts = posts.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  function changePage(nextPage: number) {
    setPage(nextPage);
    listHeading.current?.focus({ preventScroll: true });
    listHeading.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }

  return (
    <main className="container community-page team-community-page">
      <nav className="community-breadcrumb" aria-label="현재 위치"><Link href="/">홈</Link><Icon name="chevron" size={12}/><span aria-current="page">커뮤니티</span></nav>
      <header className="community-header">
        <div><p className="eyebrow">KBO COMMUNITY</p><h1>팬 커뮤니티</h1><p className="community-description">같은 팀을 응원하는 팬들과 야구 이야기를 나누는 공간이에요.</p></div>
      </header>
      <CommunityBoardTabs active="free"/>
      <nav className="team-community-filters" aria-label="팀별 자유게시판 선택">
        <Link href={getTeamBoardHref()} aria-current={!team ? "page" : undefined}>전체 팀</Link>
        {teamBoards.map(item => <Link key={item.code} href={getTeamBoardHref(item.code)} aria-current={team?.code === item.code ? "page" : undefined}>{item.shortName}</Link>)}
      </nav>

      {postId ? selectedPost && selectedPostTeam ? (
        <article className="team-community-article" aria-labelledby="free-post-heading">
          <div className="team-community-article-team"><TeamLogo code={selectedPostTeam.code} name={selectedPostTeam.name} className="team-community-logo"/><Link href={getTeamBoardHref(selectedPostTeam.code)}>{selectedPostTeam.name} 자유게시판</Link></div>
          <header><div className="community-post-labels"><PostCategory category={selectedPost.category} /><span className="community-sample-label">샘플 글</span></div><h2 id="free-post-heading">{selectedPost.title}</h2></header>
          <p className="team-community-post-content">{selectedPost.content}</p>
          <p className="team-community-sample-note">화면 구성을 확인하기 위한 샘플 글입니다. 실제 이용자가 작성한 글이 아닙니다.</p>
          <Link className="button button-secondary" href={getTeamBoardHref(team?.code)}>목록으로</Link>
        </article>
      ) : (
        <section className="team-community-missing" aria-labelledby="missing-free-post"><h2 id="missing-free-post">게시글을 찾을 수 없어요</h2><p>목록에서 다른 이야기를 선택해 주세요.</p><Link className="button button-secondary" href={getTeamBoardHref(team?.code)}>목록으로</Link></section>
      ) : (
        <section className="community-board" aria-labelledby="free-board-heading">
          <div className="community-board-heading"><h2 id="free-board-heading" ref={listHeading} tabIndex={-1}>{team ? `${team.name} 자유게시판` : "팀별 자유게시판"}</h2><span>함께 응원하고, 자유롭게 이야기해요</span></div>
          <div className="community-toolbar"><p>전체 <strong>{posts.length}</strong>개 <span className="community-page-count">{currentPage} / {pageCount} 페이지</span></p><span>미리보기용 샘플 글</span></div>
          <table className="community-table team-community-table">
            <caption className="sr-only">팀별 자유게시판 샘플 글. 제목을 누르면 내용을 볼 수 있습니다.</caption>
            <colgroup><col className="community-col-number"/><col className="team-community-col-team"/><col/><col className="team-community-col-kind"/></colgroup>
            <thead><tr><th scope="col">번호</th><th scope="col">팀</th><th scope="col" className="community-title-column">제목</th><th scope="col">구분</th></tr></thead>
            <tbody>{visiblePosts.map((post, index) => {
              const postTeam = getTeamBoard(post.teamCode);
              return <tr key={post.id}>
                <td className="community-number">{posts.length - (currentPage - 1) * pageSize - index}</td>
                <td><span className="team-community-table-team"><TeamLogo code={post.teamCode} name={postTeam?.name ?? post.teamCode} className="team-community-logo"/><span>{postTeam?.shortName ?? post.teamCode}</span></span></td>
                <td className="community-post"><Link className="community-post-link" href={getTeamBoardHref(post.teamCode, post.id)}><span className="community-post-labels"><PostCategory category={post.category} /><span className="team-community-mobile-team">{postTeam?.name}</span><span className="community-sample-label">샘플</span></span><span className="community-post-title">{post.title}</span><PostCommentCount count={post.commentCount} /></Link></td>
                <td>샘플 글</td>
              </tr>;
            })}</tbody>
          </table>
          {pageCount > 1 && <nav className="route-pagination community-pagination" aria-label="팀 자유게시판 페이지"><button type="button" aria-label="이전 페이지" disabled={currentPage === 1} onClick={() => changePage(currentPage - 1)}>‹</button>{Array.from({ length: pageCount }, (_, index) => index + 1).map(number => <button type="button" key={number} aria-label={`${number}페이지`} aria-current={currentPage === number ? "page" : undefined} className={currentPage === number ? "is-active" : ""} onClick={() => changePage(number)}>{number}</button>)}<button type="button" aria-label="다음 페이지" disabled={currentPage === pageCount} onClick={() => changePage(currentPage + 1)}>›</button></nav>}
          <p className="community-storage-note">현재는 화면 구성을 위한 샘플 글이 표시됩니다. 게시글 등록과 이용자 간 공유는 서버 연결 후 제공됩니다.</p>
        </section>
      )}
    </main>
  );
}

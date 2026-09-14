"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { getTeamBoard, getTeamBoardHref, type TeamCommunityPost } from "@/lib/team-community";
import styles from "./community-board.module.css";

export function CommunityPostBottom({ post, posts, teamCode, isFree = false }: { post: TeamCommunityPost; posts: TeamCommunityPost[]; teamCode?: string; isFree?: boolean }) {
  const postHref = (item: TeamCommunityPost) => isFree ? `/community?post=${encodeURIComponent(item.id)}` : getTeamBoardHref(item.teamCode, item.id);
  const router = useRouter();
  const writer = useRef<HTMLDialogElement>(null);
  const [message, setMessage] = useState("");
  const [order, setOrder] = useState("oldest");
  const index = posts.findIndex(item => item.id === post.id);
  const next = index >= 0 ? posts[index + 1] : undefined;
  const previous = index > 0 ? posts[index - 1] : undefined;
  return <>
    <section className={styles.authorProfile} aria-label="작성자 프로필">
      <img src="/images/default-avatar.svg" width="56" height="56" alt="작성자 기본 프로필" />
      <div><strong>{post.author}</strong><p>{!isFree && <>{getTeamBoard(post.teamCode)?.shortName} · </>}작성자</p></div>
    </section>
    <section className={styles.comments} aria-label="댓글">
      <header><h3>댓글 <b>{post.commentCount ?? 0}</b></h3><div><button type="button" aria-pressed={order === "oldest"} onClick={() => setOrder("oldest")}>등록순</button><button type="button" aria-pressed={order === "newest"} onClick={() => setOrder("newest")}>최신순</button><button type="button" onClick={() => router.refresh()}>↻ 새로고침</button></div></header>
      <p className={styles.commentsEmpty}>아직 등록된 댓글이 없어요.</p>
      <form className={styles.commentForm} onSubmit={event => { event.preventDefault(); setMessage("댓글 등록은 서버 연결 후 이용할 수 있어요."); }}>
        <textarea aria-label="댓글 내용" placeholder="댓글을 입력해 주세요." maxLength={2000} required />
        <button type="submit">등록</button>
      </form>
      {message && <p role="status" className={styles.bottomNote}>{message}</p>}
    </section>
    <nav className={styles.articleNavigation} aria-label="게시글 이동">
      <div><Link href={isFree ? "/community" : getTeamBoardHref(teamCode)}>목록</Link>{next ? <Link href={postHref(next)}>다음글</Link> : <button disabled>다음글</button>}{previous ? <Link href={postHref(previous)}>이전글</Link> : <button disabled>이전글</button>}</div>
      <div><button type="button" className={styles.writeButton} onClick={() => writer.current?.showModal()}>글쓰기</button><button type="button" onClick={() => router.back()}>이전페이지</button><button type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>맨위로 ↑</button></div>
    </nav>
    <dialog ref={writer} className={styles.reportDialog} aria-label="글쓰기 안내"><form method="dialog"><h2>글쓰기</h2><p>게시글 작성은 서버 연결 후 이용할 수 있어요.</p><button type="submit">닫기</button></form></dialog>
  </>;
}

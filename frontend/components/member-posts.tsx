"use client";

import Link from "next/link";
import { useState } from "react";
import styles from "./community-board.module.css";

const areas = [{ id: "all", name: "전체" }, { id: "free", name: "자유게시판" }, { id: "teams", name: "팀 게시판" }, { id: "predictions", name: "승부 예측" }] as const;
type MemberPost = { id: string; area: string; title: string; href: string; createdAt: string };

export function MemberPosts({ posts = [] }: { posts?: MemberPost[] }) {
  const [area, setArea] = useState<string>("all");
  // Populate from the authored-post API, independently of saved courses.
  const visible = posts.filter(post => area === "all" || post.area === area);
  return <section aria-label="내가 쓴 글">
    <h2 className={styles.memberPostsHeading}>내가 쓴 글</h2>
    <div className={styles.memberPostTags} role="group" aria-label="작성 영역 선택">{areas.map(item => <button type="button" key={item.id} aria-pressed={area === item.id} onClick={() => setArea(item.id)}>{item.name}</button>)}</div>
    {visible.length ? <ul className={styles.memberPostList}>{visible.map(post => <li key={post.id}><span>{areas.find(item => item.id === post.area)?.name ?? "게시글"}</span><Link href={post.href}>{post.title}</Link><time dateTime={post.createdAt}>{new Date(post.createdAt).toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" })}</time></li>)}</ul> : <p className={styles.commentsEmpty}>이 영역에 작성한 글이 없어요.</p>}
  </section>;
}

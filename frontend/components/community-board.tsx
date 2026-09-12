"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { getTeamBoard, teamBoards } from "@/lib/team-community";
import { Icon } from "./icons";
import styles from "./community-board.module.css";

const boards = [
  { id: "free", title: "자유 게시판", href: "/community/teams", description: "전체 팬들과 함께하거나, 응원하는 팀을 골라 야구 이야기를 나눠보세요." },
  { id: "predictions", title: "승부 예측", href: "/community/predictions", description: "전체 또는 팀별로 경기 결과를 예상하고 서로의 생각을 나눠보세요." },
] as const;

export function CommunityBoard({ section, teamCode = "" }: { section: typeof boards[number]["id"]; teamCode?: string }) {
  const router = useRouter();
  const board = boards.find((item) => item.id === section)!;
  const team = getTeamBoard(teamCode);
  const boardHref = (href: string) => team ? `${href}?team=${team.code}` : href;
  return <main className={`container ${styles.page}`}>
    <p className="eyebrow">COMMUNITY</p>
    <h1>{board.title}</h1>
    <p className={styles.description}>{board.description}</p>
    <nav className={styles.tabs} aria-label="커뮤니티 게시판">
      {boards.map((item) => <Link key={item.id} href={boardHref(item.href)} aria-current={item.id === section ? "page" : undefined}>{item.title}</Link>)}
    </nav>
    <div className={styles.filters}>
      <label htmlFor="community-team">팀 선택</label>
      <select id="community-team" aria-label={`${board.title} 팀 선택`} value={team?.code ?? "all"} onChange={(event) => {
        const selected = getTeamBoard(event.target.value);
        router.push(selected ? `${board.href}?team=${selected.code}` : board.href, { scroll: false });
      }}>
        <option value="all">전체</option>
        {teamBoards.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
      </select>
      <p role="status">{team ? team.name : "전체"} · {board.title}</p>
    </div>
    <section className={styles.empty} aria-labelledby="community-status">
      <Icon name="chat" size={32} />
      <h2 id="community-status">{team ? `${team.name} ${board.title}` : board.title}을 준비하고 있어요</h2>
      <p>게시글 조회·작성과 댓글 기능은 아직 연결되지 않았어요.</p>
    </section>
  </main>;
}

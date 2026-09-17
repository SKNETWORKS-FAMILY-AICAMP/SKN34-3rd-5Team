import Link from "next/link";
import { getTeamBoard } from "@/lib/team-community";
import styles from "./community-board.module.css";

export type CommunityNavigationProps = {
  active: "routes" | "free" | "teams" | "predictions";
  teamCode?: string;
};

const items = [
  { id: "routes", label: "직관", href: "/routes" },
  { id: "free", label: "자유 게시판", href: "/community" },
  { id: "teams", label: "팀 게시판", href: "/community/teams" },
  { id: "predictions", label: "승부 예측", href: "/community/predictions" },
] as const;

export function CommunityNavigation({ active, teamCode = "" }: CommunityNavigationProps) {
  const team = getTeamBoard(teamCode)?.code;
  return <nav className={styles.tabs} aria-label="팬 커뮤니티">
    {items.map(item => {
      const href = team && (item.id === "teams" || item.id === "predictions") ? `${item.href}?team=${team}` : item.href;
      return <Link key={item.id} href={href} aria-current={item.id === active ? "page" : undefined}>{item.label}</Link>;
    })}
  </nav>;
}

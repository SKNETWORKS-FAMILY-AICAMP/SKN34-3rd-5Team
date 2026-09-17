import { CommunityBoard } from "./community-board";
import { CommunityNavigation } from "./community-navigation";

// CommunityBoard owns useCommunityPosts and its "다시 시도" error UI; these exports only preserve legacy callers.

export function CommunityBoardTabs({ active }: { active: "routes" | "free" }) {
  return <CommunityNavigation active={active === "free" ? "teams" : active} />;
}

export function TeamCommunityBoard({ teamCode, postId }: { teamCode: string; postId: string }) {
  return <CommunityBoard section="teams" teamCode={teamCode} postId={postId} />;
}

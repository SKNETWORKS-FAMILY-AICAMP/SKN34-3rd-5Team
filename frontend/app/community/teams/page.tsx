import { CommunityBoard } from "@/components/community-board";

export const metadata = { title: "자유 게시판" };
export default async function Page({ searchParams }: { searchParams: Promise<{ team?: string | string[] }> }) {
  const { team } = await searchParams;
  return <CommunityBoard section="free" teamCode={typeof team === "string" ? team : ""} />;
}

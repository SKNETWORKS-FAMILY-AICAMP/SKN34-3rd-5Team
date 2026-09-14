import { CommunityBoard } from "@/components/community-board";

export const metadata = { title: "승부 예측" };
export default async function Page({ searchParams }: { searchParams: Promise<{ team?: string | string[] }> }) {
  const { team } = await searchParams;
  return <CommunityBoard section="predictions" teamCode={typeof team === "string" ? team : ""} />;
}

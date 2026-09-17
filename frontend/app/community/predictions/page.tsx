import { PredictionBoard } from "@/components/prediction-board";

export const metadata = { title: "승부 예측" };
export default async function Page({ searchParams }: { searchParams: Promise<{ date?: string | string[]; team?: string | string[]; game?: string | string[] }> }) {
  const { date, team, game } = await searchParams;
  return <PredictionBoard
    initialDate={typeof date === "string" ? date : ""}
    initialTeam={typeof team === "string" ? team : ""}
    initialGameId={typeof game === "string" ? game : ""}
  />;
}

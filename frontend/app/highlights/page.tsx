import type { Metadata } from "next";
import { KboHighlightBoard } from "@/components/kbo-highlight-board";
import "@/styles/kbo-detail.css";

export const metadata: Metadata = { title: "KBO 리그 하이라이트" };

export default async function HighlightsPage({ searchParams }: PageProps<"/highlights">) {
  const query = await searchParams;
  const requested = typeof query.video === "string" ? query.video : "";
  const initialVideoId = /^[A-Za-z0-9_-]{11}$/.test(requested) ? requested : "";
  return <KboHighlightBoard key={initialVideoId} initialVideoId={initialVideoId} />;
}

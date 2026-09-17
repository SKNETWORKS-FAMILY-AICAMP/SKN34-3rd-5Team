import type { Metadata } from "next";
import { KboStandingsPage } from "@/components/kbo-standings-page";
import "@/styles/kbo-detail.css";

export const metadata: Metadata = { title: "KBO 순위·기록" };

export default function StandingsPage() {
  return <KboStandingsPage />;
}

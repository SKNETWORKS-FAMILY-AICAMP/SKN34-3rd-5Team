import type { Metadata } from "next";
import { KboSchedulePage } from "@/components/kbo-schedule-page";
import "@/styles/kbo-detail.css";

export const metadata: Metadata = { title: "KBO 경기 일정" };

export default function SchedulePage() {
  return <KboSchedulePage />;
}

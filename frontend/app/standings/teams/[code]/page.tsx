import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { KboTeamProfilePage } from "@/components/kbo-team-profile-page";
import { isKboTeamCode } from "@/lib/kbo/tving-details";
import "@/styles/kbo-profile.css";

export const metadata: Metadata = { title: "KBO 구단 상세" };

export default async function TeamProfileRoute({ params }: { params: Promise<{ code: string }> }) {
  const code = (await params).code.toUpperCase();
  if (!isKboTeamCode(code)) notFound();
  return <KboTeamProfilePage code={code} />;
}


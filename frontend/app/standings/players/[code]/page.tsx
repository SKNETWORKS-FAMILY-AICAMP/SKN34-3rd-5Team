import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { KboAthleteProfilePage } from "@/components/kbo-athlete-profile-page";
import { isKboAthleteCode } from "@/lib/kbo/tving-details";
import "@/styles/kbo-profile.css";

export const metadata: Metadata = { title: "KBO 선수 상세" };

export default async function AthleteProfileRoute({ params }: { params: Promise<{ code: string }> }) {
  const code = (await params).code;
  if (!isKboAthleteCode(code)) notFound();
  return <KboAthleteProfilePage code={code} />;
}


import { getLatestKboHighlights } from "@/lib/youtube/kbo-highlight";
import type { KboHighlightApiResponse } from "@/lib/youtube/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const requestedLimit = Number.parseInt(new URL(request.url).searchParams.get("limit") ?? "", 10);
    const data = await getLatestKboHighlights(requestedLimit);
    const body: KboHighlightApiResponse = { data, error: null };
    return Response.json(body, { headers: { "Cache-Control": "no-store" } });
  } catch {
    const body: KboHighlightApiResponse = { data: [], error: "최신 KBO 하이라이트를 불러오지 못했어요." };
    return Response.json(body, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

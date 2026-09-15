import { getTourismPlaces, parseTourismQuery } from "@/lib/tour-api-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const raw = { stadium: params.get("stadium"), lat: Number(params.get("lat")), lng: Number(params.get("lng")) };
  const query = params.get("lat")?.trim() && params.get("lng")?.trim() ? parseTourismQuery(raw) : null;
  if (!query) return json({ error: "구장 위치를 확인해 주세요." }, 400);
  const result = await getTourismPlaces(query, process.env.TOUR_API_KEY);
  return json(result.body, result.status);
}

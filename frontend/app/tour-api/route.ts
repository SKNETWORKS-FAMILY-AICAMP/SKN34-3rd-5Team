import { stadiums } from "@/lib/stadiums";
import { distanceMeters } from "@/lib/nearby-places";
import { fetchTourPlaces } from "@/lib/tour-api";
import type { TourResult } from "@/lib/tour-places";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const cache = new Map<string, { expires: number; result: TourResult }>();
const pending = new Map<string, Promise<TourResult>>();
let windowStarted = 0, requestCount = 0;
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const venue = stadiums.find((stadium) => stadium.code === params.get("stadium"));
  const lat = Number(params.get("lat")), lng = Number(params.get("lng"));
  if (!venue || !params.get("lat")?.trim() || !params.get("lng")?.trim() || !Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180 || distanceMeters(venue, { lat, lng }) > 1000) return json({ error: "구장 위치를 확인해 주세요." }, 400);
  const serviceKey = process.env.TOUR_API_KEY?.trim();
  if (!serviceKey) return json({ status: "unconfigured", places: [], truncated: false } satisfies TourResult);
  const key = `${venue.code}:${lat.toFixed(6)}:${lng.toFixed(6)}`;
  const now = Date.now();
  const cached = cache.get(key);
  if (cached && cached.expires > now) return json(cached.result);
  const existing = pending.get(key);
  if (existing) return json(await existing);
  if (now - windowStarted > 60_000) { windowStarted = now; requestCount = 0; }
  if (requestCount >= 20 || pending.size >= 3) return json({ error: "관광공사 장소를 잠시 후 다시 불러와 주세요." }, 429);
  requestCount++;
  const task = fetchTourPlaces({ ...venue, lat, lng }, serviceKey);
  pending.set(key, task);
  try {
    const result = await task;
    if (result.status === "ok") {
      if (cache.size >= 90) cache.clear();
      cache.set(key, { result, expires: Date.now() + 10 * 60_000 });
    }
    return json(result);
  } finally { pending.delete(key); }
}

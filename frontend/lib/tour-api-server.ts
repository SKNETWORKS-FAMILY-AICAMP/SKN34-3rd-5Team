import { stadiums } from "./stadiums";
import { distanceMeters } from "./nearby-places";
import { fetchTourPlaces } from "./tour-api";
import type { TourResult } from "./tour-places";

export type TourismQuery = { stadium: string; lat: number; lng: number };
type TourismResponse = { body: TourResult | { error: string }; status: number };
const cache = new Map<string, { expires: number; result: TourResult }>();
const pending = new Map<string, Promise<TourResult>>();
let windowStarted = 0, requestCount = 0;

export function parseTourismQuery(value: unknown): TourismQuery | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const body = value as Record<string, unknown>;
  const venue = stadiums.find((stadium) => stadium.code === body.stadium);
  const lat = body.lat, lng = body.lng;
  if (!venue || typeof lat !== "number" || typeof lng !== "number" || !Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180 || distanceMeters(venue, { lat, lng }) > 1000) return null;
  return { stadium: venue.code, lat, lng };
}

export async function getTourismPlaces(query: TourismQuery, serviceKey: string | undefined, fetcher: typeof fetch = fetch): Promise<TourismResponse> {
  const venue = stadiums.find((stadium) => stadium.code === query.stadium)!;
  if (!serviceKey?.trim()) return { body: { status: "unconfigured", places: [], truncated: false }, status: 200 };
  const key = `${venue.code}:${query.lat.toFixed(6)}:${query.lng.toFixed(6)}`;
  const now = Date.now();
  const cached = cache.get(key);
  if (cached && cached.expires > now) return { body: cached.result, status: 200 };
  const existing = pending.get(key);
  if (existing) return { body: await existing, status: 200 };
  if (now - windowStarted > 60_000) { windowStarted = now; requestCount = 0; }
  if (requestCount >= 20 || pending.size >= 3) return { body: { error: "관광공사 장소를 잠시 후 다시 불러와 주세요." }, status: 429 };
  requestCount++;
  const task = fetchTourPlaces({ ...venue, lat: query.lat, lng: query.lng }, serviceKey, fetcher);
  pending.set(key, task);
  try {
    const result = await task;
    if (result.status === "ok") {
      if (cache.size >= 90) cache.clear();
      cache.set(key, { result, expires: Date.now() + 10 * 60_000 });
    }
    return { body: result, status: 200 };
  } finally { pending.delete(key); }
}

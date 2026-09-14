import { mergePlaces, type NearbyPlace, type NearbyStadium } from "./nearby-places";
import { normalizeTourPlace, parseTourPage, TOUR_CONTENT_TYPES, type TourResult } from "./tour-places";

// Called by the Next route only; credentials never enter the client bundle.
export async function fetchTourPlaces(stadium: NearbyStadium, serviceKey: string, fetcher: typeof fetch = fetch): Promise<TourResult> {
  const places: NearbyPlace[] = [];
  let successes = 0, failures = 0, truncated = false;
  let key = serviceKey.trim();
  try { key = decodeURIComponent(key); } catch { /* Already-decoded service keys are also accepted. */ }
  await Promise.all(TOUR_CONTENT_TYPES.map(async (contentTypeId) => {
    for (let page = 1; page <= 3; page++) {
      try {
        const params = new URLSearchParams({ serviceKey: key, MobileOS: "ETC", MobileApp: "KBORoute", _type: "json", mapX: String(stadium.lng), mapY: String(stadium.lat), radius: "2500", contentTypeId, arrange: "E", numOfRows: "100", pageNo: String(page) });
        const response = await fetcher(`https://apis.data.go.kr/B551011/KorService2/locationBasedList2?${params}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
        if (!response.ok) throw new Error("Tourism request failed");
        const { items, total } = parseTourPage(await response.json());
        successes++;
        for (const item of items) { const place = normalizeTourPlace(item, stadium); if (place) places.push(place); }
        if (page * 100 >= total) break;
        if (page === 3) truncated = true;
      } catch {
        // Upstream errors may contain the credential-bearing URL. Never expose them.
        failures++;
        break;
      }
    }
  }));
  return { status: failures ? successes ? "partial" : "error" : "ok", places: mergePlaces([], places), truncated };
}

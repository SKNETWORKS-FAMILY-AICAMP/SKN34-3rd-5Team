import type { KakaoMaps, KakaoPlace } from "./kakao-maps";
import { NEARBY_RADIUS, NEARBY_SEARCHES, normalizePlace, type CategoryFilter, type NearbyPlace, type NearbyStadium, type SearchSpec } from "./nearby-places";

type SearchPage = { places: KakaoPlace[]; hasNextPage: boolean };
const cache = new Map<string, { expires: number; result: SearchPage }>();

export async function searchPage(maps: KakaoMaps, stadium: NearbyStadium, spec: SearchSpec, page: number, signal: AbortSignal): Promise<SearchPage> {
  signal.throwIfAborted();
  const key = `${stadium.code}:${stadium.lat}:${stadium.lng}:${spec.method}:${spec.query}:${spec.accuracy ?? false}:${page}`;
  const saved = cache.get(key);
  if (saved && saved.expires > Date.now()) return saved.result;
  const result = await new Promise<SearchPage>((resolve, reject) => {
    let settled = false;
    const finish = (result?: SearchPage, error?: Error) => {
      if (settled) return;
      settled = true; clearTimeout(timer); signal.removeEventListener("abort", abort);
      if (error) reject(error); else resolve(result!);
    };
    const abort = () => finish(undefined, new DOMException("Search cancelled", "AbortError"));
    const timer = setTimeout(() => finish(undefined, new Error("장소 검색 응답이 늦어지고 있어요.")), 8000);
    signal.addEventListener("abort", abort, { once: true });
    try {
      const service = new maps.services.Places();
      const callback = (places: KakaoPlace[], status: string, pagination: { hasNextPage: boolean }) => {
        if (status === maps.services.Status.ZERO_RESULT) finish({ places: [], hasNextPage: false });
        else if (status === maps.services.Status.OK) finish({ places, hasNextPage: pagination?.hasNextPage ?? false });
        else finish(undefined, new Error("일부 장소를 불러오지 못했어요."));
      };
      const options = { location: new maps.LatLng(stadium.lat, stadium.lng), radius: NEARBY_RADIUS, size: 15, page, sort: spec.accuracy ? maps.services.SortBy.ACCURACY : maps.services.SortBy.DISTANCE, ...(spec.group ? { category_group_code: spec.group } : {}) };
      if (spec.method === "category") service.categorySearch(spec.query, callback, options);
      else service.keywordSearch(spec.query, callback, options);
    } catch { finish(undefined, new Error("장소 검색을 시작하지 못했어요.")); }
  });
  signal.throwIfAborted();
  if (cache.size > 600) cache.clear();
  cache.set(key, { expires: Date.now() + 5 * 60_000, result });
  return result;
}

// Address geocodes may point at the entire sports complex (not the ballpark).
// Resolve the actual baseball venue before setting the search radius.
export async function resolveStadium(maps: KakaoMaps, stadium: NearbyStadium, signal: AbortSignal): Promise<NearbyStadium> {
  const result = await searchPage(maps, stadium, { kind: "sight", method: "keyword", query: stadium.name, accuracy: true }, 1, signal);
  const compact = (value: string) => value.replace(/[\s-]/g, "").toLowerCase().replace(/kia/g, "기아");
  const venue = result.places.find((place) => /야구장/.test(place.category_name ?? "") && compact(place.place_name).includes(compact(stadium.name).replace(/^인천/, "")));
  if (!venue || !venue.x.trim() || !venue.y.trim() || !Number.isFinite(Number(venue.x)) || !Number.isFinite(Number(venue.y))) throw new Error("구장 위치를 확인하지 못했어요. 다시 불러와 주세요.");
  return { ...stadium, lat: Number(venue.y), lng: Number(venue.x), address: venue.road_address_name || stadium.address };
}

export async function collectNearbyPlaces(maps: KakaoMaps, stadium: NearbyStadium, signal: AbortSignal, preferred: () => CategoryFilter, onUpdate: (places: NearbyPlace[], completed: number, failures: number) => void) {
  const queue = NEARBY_SEARCHES.map((spec, order) => ({ spec, order, page: 1 }));
  let completed = 0, failures = 0;
  async function worker() {
    while (queue.length && !signal.aborted) {
      const category = preferred();
      queue.sort((a, b) => {
        const priority = (job: typeof a) => category === job.spec.kind ? -1 : job.spec.kind === "stay" ? 2 : job.spec.kind === "store" ? 1 : 0;
        return priority(a) - priority(b) || a.page - b.page || a.order - b.order;
      });
      const job = queue.shift()!;
      try {
        const result = await searchPage(maps, stadium, job.spec, job.page, signal);
        signal.throwIfAborted();
        const normalized = result.places.map((place) => normalizePlace(place, stadium)).filter((place): place is NearbyPlace => place !== null);
        if (result.hasNextPage && job.page < 3) queue.push({ ...job, page: job.page + 1 });
        else completed++;
        onUpdate(normalized, completed, failures);
      } catch (error) {
        if (signal.aborted) throw error;
        failures++; completed++; onUpdate([], completed, failures);
      }
    }
  }
  await Promise.all([worker(), worker()]);
  return { completed, failures };
}

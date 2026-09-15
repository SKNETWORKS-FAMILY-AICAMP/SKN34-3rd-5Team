import type { KakaoPlace } from "./kakao-maps";

type Obj = Record<string, unknown>;
export type KakaoPlaceQuery = {
  method: "keyword" | "category";
  keyword?: string;
  category?: string;
  lat: number;
  lng: number;
  radius?: number;
  page: number;
  size: number;
  sort: "accuracy" | "distance";
};
export type KakaoPlacePage = { places: KakaoPlace[]; hasNextPage: boolean };

const CATEGORIES = new Set(["FD6", "CE7", "AT4", "CT1", "CS2", "AD5"]);
const object = (value: unknown): Obj | null => value && typeof value === "object" && !Array.isArray(value) ? value as Obj : null;
const finiteCoordinate = (value: unknown, limit: number) => typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= limit;
const integer = (value: unknown, min: number, max: number) => Number.isInteger(value) && Number(value) >= min && Number(value) <= max;

export function parseKakaoPlaceQuery(value: unknown): KakaoPlaceQuery | null {
  const body = object(value);
  if (!body || typeof body.method !== "string" || !["keyword", "category"].includes(body.method) || !finiteCoordinate(body.lat, 90) || !finiteCoordinate(body.lng, 180) || !integer(body.page, 1, 3) || !integer(body.size, 1, 15) || typeof body.sort !== "string" || !["accuracy", "distance"].includes(body.sort)) return null;
  if (body.radius !== undefined && !integer(body.radius, 1, 20_000)) return null;
  const keyword = typeof body.keyword === "string" ? body.keyword.trim() : "";
  const category = typeof body.category === "string" ? body.category.trim() : "";
  if (body.method === "keyword" ? keyword.length < 1 || keyword.length > 100 || Boolean(category && !CATEGORIES.has(category)) : !CATEGORIES.has(category)) return null;
  return {
    method: body.method as KakaoPlaceQuery["method"],
    ...(keyword ? { keyword } : {}),
    ...(category ? { category } : {}),
    lat: body.lat as number,
    lng: body.lng as number,
    ...(body.radius === undefined ? {} : { radius: body.radius as number }),
    page: body.page as number,
    size: body.size as number,
    sort: body.sort as KakaoPlaceQuery["sort"],
  };
}

const field = (value: Obj, key: string) => typeof value[key] === "string" ? value[key] as string : "";
function normalizeKakaoPlace(value: unknown): KakaoPlace | null {
  const item = object(value);
  if (!item) return null;
  const id = field(item, "id"), name = field(item, "place_name"), x = field(item, "x"), y = field(item, "y");
  if (!id || !name || !x || !y || !Number.isFinite(Number(x)) || !Number.isFinite(Number(y))) return null;
  return {
    id,
    place_name: name,
    road_address_name: field(item, "road_address_name"),
    address_name: field(item, "address_name"),
    category_group_name: field(item, "category_group_name"),
    category_group_code: field(item, "category_group_code"),
    category_name: field(item, "category_name"),
    phone: field(item, "phone"),
    x,
    y,
  };
}

const cache = new Map<string, { expires: number; result: KakaoPlacePage }>();
export async function fetchKakaoPlacePage(query: KakaoPlaceQuery, key: string, fetcher: typeof fetch = fetch, signal?: AbortSignal): Promise<KakaoPlacePage> {
  const cacheKey = JSON.stringify(query);
  const saved = cache.get(cacheKey);
  if (saved && saved.expires > Date.now()) return saved.result;
  const params = new URLSearchParams({
    ...(query.method === "keyword" ? { query: query.keyword! } : { category_group_code: query.category! }),
    ...(query.method === "keyword" && query.category ? { category_group_code: query.category } : {}),
    x: String(query.lng), y: String(query.lat), page: String(query.page), size: String(query.size), sort: query.sort,
    ...(query.radius ? { radius: String(query.radius) } : {}),
  });
  const requestSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(8000)]) : AbortSignal.timeout(8000);
  const response = await fetcher(`https://dapi.kakao.com/v2/local/search/${query.method}.json?${params}`, { headers: { Authorization: `KakaoAK ${key}` }, cache: "no-store", signal: requestSignal });
  if (!response.ok) throw new Error("Kakao place request failed");
  const value = object(await response.json());
  const meta = object(value?.meta), documents = value?.documents;
  if (!meta || typeof meta.is_end !== "boolean" || !Array.isArray(documents)) throw new Error("Invalid Kakao place response");
  const result = { places: documents.map(normalizeKakaoPlace).filter((place): place is KakaoPlace => place !== null), hasNextPage: !meta.is_end };
  if (cache.size >= 600) cache.clear();
  cache.set(cacheKey, { expires: Date.now() + 5 * 60_000, result });
  return result;
}

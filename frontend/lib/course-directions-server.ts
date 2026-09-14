import { validTravelPoint, type CourseDirections, type TravelLeg, type TravelMode, type TravelPoint } from "./course-directions";

type Obj = Record<string, unknown>;
const obj = (v: unknown): Obj => v && typeof v === "object" ? v as Obj : {};
const list = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
const amount = (v: unknown) => typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null;
const noRoute = () => new Error("이 구간의 경로를 찾지 못했어요. 다른 이동 수단이나 장소를 선택해 주세요.");

export function parseDirections(mode: TravelMode, value: unknown): TravelLeg {
  const data = obj(value);
  if (["SAME_POINT", "EQUAL_POINTS"].includes(String(data.status))) return { status: "ok", distance: 0, seconds: 0, paths: [], instructions: ["출발지와 도착지가 같은 위치예요."] };
  let distance: number | null, seconds: number | null;
  let steps: unknown[];
  if (mode === "car") {
    const route = obj(list(data.routes)[0]);
    if (route.result_code !== 0) throw noRoute();
    distance = amount(obj(route.summary).distance); seconds = amount(obj(route.summary).duration);
    steps = list(route.sections).flatMap((section) => list(obj(section).roads)).map((road) => {
      const r = obj(road), vertices = list(r.vertexes), points = [];
      for (let i = 0; i + 1 < vertices.length; i += 2) points.push([vertices[i], vertices[i + 1]]);
      return { path: { points }, properties: { guidance: typeof r.name === "string" && r.name ? `${r.name} 이동` : "도로 이동" } };
    });
  } else {
    if (data.status !== "OK") throw noRoute();
    const routes = list(data.routes).map(obj).filter((r) => amount(obj(r.properties).totalTime) !== null);
    const route = mode === "walk" ? obj(data.route) : routes.sort((a, b) => Number(obj(a.properties).totalTime) - Number(obj(b.properties).totalTime))[0];
    if (!route) throw noRoute();
    distance = amount(obj(route.properties).totalDistance); seconds = amount(obj(route.properties).totalTime);
    steps = mode === "walk" ? list(route.legs).flatMap((leg) => list(obj(leg).steps)) : list(route.steps);
  }
  if (distance === null || seconds === null) throw noRoute();
  const paths = steps.map((step) => list(obj(obj(step).path).points).map((pair) => {
    const values = list(pair); return { lng: values[0], lat: values[1] };
  }).filter(validTravelPoint)).filter((path) => path.length > 1);
  if (distance > 0 && paths.length === 0) throw noRoute();
  const instructions = steps.map((step) => obj(obj(step).properties).guidance).filter((v): v is string => typeof v === "string" && Boolean(v));
  return { status: "ok", distance, seconds, paths, instructions };
}

export function parseCourseRequest(value: unknown): { mode: TravelMode; points: TravelPoint[] } | null {
  const body = obj(value);
  if (!["walk", "car", "transit"].includes(String(body.mode)) || !Array.isArray(body.points) || body.points.length < 2 || body.points.length > 13 || !body.points.every(validTravelPoint)) return null;
  return { mode: body.mode as TravelMode, points: body.points.map(({ lat, lng }) => ({ lat, lng })) };
}

const cache = new Map<string, { expires: number; leg: TravelLeg }>();
export async function fetchCourseDirections(mode: TravelMode, points: TravelPoint[], key: string, fetcher: typeof fetch = fetch, signal?: AbortSignal): Promise<CourseDirections> {
  const legs: TravelLeg[] = [];
  async function fetchLeg(a: TravelPoint, b: TravelPoint): Promise<TravelLeg> {
    if (a.lat === b.lat && a.lng === b.lng) return { status: "ok", distance: 0, seconds: 0, paths: [], instructions: ["같은 위치예요."] };
    const cacheKey = `${mode}:${a.lng},${a.lat}:${b.lng},${b.lat}`;
    const saved = cache.get(cacheKey);
    if (saved && saved.expires > Date.now()) return saved.leg;
    const params = mode === "car" ? new URLSearchParams({ origin: `${a.lng},${a.lat}`, destination: `${b.lng},${b.lat}`, summary: "false", alternatives: "false" }) : new URLSearchParams({ start_x: String(a.lng), start_y: String(a.lat), end_x: String(b.lng), end_y: String(b.lat), input_coord: "WGS84", output_coord: "WGS84" });
    const base = mode === "car" ? "https://apis-navi.kakaomobility.com/v1/directions" : `https://dapi.kakao.com/v2/routing/${mode === "walk" ? "walk" : "publictraffic"}`;
    try {
      const response = await fetcher(`${base}?${params}`, { headers: { Authorization: `KakaoAK ${key}` }, cache: "no-store", signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000) });
      if (!response.ok) return { status: "error", paths: [], instructions: [], error: response.status === 429 ? "길찾기 요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요." : "길찾기 서비스에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." };
      const leg = parseDirections(mode, await response.json());
      if (cache.size >= 500) cache.clear();
      cache.set(cacheKey, { leg, expires: Date.now() + (mode === "walk" ? 30 : 2) * 60_000 });
      return leg;
    } catch {
      return { status: "error", paths: [], instructions: [], error: "경로를 조회하지 못했어요. 다른 이동 수단을 선택하거나 다시 조회해 주세요." };
    }
  }
  // Preserve visit order; bound simultaneous calls, including a current-location leg.
  for (let i = 0; i < points.length - 1; i += 3) {
    signal?.throwIfAborted();
    legs.push(...await Promise.all(points.slice(i, Math.min(i + 3, points.length - 1)).map((point, offset) => fetchLeg(point, points[i + offset + 1]))));
  }
  const complete = legs.every((leg) => leg.status === "ok");
  return { mode, legs, seconds: complete ? legs.reduce((sum, leg) => sum + leg.seconds!, 0) : null, distance: complete ? legs.reduce((sum, leg) => sum + leg.distance!, 0) : null };
}

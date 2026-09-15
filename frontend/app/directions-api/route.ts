import { fetchCourseDirections, parseCourseRequest } from "@/lib/course-directions-server";
import { fetchKakaoPlacePage, parseKakaoPlaceQuery } from "@/lib/kakao-places-server";
import { getTourismPlaces, parseTourismQuery } from "@/lib/tour-api-server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
const limits = {
  directions: { started: 0, count: 0, active: 0, perMinute: 40, concurrent: 4 },
  places: { started: 0, count: 0, active: 0, perMinute: 240, concurrent: 8 },
};
function enter(kind: keyof typeof limits) {
  const limit = limits[kind], now = Date.now();
  if (now - limit.started > 60_000) { limit.started = now; limit.count = 0; }
  if (limit.count >= limit.perMinute || limit.active >= limit.concurrent) return false;
  limit.count++; limit.active++;
  return true;
}
export async function POST(request: Request) {
  const length = Number(request.headers.get("content-length"));
  if (Number.isFinite(length) && length > 12_000) return json({ error: "요청 내용이 너무 커요." }, 413);
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return json({ error: "JSON 요청만 사용할 수 있어요." }, 415);
  let body: unknown;
  try { const raw = await request.text(); if (new TextEncoder().encode(raw).byteLength > 12_000) return json({ error: "요청 내용이 너무 커요." }, 413); body = JSON.parse(raw); }
  catch { return json({ error: "요청 내용을 확인해 주세요." }, 400); }
  const value = body && typeof body === "object" && !Array.isArray(body) ? body as Record<string, unknown> : null;
  const action = value && "action" in value ? value.action : "directions";
  if (typeof action !== "string" || !["directions", "places", "tourism"].includes(action)) return json({ error: "지원하지 않는 지도 요청이에요." }, 400);

  if (action === "tourism") {
    const query = parseTourismQuery(value);
    if (!query) return json({ error: "구장 위치를 확인해 주세요." }, 400);
    const result = await getTourismPlaces(query, process.env.TOUR_API_KEY);
    return json(result.body, result.status);
  }

  const key = process.env.KAKAO_REST_API_KEY?.trim();
  if (!key) return json({ error: "지도 데이터 연결 설정이 필요해요. 서버의 카카오 REST API 키를 확인해 주세요." }, 503);
  if (action === "places") {
    const query = parseKakaoPlaceQuery(value);
    if (!query) return json({ error: "장소 검색 조건을 확인해 주세요." }, 400);
    if (!enter("places")) return json({ error: "장소 검색 요청이 많아요. 잠시 후 다시 시도해 주세요." }, 429);
    try { return json(await fetchKakaoPlacePage(query, key, fetch, request.signal)); }
    catch { return json({ error: "일부 장소를 불러오지 못했어요." }, 502); }
    finally { limits.places.active--; }
  }

  const directions = parseCourseRequest(value);
  if (!directions) return json({ error: "2~13개의 유효한 위치와 이동 수단을 선택해 주세요." }, 400);
  if (!enter("directions")) return json({ error: "길찾기 요청이 많아요. 잠시 후 다시 시도해 주세요." }, 429);
  try { return json(await fetchCourseDirections(directions.mode, directions.points, key, fetch, request.signal)); }
  catch { return json({ error: "길찾기 조회가 중단됐어요. 다시 시도해 주세요." }, 502); }
  finally { limits.directions.active--; }
}

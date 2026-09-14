import { fetchCourseDirections, parseCourseRequest } from "@/lib/course-directions-server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
let started = 0, count = 0, active = 0;
export async function POST(request: Request) {
  let body;
  try { const raw = await request.text(); if (raw.length > 12000) return json({ error: "코스가 너무 길어요." }, 413); body = parseCourseRequest(JSON.parse(raw)); }
  catch { return json({ error: "코스 좌표를 확인해 주세요." }, 400); }
  if (!body) return json({ error: "2~13개의 유효한 위치와 이동 수단을 선택해 주세요." }, 400);
  const key = process.env.KAKAO_REST_API_KEY?.trim();
  if (!key) return json({ error: "길찾기 연결 설정이 필요해요. 서버의 카카오 REST API 키를 확인해 주세요." }, 503);
  if (Date.now() - started > 60000) { started = Date.now(); count = 0; }
  if (count >= 40 || active >= 4) return json({ error: "길찾기 요청이 많아요. 잠시 후 다시 시도해 주세요." }, 429);
  count++; active++;
  try { return json(await fetchCourseDirections(body.mode, body.points, key, fetch, request.signal)); }
  catch { return json({ error: "길찾기 조회가 중단됐어요. 다시 시도해 주세요." }, 502); }
  finally { active--; }
}

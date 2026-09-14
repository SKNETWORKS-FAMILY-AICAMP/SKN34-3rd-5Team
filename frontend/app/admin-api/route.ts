import { checkSameOrigin, teamRequest } from "@/lib/team-backend";
import { ChatError, isRecord } from "@/lib/chat/validation";
export const runtime = "nodejs";
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
const failure = (error: unknown) => json({ error: error instanceof ChatError ? error.message : "관리자 서버에 연결하지 못했어요." }, error instanceof ChatError ? error.status : 502);
async function identity(master = false) {
  const user = await teamRequest("auth/user", undefined, true, undefined, "GET");
  if (!isRecord(user) || user.is_active !== true || user.is_staff !== true || (master && user.is_superuser !== true)) throw new ChatError("관리자 권한이 필요해요.", 403);
  return user;
}
export async function GET(request: Request) {
  try {
    const user = await identity();
    const params = new URL(request.url).searchParams;
    const page = Math.max(1, Math.min(1000000, Number(params.get("page")) || 1));
    const query = new URLSearchParams({ page: String(Math.floor(page)), q: (params.get("q") ?? "").slice(0, 150) });
    const members = await teamRequest(`auth/admin/members/?${query}`, undefined, true, request.signal, "GET");
    return json({ user, members });
  } catch (error) { return failure(error); }
}
export async function PATCH(request: Request) {
  try {
    checkSameOrigin(request);
    await identity(true);
    const raw = await request.text();
    if (raw.length > 1024) throw new ChatError("요청이 너무 길어요.");
    let body: unknown;
    try { body = JSON.parse(raw); } catch { throw new ChatError("요청 형식을 확인해 주세요."); }
    if (!isRecord(body) || !Number.isSafeInteger(body.id) || Number(body.id) < 1 || typeof body.is_staff !== "boolean") throw new ChatError("회원과 권한을 확인해 주세요.");
    const result = await teamRequest(`auth/admin/members/${body.id}/role/`, { is_staff: body.is_staff }, true, request.signal, "PATCH");
    return json(result);
  } catch (error) { return failure(error); }
}

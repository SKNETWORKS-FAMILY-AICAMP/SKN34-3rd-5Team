import { cookies } from "next/headers";
import { checkSameOrigin, clearTokens, teamRequest } from "@/lib/team-backend";
import { ChatError, isRecord } from "@/lib/chat/validation";

export const runtime = "nodejs";
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
const failure = (error: unknown) => json({ error: error instanceof ChatError ? error.message : "회원 요청을 처리하지 못했어요.", ...(error instanceof ChatError && error.fields ? { fields: error.fields } : {}) }, error instanceof ChatError ? error.status : 502);

async function body(request: Request, limit = 8192) {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new ChatError("JSON 형식으로 보내 주세요.", 415);
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > limit) throw new ChatError("입력한 정보가 너무 길어요.", 413);
  let value: unknown;
  try { value = JSON.parse(raw); } catch { throw new ChatError("입력 형식을 확인해 주세요."); }
  if (!isRecord(value)) throw new ChatError("객체 형태로 입력해 주세요.");
  return value;
}

function pick(value: Record<string, unknown>, fields: string[]) {
  return Object.fromEntries(fields.filter(field => field in value).map(field => [field, value[field]]));
}

export async function GET(request: Request, context: RouteContext<"/team-auth/[...action]">) {
  try {
    const { action } = await context.params;
    if (action.join("/") !== "user") return new Response(null, { status: 404 });
    return json(await teamRequest("auth/user", undefined, true, request.signal, "GET"));
  } catch (error) { return failure(error); }
}

export async function PATCH(request: Request, context: RouteContext<"/team-auth/[...action]">) {
  try {
    checkSameOrigin(request);
    const { action } = await context.params;
    if (action.join("/") !== "user") return new Response(null, { status: 404 });
    const value = await body(request, 700000);
    const allowed = pick(value, ["first_name", "birth_date", "gender", "nickname", "team_code", "avatar", "notifications", "visibility"]);
    if (Object.keys(allowed).length !== Object.keys(value).length) throw new ChatError("변경할 수 없는 회원 정보가 포함됐어요.");
    return json(await teamRequest("auth/user", allowed, true, request.signal, "PATCH"));
  } catch (error) { return failure(error); }
}

export async function POST(request: Request, context: RouteContext<"/team-auth/[...action]">) {
  let action = "";
  try {
    checkSameOrigin(request);
    action = (await context.params).action.join("/");
    const value = await body(request);
    if (action === "signup") {
      const allowed = pick(value, ["username", "email", "password", "passwordConfirm", "first_name", "birth_date", "gender"]);
      if (Object.keys(allowed).length !== Object.keys(value).length) throw new ChatError("회원가입 입력을 확인해 주세요.");
      const { passwordConfirm, ...rest } = allowed;
      const payload = { ...rest, re_password: passwordConfirm };
      await teamRequest("auth/signup/", payload, false, request.signal);
      return json({ ok: true }, 201);
    }
    if (action === "username/request" || action === "password/request") {
      if (typeof value.email !== "string" || Object.keys(value).length !== 1) throw new ChatError("이메일 주소를 확인해 주세요.");
      await teamRequest(`auth/${action}`, { email: value.email }, false, request.signal);
      return json({ ok: true });
    }
    if (action === "email/request" || action === "email/verify") {
      const allowed = action.endsWith("request") ? pick(value, ["email"]) : pick(value, ["request_id", "code"]);
      if (Object.keys(allowed).length !== Object.keys(value).length) throw new ChatError("이메일 인증 입력을 확인해 주세요.");
      return json(await teamRequest(`auth/${action}`, allowed, true, request.signal));
    }
    if (action === "password" || action === "password/reset") {
      const fields = action === "password" ? ["current_password", "new_password", "new_password_confirm"] : ["uid", "token", "new_password", "new_password_confirm"];
      const allowed = pick(value, fields);
      if (Object.keys(allowed).length !== Object.keys(value).length) throw new ChatError("비밀번호 입력을 확인해 주세요.");
      await teamRequest("auth/password", allowed, !action.endsWith("reset"), request.signal);
      await clearTokens();
      return json({ ok: true });
    }
    if (action === "logout") {
      if (Object.keys(value).length) throw new ChatError("로그아웃 요청을 확인해 주세요.");
      const refresh = (await cookies()).get("kbo_refresh")?.value;
      let warning = "";
      try { if (refresh) await teamRequest("auth/logout", { refresh }, false, request.signal); }
      catch (error) { if (!(error instanceof ChatError) || ![400, 401].includes(error.status)) warning = "서버의 토큰 폐기 여부를 확인하지 못했어요."; }
      await clearTokens();
      return json({ ok: true, ...(warning ? { warning } : {}) }, warning ? 502 : 200);
    }
    return new Response(null, { status: 404 });
  } catch (error) {
    if (action === "logout") await clearTokens();
    return failure(error);
  }
}

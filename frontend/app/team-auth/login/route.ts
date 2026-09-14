import { verifyPreviewPassword } from "@/lib/preview-credentials";
import { checkSameOrigin, saveTokens, teamRequest } from "@/lib/team-backend";
import { ChatError, isRecord } from "@/lib/chat/validation";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    checkSameOrigin(request);
    const raw = await request.text();
    if (raw.length > 4096) throw new ChatError("입력한 정보가 너무 길어요.");
    let data: unknown;
    try { data = JSON.parse(raw); } catch { throw new ChatError("로그인 정보를 확인해 주세요."); }
    if (!isRecord(data) || typeof data.username !== "string" || !data.username.trim() || typeof data.password !== "string" || !data.password) throw new ChatError("아이디와 비밀번호를 입력해 주세요.");
    // Development fixture only; never issue backend tokens or grant server permissions.
    const previewUsername = process.env.MEMBER_PREVIEW_USERNAME;
    if (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_MEMBER_PREVIEW === "true" && previewUsername && data.username.trim() === previewUsername) {
      if (!await verifyPreviewPassword(data.password)) {
        throw new ChatError("아이디 또는 비밀번호를 확인해 주세요.", 401);
      }
      return Response.json({ ok: true, mode: "preview" }, { headers: { "Cache-Control": "no-store" } });
    }
    const tokens = await teamRequest("auth/signin", { username: data.username.trim(), password: data.password }, false);
    if (!isRecord(tokens) || typeof tokens.access !== "string" || typeof tokens.refresh !== "string") throw new ChatError("로그인 응답을 확인하지 못했어요.", 502);
    await saveTokens(tokens.access, tokens.refresh, true);
    return Response.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return Response.json({ error: error instanceof ChatError ? error.message : "로그인에 실패했어요." }, { status: error instanceof ChatError ? error.status : 502, headers: { "Cache-Control": "no-store" } });
  }
}

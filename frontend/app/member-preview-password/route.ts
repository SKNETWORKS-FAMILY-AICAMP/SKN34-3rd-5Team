import { checkSameOrigin } from "@/lib/team-backend";
import { ChatError, isRecord } from "@/lib/chat/validation";
import { changePreviewPassword, previewCredentialsEnabled, verifyPreviewPassword } from "@/lib/preview-credentials";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    checkSameOrigin(request);
    if (!previewCredentialsEnabled()) return new Response(null, { status: 404 });
    const text = await request.text();
    if (text.length > 4096) throw new ChatError("입력한 정보가 너무 길어요.");
    let body: unknown;
    try { body = JSON.parse(text); } catch { throw new ChatError("입력을 확인해 주세요."); }
    if (!isRecord(body) || typeof body.currentPassword !== "string" || typeof body.newPassword !== "string" || body.newPassword.length < 8 || body.newPassword.length > 128 || !/[A-Za-z]/.test(body.newPassword) || !/\d/.test(body.newPassword) || !/[^A-Za-z0-9\s]/.test(body.newPassword) || /\s/.test(body.newPassword)) throw new ChatError("새 비밀번호는 영문·숫자·특수문자를 포함한 8~128자여야 해요.");
    if (!await verifyPreviewPassword(body.currentPassword)) throw new ChatError("현재 비밀번호가 맞지 않아요.", 401);
    if (body.currentPassword === body.newPassword) throw new ChatError("현재 비밀번호와 다른 비밀번호를 입력해 주세요.");
    await changePreviewPassword(body.newPassword);
    return Response.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return Response.json({ error: error instanceof ChatError ? error.message : "비밀번호를 변경하지 못했어요." }, { status: error instanceof ChatError ? error.status : 500, headers: { "Cache-Control": "no-store" } });
  }
}

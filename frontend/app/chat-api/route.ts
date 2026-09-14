import { teamRequest, checkSameOrigin } from "@/lib/team-backend";
import { createTeamReply } from "@/lib/chat/team";
import { createChatReply, getChatStatus } from "@/lib/chat/server";
import { ChatError, parseChatRequest } from "@/lib/chat/validation";
import { MAX_REQUEST_BYTES } from "@/lib/chat/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Local prototype guard. A shared authenticated quota belongs in the team backend.
let windowStartedAt = 0;
let requestsInWindow = 0;
let activeRequests = 0;

function reserveRequest() {
  const now = Date.now();
  if (now - windowStartedAt >= 60000) { windowStartedAt = now; requestsInWindow = 0; }
  if (requestsInWindow >= 20 || activeRequests >= 3) throw new ChatError("잠시 후 다시 질문해 주세요. 요청을 차례로 처리하고 있어요.", 429);
  requestsInWindow += 1;
  activeRequests += 1;
}

function json(value: unknown, status = 200) {
  return Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
}

function failure(error: unknown) {
  return error instanceof ChatError
    ? json({ error: error.message }, error.status)
    : json({ error: "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요." }, 500);
}

export function GET() {
  try { return json(getChatStatus()); } catch (error) { return failure(error); }
}

export async function POST(request: Request) {
  let reserved = false;
  try {
    checkSameOrigin(request);
    const origin = request.headers.get("origin");
    if (origin && new URL(origin).host !== request.headers.get("host")) throw new ChatError("같은 사이트에서 질문을 보내 주세요.", 403);
    if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new ChatError("JSON 형식으로 질문을 보내 주세요.", 415);
    const size = Number(request.headers.get("content-length"));
    if (size > MAX_REQUEST_BYTES) throw new ChatError("대화 내용이 너무 길어요. 새 대화를 시작해 주세요.", 413);
    const body = await request.text();
    if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) throw new ChatError("대화 내용이 너무 길어요. 새 대화를 시작해 주세요.", 413);
    let value: unknown;
    try { value = JSON.parse(body); } catch { throw new ChatError("질문 형식을 확인해 주세요."); }
    const input = parseChatRequest(value);
    if (getChatStatus().provider !== "demo") { reserveRequest(); reserved = true; }
    if (getChatStatus().provider === "backend") return json(await createTeamReply(input, (path, body) => teamRequest(path, body, true, request.signal)));
    return json(await createChatReply(input, { signal: request.signal }));
  } catch (error) {
    return failure(error);
  } finally {
    if (reserved) activeRequests -= 1;
  }
}

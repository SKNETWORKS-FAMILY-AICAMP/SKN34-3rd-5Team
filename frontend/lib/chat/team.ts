import type { ChatRequest, ChatReply } from "./types";
import { ChatError, isRecord } from "./validation";

type Requester = (path: string, body: unknown) => Promise<unknown>;
export async function createTeamReply(request: ChatRequest, send: Requester): Promise<ChatReply> {
  const question = request.messages.at(-1)!.content;
  let sessionId = request.sessionId;
  if (!sessionId) {
    const room = await send("chat/sessions/", { title: question.slice(0, 80) });
    if (!isRecord(room) || !Number.isSafeInteger(room.id) || Number(room.id) < 1) throw new ChatError("채팅방 생성 응답을 확인하지 못했어요.", 502);
    sessionId = room.id as number;
  }
  const context = request.context?.stadium ? `[선택한 구장: ${request.context.stadium}]\n` : "";
  const result = await send(`chat/sessions/${sessionId}/messages/`, { content: context + question });
  if (!isRecord(result) || typeof result.assistant_message !== "string" || !result.assistant_message.trim()) throw new ChatError("팀 챗봇의 답변을 확인하지 못했어요.", 502);
  return { provider: "backend", model: "팀 챗봇", ready: true, sessionId, reply: result.assistant_message };
}

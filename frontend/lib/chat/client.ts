import { memberError, memberFetch } from "../member-auth-request";
import { isRecord, parseChatRequest } from "./validation";
import type { ChatReply, ChatRequest, ChatStatus } from "./types";
import { MAX_REPLY_LENGTH } from "./types";

const REQUEST_TIMEOUT_MS = 55_000;
const MEMBER_STATUS: ChatStatus = { provider: "backend", model: "팀 챗봇", ready: true };
export const GUEST_STATUS: ChatStatus = { provider: "guest", model: "팀 챗봇", ready: true };

export type ChatCheckpoint = { turnId: string; receipt: string; prefix: string };
export type ChatStreamCallbacks = {
  onDelta?: (answer: string, checkpoint?: ChatCheckpoint) => void;
  onCheckpoint?: (checkpoint: ChatCheckpoint) => void;
  getStop?: () => ChatCheckpoint | null;
  isCurrent?: () => boolean;
  finalizeSignal?: AbortSignal;
};

export class ChatClientError extends Error {
  constructor(message: string, public status: number, public uncertain = false, public sessionId?: number) { super(message); }
}

function fallback(status: number) {
  if (status === 401) return "팀 계정 로그인을 확인해 주세요.";
  if (status === 403) return "이 대화를 이용할 권한이 없어요.";
  if (status === 404) return "채팅방을 찾지 못했어요. 새 대화를 시작해 주세요.";
  if (status === 409) return "더 최신 대화가 있어 이 답변을 저장하지 못했어요.";
  if (status === 429) return "요청이 많아요. 잠시 후 다시 시도해 주세요.";
  if (status >= 500) return "챗봇 서버에서 요청을 처리하지 못했어요.";
  return "입력 내용을 확인해 주세요.";
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function request<T>(
  path: string,
  init: RequestInit,
  signal: AbortSignal | undefined,
  fetcher: (path: string, init: RequestInit) => Promise<Response>,
  read: (response: Response) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, REQUEST_TIMEOUT_MS);
  const mutating = init.method !== "GET";
  try {
    const response = await fetcher(path, { ...init, cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      const data = await readJson(response).catch(() => null);
      throw new ChatClientError(
        response.status >= 500 ? fallback(response.status) : memberError(data, fallback(response.status)),
        response.status,
        response.status >= 500 && mutating,
      );
    }
    return await read(response);
  } catch (error) {
    if (error instanceof ChatClientError) throw error;
    if (error instanceof SyntaxError) throw new ChatClientError("응답을 읽지 못했어요.", 502, mutating);
    if (timedOut) throw new ChatClientError("응답 시간이 지났지만 서버 처리 여부는 확인할 수 없어요.", 504, mutating);
    if (controller.signal.aborted) throw new ChatClientError("요청이 중단됐어요.", 499, mutating);
    throw new ChatClientError("연결이 끊겨 서버 처리 여부를 확인할 수 없어요.", 502, mutating);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

const memberRequest = <T>(path: string, init: RequestInit, signal: AbortSignal | undefined, read: (response: Response) => Promise<T>) =>
  request(path, init, signal, memberFetch, read);
const guestRequest = <T>(path: string, init: RequestInit, signal: AbortSignal | undefined, read: (response: Response) => Promise<T>) =>
  request(path, init, signal, fetch, read);

function parseCheckpoint(value: Record<string, unknown>, prefix: string, turnId?: string): ChatCheckpoint {
  if (typeof value.turn_id !== "string" || !value.turn_id || typeof value.receipt !== "string" || !value.receipt || (turnId && value.turn_id !== turnId)) {
    throw new ChatClientError("체크포인트 형식이 올바르지 않아요.", 502, true);
  }
  return { turnId: value.turn_id, receipt: value.receipt, prefix };
}

async function finalizeMemberTurn(sessionId: number, checkpoint: ChatCheckpoint, status: "completed" | "stopped", callbacks: ChatStreamCallbacks) {
  if (callbacks.isCurrent && !callbacks.isCurrent()) throw new ChatClientError("계정이 변경되어 저장을 중단했어요.", 409);
  const value = await memberRequest(`/api/chat/turns/${checkpoint.turnId}/finalize/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ receipt: checkpoint.receipt, prefix: checkpoint.prefix, status }),
  }, callbacks.finalizeSignal, readJson);
  if (!isRecord(value) || value.turn_id !== checkpoint.turnId || value.session_id !== sessionId ||
      (value.status !== "completed" && value.status !== "stopped") || typeof value.user_message_id !== "number" ||
      (value.assistant_message_id !== null && typeof value.assistant_message_id !== "number") ||
      typeof value.assistant_message !== "string") {
    throw new ChatClientError("저장 확인 응답이 올바르지 않아요.", 502, true, sessionId);
  }
  return {
    ...MEMBER_STATUS,
    sessionId,
    reply: value.assistant_message,
    completionStatus: value.status,
    turnId: checkpoint.turnId,
    userMessageId: value.user_message_id,
    assistantMessageId: value.assistant_message_id,
  } satisfies ChatReply;
}

async function readMemberStream(response: Response, sessionId: number, callbacks: ChatStreamCallbacks): Promise<ChatReply> {
  if (!response.body || !response.headers.get("Content-Type")?.toLowerCase().startsWith("text/event-stream")) {
    throw new ChatClientError("스트림 응답을 확인하지 못했어요.", 502, true, sessionId);
  }
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = "", answer = "", checkpoint: ChatCheckpoint | null = null, done = false;
  const consume = (frame: string) => {
    const [eventLine, ...lines] = frame.split(/\r?\n/);
    const event = eventLine?.startsWith("event:") ? eventLine.slice(6).trim() : "";
    const raw = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new ChatClientError("스트림 응답 형식이 올바르지 않아요.", 502, true, sessionId); }
    if (!isRecord(value) || done) throw new ChatClientError("스트림 응답 순서가 올바르지 않아요.", 502, true, sessionId);
    if (event === "checkpoint") {
      if (checkpoint) throw new ChatClientError("체크포인트 순서가 올바르지 않아요.", 502, true, sessionId);
      checkpoint = parseCheckpoint(value, "");
      callbacks.onCheckpoint?.(checkpoint);
      return;
    }
    if (event === "delta") {
      if (!checkpoint || typeof value.text !== "string" || !value.text || answer.length + value.text.length > MAX_REPLY_LENGTH) {
        throw new ChatClientError("답변이 비어 있거나 너무 길어요.", 502, true, sessionId);
      }
      answer += value.text;
      checkpoint = parseCheckpoint(value, answer, checkpoint.turnId);
      callbacks.onCheckpoint?.(checkpoint);
      callbacks.onDelta?.(answer, checkpoint);
      return;
    }
    if (event === "error") {
      const detail = typeof value.detail === "string" && value.detail.length <= 200 ? value.detail : fallback(502);
      throw new ChatClientError(detail, 502, false, sessionId);
    }
    if (event === "done") {
      if (!checkpoint || !answer.trim()) throw new ChatClientError("최종 답변을 확인하지 못했어요.", 502, true, sessionId);
      checkpoint = parseCheckpoint(value, answer, checkpoint.turnId);
      callbacks.onCheckpoint?.(checkpoint);
      done = true;
      return;
    }
    throw new ChatClientError("알 수 없는 스트림 응답을 받았어요.", 502, true, sessionId);
  };

  try {
    while (!done) {
      const next = await reader.read();
      buffer += decoder.decode(next.value, { stream: !next.done });
      let boundary;
      while ((boundary = buffer.search(/\r?\n\r?\n/)) >= 0) {
        const frame = buffer.slice(0, boundary), separator = buffer.slice(boundary).startsWith("\r\n\r\n") ? 4 : 2;
        buffer = buffer.slice(boundary + separator);
        if (frame.trim()) consume(frame);
      }
      if (buffer.length > MAX_REPLY_LENGTH * 4) throw new ChatClientError("스트림 응답이 너무 길어요.", 502, true, sessionId);
      if (next.done) break;
    }
    if (!done || buffer.trim() || !checkpoint) throw new ChatClientError("답변 완료를 확인하지 못했어요.", 502, true, sessionId);
    const stopped = callbacks.getStop?.();
    let result = await finalizeMemberTurn(sessionId, stopped ?? checkpoint, stopped ? "stopped" : "completed", callbacks);
    const racedStop = callbacks.getStop?.();
    if (result.completionStatus === "completed" && racedStop) result = await finalizeMemberTurn(sessionId, racedStop, "stopped", callbacks);
    return result;
  } catch (error) {
    const stopped = callbacks.getStop?.();
    if (stopped) return finalizeMemberTurn(sessionId, stopped, "stopped", callbacks);
    throw error;
  } finally { await reader.cancel().catch(() => undefined); }
}

async function readGuestStream(response: Response, callbacks: ChatStreamCallbacks): Promise<ChatReply> {
  if (!response.body || !response.headers.get("Content-Type")?.toLowerCase().startsWith("text/event-stream")) {
    throw new ChatClientError("스트림 응답을 확인하지 못했어요.", 502);
  }
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = "", answer = "", done = false;
  callbacks.onCheckpoint?.({ turnId: "guest", receipt: "", prefix: "" });
  const consume = (frame: string) => {
    const [eventLine, ...lines] = frame.split(/\r?\n/), event = eventLine?.slice(6).trim();
    const raw = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new ChatClientError("스트림 응답 형식이 올바르지 않아요.", 502); }
    if (!isRecord(value) || done) throw new ChatClientError("스트림 응답 순서가 올바르지 않아요.", 502);
    if (event === "delta") {
      if (typeof value.text !== "string" || !value.text || answer.length + value.text.length > MAX_REPLY_LENGTH) throw new ChatClientError("답변이 너무 길어요.", 502);
      answer += value.text;
      callbacks.onCheckpoint?.({ turnId: "guest", receipt: "", prefix: answer });
      callbacks.onDelta?.(answer);
      return;
    }
    if (event === "done") {
      if (!answer.trim() || value.assistant_message !== answer) throw new ChatClientError("최종 답변을 확인하지 못했어요.", 502);
      done = true; return;
    }
    if (event === "error") throw new ChatClientError(typeof value.detail === "string" && value.detail.length <= 200 ? value.detail : fallback(502), 502);
    throw new ChatClientError("알 수 없는 스트림 응답을 받았어요.", 502);
  };
  try {
    while (!done) {
      const next = await reader.read();
      buffer += decoder.decode(next.value, { stream: !next.done });
      let boundary;
      while ((boundary = buffer.search(/\r?\n\r?\n/)) >= 0) {
        const frame = buffer.slice(0, boundary), separator = buffer.slice(boundary).startsWith("\r\n\r\n") ? 4 : 2;
        buffer = buffer.slice(boundary + separator); if (frame.trim()) consume(frame);
      }
      if (buffer.length > MAX_REPLY_LENGTH * 4) throw new ChatClientError("스트림 응답이 너무 길어요.", 502);
      if (next.done) break;
    }
    if (!done || buffer.trim()) throw new ChatClientError("답변 완료를 확인하지 못했어요.", 502);
    const stop = callbacks.getStop?.();
    return { ...GUEST_STATUS, reply: stop ? (stop.prefix.trim() ? stop.prefix : "") : answer, completionStatus: stop ? "stopped" : "completed" };
  } catch (error) {
    const stop = callbacks.getStop?.();
    if (stop) return { ...GUEST_STATUS, reply: stop.prefix.trim() ? stop.prefix : "", completionStatus: "stopped" };
    throw error;
  } finally { await reader.cancel().catch(() => undefined); }
}

export async function getChatStatus(signal?: AbortSignal): Promise<ChatStatus> {
  const sessions = await memberRequest("/api/chat/sessions/", { method: "GET" }, signal, readJson);
  if (!Array.isArray(sessions)) throw new ChatClientError("채팅방 목록 응답을 확인하지 못했어요.", 502);
  return MEMBER_STATUS;
}

export async function sendChatMessage(body: ChatRequest, signal?: AbortSignal, callbacks: ChatStreamCallbacks = {}): Promise<ChatReply> {
  const input = parseChatRequest(body), question = input.messages.at(-1)!.content;
  let sessionId = input.sessionId;
  if (!sessionId) {
    const room = await memberRequest("/api/chat/sessions/", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: question.slice(0, 80) }),
    }, signal, readJson);
    if (!isRecord(room) || !Number.isSafeInteger(room.id) || Number(room.id) < 1) throw new ChatClientError("채팅방 생성 응답을 확인하지 못했어요.", 502);
    sessionId = room.id as number;
  }
  const content = `${input.context?.stadium ? `[선택한 구장: ${input.context.stadium}]\n` : ""}${question}`;
  try {
    return await memberRequest(`/api/chat/sessions/${sessionId}/messages/`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ content }),
    }, signal, response => readMemberStream(response, sessionId!, callbacks));
  } catch (error) {
    if (error instanceof ChatClientError && error.sessionId === undefined) error.sessionId = sessionId;
    throw error;
  }
}

export async function sendGuestChatMessage(body: ChatRequest, signal?: AbortSignal, callbacks: ChatStreamCallbacks = {}): Promise<ChatReply> {
  const input = parseChatRequest(body);
  const messages = input.messages.map((message, index) => ({
    ...message,
    content: index === input.messages.length - 1 && input.context?.stadium
      ? `[선택한 구장: ${input.context.stadium}]\n${message.content}` : message.content,
  }));
  return guestRequest("/api/chat/guest/", {
    method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ messages }),
  }, signal, response => readGuestStream(response, callbacks));
}

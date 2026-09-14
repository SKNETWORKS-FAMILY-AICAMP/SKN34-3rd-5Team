import type { ChatReply, ChatRequest, ChatStatus } from "./types";

// The browser talks only to our server. Provider URLs and keys stay on the server.
const CHAT_ENDPOINT = "/chat-api";
const REQUEST_TIMEOUT_MS = 55_000;

async function request<T>(init: RequestInit, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(CHAT_ENDPOINT, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(typeof data?.error === "string" ? data.error : "대화 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
    if (!data || typeof data !== "object") throw new Error("응답을 읽지 못했어요. 다시 시도해 주세요.");
    return data as T;
  } catch (error) {
    if (timedOut) throw new Error("응답이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.");
    if (error instanceof TypeError) throw new Error("연결을 확인한 뒤 다시 시도해 주세요.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

export function getChatStatus(signal?: AbortSignal): Promise<ChatStatus> {
  return request<ChatStatus>({ method: "GET" }, signal);
}

export async function sendChatMessage(body: ChatRequest, signal?: AbortSignal): Promise<ChatReply> {
  const response = await request<ChatReply>({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }, signal);
  if (typeof response.reply !== "string" || !response.reply.trim()) {
    throw new Error("답변이 비어 있어요. 다시 시도해 주세요.");
  }
  return response;
}

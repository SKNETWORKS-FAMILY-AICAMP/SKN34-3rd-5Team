export type ChatMessage = { role: "user" | "assistant"; content: string };
export type ChatOrigin = { lat: number; lng: number };
// origin: 코스 작성 화면에서 지도에 찍은 출발지. 백엔드 코스 챗봇이 이 지점부터 이어서 코스를 짠다.
export type ChatContext = { stadium?: string; intent?: "route" | "baseball" | "stadium"; origin?: ChatOrigin };
export type ChatRequest = { messages: ChatMessage[]; sessionId?: number; context?: ChatContext };
export type ChatStatus = { provider: "demo" | "openai" | "backend" | "guest"; model: string; ready: boolean };
export type ChatReply = ChatStatus & ChatCourseMetadataDto & {
  reply: string;
  sessionId?: number;
  completionStatus?: "completed" | "stopped";
  turnId?: string;
  userMessageId?: number;
  assistantMessageId?: number | null;
};

export const MAX_MESSAGE_LENGTH = 2000;
export const MAX_HISTORY_MESSAGES = 12;
export const MAX_REPLY_LENGTH = 8000;
export const MAX_REQUEST_BYTES = 64000;
import type { ChatCourseMetadataDto } from "./wire";

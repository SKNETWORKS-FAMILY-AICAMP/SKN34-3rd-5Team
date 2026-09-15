export type ChatMessage = { role: "user" | "assistant"; content: string };
export type ChatContext = { stadium?: string; intent?: "route" | "baseball" | "stadium" };
export type ChatRequest = { messages: ChatMessage[]; sessionId?: number; context?: ChatContext };
export type ChatStatus = { provider: "demo" | "openai" | "backend" | "guest"; model: string; ready: boolean };
export type ChatReply = ChatStatus & {
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

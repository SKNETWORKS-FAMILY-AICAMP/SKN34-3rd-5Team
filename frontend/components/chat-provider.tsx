"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { ChatContext, ChatMessage, ChatStatus } from "@/lib/chat/types";
import { MAX_HISTORY_MESSAGES, MAX_MESSAGE_LENGTH } from "@/lib/chat/types";
import { getChatStatus, sendChatMessage } from "@/lib/chat/client";
import { ChatPopup } from "./chat-popup";

type ConversationSnapshot = {
  messages: ChatMessage[];
  draft: string;
  context?: ChatContext;
  failed: string;
  failedContext?: ChatContext;
  error: string;
  notice: string;
};
type ChatControls = ConversationSnapshot & {
  openChat: (initialMessage?: string, context?: ChatContext) => void;
  onExpand: () => void;
  onMinimize: () => void;
  onClosePopup: () => void;
  status: ChatStatus | null;
  statusLoading: boolean;
  statusError: string;
  pending: string;
  conversations: { id: string; title: string }[];
  activeConversationId: string;
  onDraftChange: (value: string) => void;
  onRefreshStatus: () => void;
  onSend: () => void;
  onRetry: () => void;
  onCancel: () => void;
  onReset: () => void;
  onSuggestion: (text: string, intent: ChatContext["intent"]) => void;
  onSelectConversation: (id: string) => void;
  onContextChange: (context?: ChatContext) => void;
};
const ChatControlsContext = createContext<ChatControls | null>(null);

export function useChat() {
  const value = useContext(ChatControlsContext);
  if (!value) throw new Error("useChat must be used inside ChatProvider");
  return value;
}

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isChatPage = pathname === "/chat";
  const hasEmbeddedChat = pathname === "/routes/new";
  const [popupRequested, setPopupRequested] = useState(false);
  const popupOpen = popupRequested && !isChatPage && !hasEmbeddedChat;
  const [activeConversationId, setActiveConversationId] = useState("initial-chat");
  const [conversations, setConversations] = useState([{ id: "initial-chat", title: "새 대화" }]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [context, setContext] = useState<ChatContext | undefined>();
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState("");
  const [pending, setPending] = useState("");
  const [failed, setFailed] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const historyRef = useRef<ChatMessage[]>([]);
  const requestRef = useRef<AbortController | null>(null);
  const statusRequestRef = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);
  const pendingRef = useRef("");
  const failedContextRef = useRef<ChatContext | undefined>(undefined);
  const returnPageRef = useRef({ url: "/", scrollY: 0 });
  const restorePageRef = useRef(false);
  const popupOpenerRef = useRef<HTMLElement | null>(null);
  const topButtonRef = useRef<HTMLButtonElement>(null);
  // Root layout keeps conversations alive across client-side page navigation.
  const backendSessions = useRef(new Map<string, number>());
  const archivedConversations = useRef(new Map<string, ConversationSnapshot>());

  const loadStatus = useCallback((controller: AbortController) => {
    return getChatStatus(controller.signal).then(
      nextStatus => {
        if (!controller.signal.aborted) { setStatus(nextStatus); setStatusError(""); }
      },
      cause => {
        if (!controller.signal.aborted) {
          setStatus(null);
          setStatusError(cause instanceof Error ? cause.message : "연결 상태를 확인하지 못했어요.");
        }
      },
    ).finally(() => {
      if (!controller.signal.aborted) setStatusLoading(false);
    });
  }, []);

  const refreshStatus = useCallback(() => {
    statusRequestRef.current?.abort();
    const controller = new AbortController();
    statusRequestRef.current = controller;
    setStatusLoading(true);
    setStatusError("");
    void loadStatus(controller);
  }, [loadStatus]);

  const closePopup = useCallback(() => {
    setPopupRequested(false);
    requestAnimationFrame(() => {
      const opener = popupOpenerRef.current;
      if (opener?.isConnected) opener.focus({ preventScroll: true });
      else topButtonRef.current?.focus({ preventScroll: true });
    });
  }, []);

  const expandChat = useCallback(() => {
    setPopupRequested(false);
    if (!isChatPage) {
      returnPageRef.current = { url: `${window.location.pathname}${window.location.search}${window.location.hash}`, scrollY: window.scrollY };
      router.push("/chat");
    }
  }, [isChatPage, router]);

  const minimizeChat = useCallback(() => {
    // Returning to the embedded assistant must not leave a hidden popup request.
    const destination = isChatPage
      ? new URL(returnPageRef.current.url, window.location.origin).pathname
      : pathname;
    setPopupRequested(destination !== "/routes/new");
    popupOpenerRef.current = null;
    if (isChatPage) {
      restorePageRef.current = true;
      router.push(returnPageRef.current.url, { scroll: false });
    }
  }, [isChatPage, pathname, router]);

  const cancelRequest = useCallback(() => {
    requestVersion.current += 1;
    requestRef.current?.abort();
    requestRef.current = null;
    const cancelledQuestion = pendingRef.current;
    if (cancelledQuestion) setDraft(current => current.trim() ? current : cancelledQuestion);
    pendingRef.current = "";
    setPending("");
    setNotice("응답 요청을 취소했어요. 질문을 수정하거나 다시 보낼 수 있어요.");
  }, []);

  const archiveCurrentConversation = useCallback(() => {
    archivedConversations.current.set(activeConversationId, {
      messages: historyRef.current, draft, context, failed, failedContext: failedContextRef.current, error, notice,
    });
  }, [activeConversationId, context, draft, error, failed, notice]);

  const resetChat = useCallback(() => {
    if (requestRef.current) return;
    if (!historyRef.current.length && !draft.trim() && !failed) {
      setContext(undefined);
      setNotice("");
      return;
    }
    archiveCurrentConversation();
    const id = crypto.randomUUID();
    setActiveConversationId(id);
    setConversations(current => [{ id, title: "새 대화" }, ...current]);
    historyRef.current = [];
    failedContextRef.current = undefined;
    setMessages([]);
    setDraft("");
    setPending("");
    setFailed("");
    setError("");
    setNotice("");
    setContext(undefined);
  }, [archiveCurrentConversation, draft, failed]);

  const selectConversation = useCallback((id: string) => {
    if (requestRef.current || id === activeConversationId) return;
    const saved = archivedConversations.current.get(id);
    if (!saved) return;
    archiveCurrentConversation();
    setActiveConversationId(id);
    historyRef.current = saved.messages;
    failedContextRef.current = saved.failedContext;
    setMessages(saved.messages);
    setDraft(saved.draft);
    setContext(saved.context);
    setFailed(saved.failed);
    setError(saved.error);
    setNotice(saved.notice);
  }, [activeConversationId, archiveCurrentConversation]);

  const send = useCallback(async (text = draft, options?: { context?: ChatContext }) => {
    const selectedContext = options ? options.context : context;
    const content = text.trim();
    if (!content || requestRef.current || content.length > MAX_MESSAGE_LENGTH) return;
    const controller = new AbortController();
    const version = ++requestVersion.current;
    requestRef.current = controller;
    pendingRef.current = content;
    setPending(content);
    setDraft("");
    setError("");
    setNotice("");
    setFailed("");
    failedContextRef.current = undefined;
    const userMessage: ChatMessage = { role: "user", content };
    const previous = historyRef.current;
    if (previous.length === 0) {
      setConversations(current => current.map(item => item.id === activeConversationId
        ? { ...item, title: content.replace(/\s+/g, " ").slice(0, 48) }
        : item));
    }
    try {
      // Keep complete exchanges, leaving one slot for this question.
      const reply = await sendChatMessage({
        messages: [...previous.slice(-(MAX_HISTORY_MESSAGES - 2)), userMessage],
        context: selectedContext,
        sessionId: backendSessions.current.get(activeConversationId),
      }, controller.signal);
      if (reply.sessionId) backendSessions.current.set(activeConversationId, reply.sessionId);
      if (version !== requestVersion.current) return;
      const next: ChatMessage[] = [...previous, userMessage, { role: "assistant", content: reply.reply }];
      historyRef.current = next;
      setMessages(next);
      setStatus({ provider: reply.provider, model: reply.model, ready: reply.ready });
    } catch (cause) {
      if (version !== requestVersion.current || controller.signal.aborted) return;
      setFailed(content);
      failedContextRef.current = selectedContext;
      setDraft(current => current.trim() ? current : content);
      setError(cause instanceof Error ? cause.message : "답변을 가져오지 못했어요. 다시 시도해 주세요.");
    } finally {
      if (version === requestVersion.current) {
        requestRef.current = null;
        pendingRef.current = "";
        setPending("");
      }
    }
  }, [activeConversationId, context, draft]);

  const openChat = useCallback((initialMessage?: string, nextContext?: ChatContext) => {
    expandChat();
    if (nextContext) setContext(nextContext);
    if (requestRef.current) {
      if (initialMessage?.trim()) {
        setDraft(initialMessage.slice(0, MAX_MESSAGE_LENGTH));
        setNotice("지금 답변이 끝나면 아래에 준비한 질문을 보낼 수 있어요.");
      }
      return;
    }
    if (initialMessage?.trim()) void send(initialMessage.slice(0, MAX_MESSAGE_LENGTH), { context: nextContext ?? context });
  }, [context, expandChat, send]);

  useEffect(() => {
    if (isChatPage || !restorePageRef.current) return;
    restorePageRef.current = false;
    const frame = requestAnimationFrame(() => window.scrollTo({ top: returnPageRef.current.scrollY, behavior: "instant" }));
    return () => cancelAnimationFrame(frame);
  }, [isChatPage]);

  useEffect(() => {
    if (!isChatPage && !popupOpen && !hasEmbeddedChat) return;
    statusRequestRef.current?.abort();
    const controller = new AbortController();
    statusRequestRef.current = controller;
    void loadStatus(controller);
    return () => controller.abort();
  }, [hasEmbeddedChat, isChatPage, popupOpen, loadStatus]);

  useEffect(() => () => {
    requestVersion.current += 1;
    requestRef.current?.abort();
    statusRequestRef.current?.abort();
  }, []);

  return (
    <ChatControlsContext.Provider value={{
      openChat, onExpand: expandChat, onMinimize: minimizeChat, onClosePopup: closePopup,
      messages, draft, context, status, statusLoading, statusError,
      pending, failed, error, notice, conversations, activeConversationId,
      onDraftChange: setDraft, onRefreshStatus: () => void refreshStatus(),
      onSend: () => void send(), onRetry: () => void send(failed, { context: failedContextRef.current }),
      onCancel: cancelRequest, onReset: resetChat,
      onSuggestion: (text, intent) => { setDraft(text); setContext(current => ({ ...current, intent })); },
      onSelectConversation: selectConversation,
      onContextChange: setContext,
    }}>
      {children}
      {!popupOpen && <button ref={topButtonRef} type="button" className="scroll-to-top" aria-label="맨 위로 이동" title="맨 위로 이동" onClick={() => window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" })}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 11 6-6 6 6M12 5v14" /></svg>
      </button>}
      {popupOpen && <ChatPopup />}
    </ChatControlsContext.Provider>
  );
}

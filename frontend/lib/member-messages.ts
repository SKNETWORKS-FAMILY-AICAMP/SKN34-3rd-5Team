"use client";
import { useMemo, useSyncExternalStore } from "react";
import { MEMBER_PREVIEW_ENABLED } from "./member-preview";

export type MemberMessage = { id: string; sender: string; subject: string; body: string; createdAt: string; read: boolean };
const key = "kbo-member-inbox-v1", eventName = "kbo-member-inbox-change";
function read() { try { return MEMBER_PREVIEW_ENABLED ? localStorage.getItem(key) ?? "[]" : "[]"; } catch { return "[]"; } }
function parse(raw: string): MemberMessage[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.filter((m: MemberMessage) => m && typeof m.id === "string" && typeof m.sender === "string" && typeof m.subject === "string" && typeof m.body === "string" && typeof m.createdAt === "string" && Number.isFinite(Date.parse(m.createdAt)) && typeof m.read === "boolean") : [];
  } catch { return []; }
}
function subscribe(callback: () => void) {
  window.addEventListener(eventName, callback); window.addEventListener("storage", callback);
  return () => { window.removeEventListener(eventName, callback); window.removeEventListener("storage", callback); };
}
export function useMemberMessages() {
  const raw = useSyncExternalStore(subscribe, read, () => "[]");
  return useMemo(() => parse(raw), [raw]);
}
export function markMessageRead(id: string) {
  if (!MEMBER_PREVIEW_ENABLED) return;
  localStorage.setItem(key, JSON.stringify(parse(read()).map(m => m.id === id ? { ...m, read: true } : m)));
  window.dispatchEvent(new Event(eventName));
}

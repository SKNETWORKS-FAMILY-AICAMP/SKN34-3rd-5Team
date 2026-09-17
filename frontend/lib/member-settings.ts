"use client";
import { useMemo, useSyncExternalStore } from "react";
import { MEMBER_PREVIEW_ENABLED } from "./member-preview";
import { createClientId } from "./client-id";

export type NotificationKind = "comments" | "courses" | "announcements";
export type MemberNotice = { id: string; text: string; kind: NotificationKind; read: boolean; createdAt: string };
export type MemberSettings = {
  email: string;
  notifications: Record<NotificationKind, boolean>;
  visibility: { courses: boolean; posts: boolean; likes: boolean };
  notices: MemberNotice[];
};
const defaults: MemberSettings = { email: "", notifications: { comments: true, courses: true, announcements: true }, visibility: { courses: false, posts: false, likes: false }, notices: [] };
const key = "kbo-member-settings-v1", eventName = "kbo-member-settings-change";
function read() { try { return localStorage.getItem(key) ?? ""; } catch { return ""; } }
function parse(raw: string): MemberSettings {
  try {
    const value = JSON.parse(raw);
    return {
      email: typeof value.email === "string" ? value.email : "",
      notifications: { comments: value.notifications?.comments !== false, courses: value.notifications?.courses !== false, announcements: value.notifications?.announcements !== false },
      visibility: { courses: value.visibility?.courses === true, posts: value.visibility?.posts === true, likes: value.visibility?.likes === true },
      notices: Array.isArray(value.notices) ? value.notices.filter((n: MemberNotice) => n && typeof n.id === "string" && typeof n.text === "string" && typeof n.read === "boolean" && ["comments", "courses", "announcements"].includes(n.kind)).slice(0, 100) : [],
    };
  } catch { return defaults; }
}
function write(settings: MemberSettings) {
  if (!MEMBER_PREVIEW_ENABLED) throw new Error("개발용 회원 설정을 사용할 수 없어요.");
  localStorage.setItem(key, JSON.stringify(settings)); window.dispatchEvent(new Event(eventName));
}
function subscribe(callback: () => void) {
  window.addEventListener(eventName, callback); window.addEventListener("storage", callback);
  return () => { window.removeEventListener(eventName, callback); window.removeEventListener("storage", callback); };
}
export function useMemberSettings() {
  const raw = useSyncExternalStore(subscribe, read, () => "");
  return useMemo(() => parse(raw), [raw]);
}
export function saveMemberSettings(settings: Omit<MemberSettings, "notices">) {
  if (settings.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(settings.email)) throw new Error("이메일 주소를 확인해 주세요.");
  write({ ...settings, notices: parse(read()).notices });
}
// Connect real backend events here later; do not generate fake unread counts.
export function addMemberNotice(kind: NotificationKind, text: string) {
  const state = parse(read());
  if (!state.notifications[kind]) return;
  write({ ...state, notices: [{ id: createClientId(), text, kind, read: false, createdAt: new Date().toISOString() }, ...state.notices].slice(0, 100) });
}
export function markNoticesRead(id?: string) {
  const state = parse(read());
  write({ ...state, notices: state.notices.map(notice => !id || notice.id === id ? { ...notice, read: true } : notice) });
}

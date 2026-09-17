"use client";

import { useMemo, useSyncExternalStore } from "react";
import { nicknameChangeTimestamp, memberLevelForPoints, type MemberLevel } from "./member-policy";
import { teamBoards } from "./team-community";

// UI fixtures only. Never use this state to authorize server requests.
export const MEMBER_PREVIEW_ENABLED = process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_MEMBER_PREVIEW === "true";
const KEY = "kbo-member-preview-v1";
const EVENT = "kbo-member-preview-change";
const DEFAULT = JSON.stringify({ signedIn: false, nickname: "직관팬", teamCode: "" });
export type PreviewMember = { id: "preview-member"; nickname: string; teamCode: string; avatar: string; level: MemberLevel; points: number; nicknameChangedAt: string | null; role: "member"; mode: "preview" };
function read() {
  if (!MEMBER_PREVIEW_ENABLED) return "";
  try { return localStorage.getItem(KEY) ?? DEFAULT; } catch { return DEFAULT; }
}
function parse(raw: string) {
  try {
    const value = JSON.parse(raw);
    return { points: Number.isSafeInteger(value.points) && value.points >= 0 ? value.points : 56, nicknameChangedAt: typeof value.nicknameChangedAt === "string" && Number.isFinite(Date.parse(value.nicknameChangedAt)) ? value.nicknameChangedAt : null, signedIn: value.signedIn === true, nickname: typeof value.nickname === "string" && value.nickname.trim() ? value.nickname.trim().slice(0, 20) : "직관팬", avatar: typeof value.avatar === "string" && value.avatar.length < 600000 && /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(value.avatar) ? value.avatar : "", teamCode: teamBoards.some(team => team.code === value.teamCode) ? value.teamCode : "" };
  } catch { return { signedIn: false, nickname: "직관팬", teamCode: "", avatar: "", points: 56, nicknameChangedAt: null }; }
}
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback); window.addEventListener("storage", callback);
  return () => { window.removeEventListener(EVENT, callback); window.removeEventListener("storage", callback); };
}
function write(value: ReturnType<typeof parse>) {
  if (!MEMBER_PREVIEW_ENABLED) throw new Error("회원 미리보기는 개발 환경에서만 사용할 수 있어요.");
  try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { throw new Error("브라우저에 저장하지 못했어요. 저장 공간 설정을 확인해 주세요."); }
  window.dispatchEvent(new Event(EVENT));
}
export function setPreviewSignedIn(signedIn: boolean) { write({ ...parse(read()), signedIn }); }
export function updatePreviewAvatar(avatar: string) {
  const state = parse(read());
  if (!state.signedIn) throw new Error("로그인 후 변경해 주세요.");
  if (avatar && (avatar.length >= 600000 || !/^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(avatar))) throw new Error("사진을 다시 선택해 주세요.");
  write({ ...state, avatar });
}
export function updatePreviewProfile(nickname: string, teamCode: string) {
  const state = parse(read());
  if (!state.signedIn) throw new Error("로그인 후 변경해 주세요.");
  if (!/^[A-Za-z가-힣]{1,12}$/.test(nickname.trim())) throw new Error("닉네임은 한글·영문만 1~12자로 입력해 주세요. 숫자·공백·특수문자는 사용할 수 없어요.");
  if (teamCode && !teamBoards.some(team => team.code === teamCode)) throw new Error("응원팀을 확인해 주세요.");
  const nicknameChangedAt = nicknameChangeTimestamp(state.nickname, nickname, state.nicknameChangedAt, new Date());
  write({ ...state, nickname: nickname.trim(), teamCode, nicknameChangedAt });
}
export function usePreviewMember() {
  const raw = useSyncExternalStore(subscribe, read, () => "");
  return useMemo<PreviewMember | null>(() => {
    if (!MEMBER_PREVIEW_ENABLED || !raw) return null;
    const state = parse(raw);
    return state.signedIn ? { id: "preview-member", nickname: state.nickname, teamCode: state.teamCode, avatar: state.avatar, level: memberLevelForPoints(state.points), points: state.points, nicknameChangedAt: state.nicknameChangedAt, role: "member", mode: "preview" } : null;
  }, [raw]);
}

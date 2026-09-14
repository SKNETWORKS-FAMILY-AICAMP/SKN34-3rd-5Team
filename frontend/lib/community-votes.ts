"use client";

import { useSyncExternalStore } from "react";

const key = "kbo-community-votes-v1";
const event = "community-votes-change";
type Vote = "up" | "down";
function snapshot() { try { return localStorage.getItem(key) ?? "{}"; } catch { return "{}"; } }
function parse(value: string): Record<string, Vote> {
  try {
    const data = JSON.parse(value);
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    return Object.fromEntries(Object.entries(data).filter(([, vote]) => vote === "up" || vote === "down")) as Record<string, Vote>;
  } catch { return {}; }
}
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback); window.addEventListener(event, callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener(event, callback); };
}
export function useCommunityVotes() {
  const votes = parse(useSyncExternalStore(subscribe, snapshot, () => "{}"));
  function toggle(id: string, vote: Vote) {
    const next = parse(snapshot());
    if (next[id] === vote) delete next[id]; else next[id] = vote;
    localStorage.setItem(key, JSON.stringify(next));
    window.dispatchEvent(new Event(event));
  }
  return { votes, toggle };
}

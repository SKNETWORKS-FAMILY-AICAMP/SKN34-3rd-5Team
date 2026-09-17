"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

const KEY = "kbo-route-numbers-v1";
const EVENT = "kbo-route-numbers-change";
const samples: Record<string, string> = {
  "jamsil-day": "000001", "gocheok-day": "000002", "incheon-day": "000003",
  "suwon-day": "000004", "daejeon-day": "000005", "daegu-day": "000006",
};
type Registry = { last: number; entries: Record<string, string> };

function parse(raw: string | null): Registry {
  if (!raw) return { last: 6, entries: {} };
  const value = JSON.parse(raw) as Registry;
  if (!value || !Number.isInteger(value.last) || value.last < 6 || value.last > 999999 || !value.entries || typeof value.entries !== "object" || Array.isArray(value.entries)) throw new Error("Invalid route number registry");
  const numbers = Object.values(value.entries);
  if (numbers.some(number => typeof number !== "string" || !/^\d{6}$/.test(number) || Number(number) <= 6 || Number(number) > value.last) || new Set(numbers).size !== numbers.length) throw new Error("Invalid route numbers");
  return value;
}

/** Local preview only. Locks serialize allocation across tabs; entries survive route deletion. */
export async function ensureLocalRouteNumber(id: string): Promise<string> {
  if (Object.hasOwn(samples, id)) return samples[id];
  if (!id || !navigator.locks) throw new Error("Route number allocation is unavailable");
  return navigator.locks.request(KEY, () => {
    const registry = parse(window.localStorage.getItem(KEY));
    if (Object.hasOwn(registry.entries, id)) return registry.entries[id];
    if (registry.last >= 999999) throw new Error("Route numbers exhausted");
    const number = String(registry.last + 1).padStart(6, "0");
    window.localStorage.setItem(KEY, JSON.stringify({ last: registry.last + 1, entries: { ...registry.entries, [id]: number } }));
    window.dispatchEvent(new Event(EVENT));
    return number;
  });
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener(EVENT, callback); };
}

export function useRouteNumber(id?: string, serverNumber?: string): string {
  const [failedId, setFailedId] = useState<string>();
  const raw = useSyncExternalStore(subscribe, () => {
    try { return window.localStorage.getItem(KEY) ?? ""; } catch { return ""; }
  }, () => "");
  const sampleNumber = id && Object.hasOwn(samples, id) ? samples[id] : undefined;
  let localNumber: string | undefined;
  try { const registry = parse(raw); if (id && Object.hasOwn(registry.entries, id)) localNumber = registry.entries[id]; } catch { /* Never rebuild a damaged registry and reuse numbers. */ }
  useEffect(() => {
    if (!id || serverNumber || sampleNumber || localNumber) return;
    let active = true;
    void ensureLocalRouteNumber(id).catch(() => { if (active) setFailedId(id); });
    return () => { active = false; };
  }, [id, serverNumber, sampleNumber, localNumber]);
  return serverNumber || sampleNumber || localNumber || (failedId === id ? "번호 확인 필요" : "번호 준비 중");
}

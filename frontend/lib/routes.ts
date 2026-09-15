"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { fetchCourses, persistCourse, removeCourse } from "./course-api";

export type RouteStop = { name: string; lat: number; lng: number; category: string; placeId?: string; visitId?: string; address?: string; tourContentId?: string; isMapPoint?: boolean; isDrawnPoint?: boolean };
export function areValidCoordinates(lat: unknown, lng: unknown): boolean {
  return typeof lat === "number" && typeof lng === "number" && Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}
export type TripRoute = {
  id: string; title: string; stadium: string; description: string; content: string;
  tags: string[]; duration: string; cover: string; stops: RouteStop[];
  author: string; likes: number; isSample: boolean; createdAt: string;
  views?: number; contentFormat?: "html";
  routeNumber?: string;
  start?: { lat: number; lng: number };
  owned?: boolean;
  legacy?: boolean;
  legacySourceId?: string;
  saveWarning?: string;
};

const LIKES_KEY = "kbo-trip-likes-v1";
const VIEWS_KEY = "kbo-trip-views-v1";
const ROUTES_KEY = "kbo-trip-routes-v1";
const viewedThisSession = new Set<string>();
const CHANGE_EVENT = "kbo-routes-change";
const EMPTY = "[]";
const EMPTY_ROUTES: TripRoute[] = [];

function readStorage(key: string): string {
  if (typeof window === "undefined") return EMPTY;
  try { return window.localStorage.getItem(key) || EMPTY; } catch { return EMPTY; }
}

function isRoute(value: unknown): value is TripRoute {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return ["id", "title", "stadium", "description", "content", "duration", "cover", "author", "createdAt"].every(key => typeof item[key] === "string")
    && typeof item.likes === "number" && Number.isFinite(item.likes) && typeof item.isSample === "boolean"
    && (item.views === undefined || (typeof item.views === "number" && Number.isFinite(item.views) && item.views >= 0))
    && (item.contentFormat === undefined || item.contentFormat === "html")
    && (item.owned === undefined || typeof item.owned === "boolean")
    && (item.legacy === undefined || typeof item.legacy === "boolean")
    && (item.legacySourceId === undefined || typeof item.legacySourceId === "string")
    && (item.saveWarning === undefined || typeof item.saveWarning === "string")
    && (item.start === undefined || (item.start !== null && typeof item.start === "object" && areValidCoordinates((item.start as Record<string, unknown>).lat, (item.start as Record<string, unknown>).lng)))
    && Array.isArray(item.tags) && item.tags.every(tag => typeof tag === "string")
    && Array.isArray(item.stops) && item.stops.every(stop => stop && typeof stop === "object" && typeof stop.name === "string" && typeof stop.category === "string" && (stop.placeId === undefined || typeof stop.placeId === "string") && (stop.visitId === undefined || typeof stop.visitId === "string") && (stop.address === undefined || typeof stop.address === "string") && (stop.tourContentId === undefined || typeof stop.tourContentId === "string") && (stop.isMapPoint === undefined || typeof stop.isMapPoint === "boolean") && (stop.isDrawnPoint === undefined || typeof stop.isDrawnPoint === "boolean") && areValidCoordinates(stop.lat, stop.lng));
}

function parseStoredRoutes(raw: string): TripRoute[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRoute).filter(route => !route.isSample).map(route => ({ ...route, owned: true, legacy: true }));
  } catch { return []; }
}

function removeStoredRoute(id: string): void {
  const parsed: unknown = JSON.parse(readStorage(ROUTES_KEY));
  if (!Array.isArray(parsed)) throw new Error("저장된 코스 정보를 확인해 주세요.");
  persist(ROUTES_KEY, parsed.filter(item => !item || typeof item !== "object" || (item as Record<string, unknown>).id !== id));
}

function subscribeStorage(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  return () => { window.removeEventListener("storage", callback); window.removeEventListener(CHANGE_EVENT, callback); };
}

function persist(key: string, value: unknown): void {
  if (typeof window === "undefined") throw new Error("브라우저에서 다시 시도해 주세요.");
  try { window.localStorage.setItem(key, JSON.stringify(value)); }
  catch { throw new Error("브라우저 저장 공간을 사용할 수 없어요. 저장 권한과 남은 공간을 확인해 주세요."); }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function getRoutes(): TripRoute[] {
  return routeSnapshot;
}

const routeListeners = new Set<() => void>();
const migratedLegacyIds = new Set<string>();
let serverRoutes: TripRoute[] = [];
let routeSnapshot = EMPTY_ROUTES;
let routesReady = false;
let routesError = "";
let refreshing: Promise<void> | undefined;
const legacyRoutes = () => parseStoredRoutes(readStorage(ROUTES_KEY)).filter(route => !migratedLegacyIds.has(route.id));
const publishRoutes = () => { routeSnapshot = [...serverRoutes, ...legacyRoutes()]; routeListeners.forEach(listener => listener()); };
const subscribeRoutes = (listener: () => void) => {
  routeListeners.add(listener);
  window.addEventListener("storage", publishRoutes);
  return () => { routeListeners.delete(listener); window.removeEventListener("storage", publishRoutes); };
};
function refreshRoutes() {
  if (!refreshing) {
    routesError = "";
    refreshing = fetchCourses().then(routes => { serverRoutes = routes; }).catch(() => { routesError = "코스 목록을 불러오지 못했어요."; }).finally(() => { routesReady = true; publishRoutes(); refreshing = undefined; });
    publishRoutes();
  }
  return refreshing;
}

export const retryRoutes = () => refreshRoutes();

export async function saveRoute(route: TripRoute): Promise<TripRoute> {
  if (!isRoute(route) || route.isSample) throw new Error("저장할 코스 정보를 다시 확인해 주세요.");
  const saved = await persistCourse(route);
  const published = route.legacy ? { ...saved, legacySourceId: route.id } : route.legacySourceId ? { ...saved, legacySourceId: route.legacySourceId } : saved;
  if (route.legacy) {
    migratedLegacyIds.add(route.id);
    try { removeStoredRoute(route.id); } catch {}
  }
  serverRoutes = [published, ...serverRoutes.filter(item => item.id !== published.id)];
  publishRoutes();
  return published;
}

export async function deleteRoute(id: string): Promise<void> {
  if (legacyRoutes().some(route => route.id === id)) {
    removeStoredRoute(id);
    migratedLegacyIds.add(id);
    publishRoutes();
    return;
  }
  await removeCourse(id);
  serverRoutes = serverRoutes.filter(route => route.id !== id);
  publishRoutes();
}

export function useRoutes(): TripRoute[] {
  useEffect(() => { void refreshRoutes(); }, []);
  return useSyncExternalStore(subscribeRoutes, () => routeSnapshot, () => EMPTY_ROUTES);
}

export function useRoutesReady(): boolean {
  useEffect(() => { void refreshRoutes(); }, []);
  return useSyncExternalStore(subscribeRoutes, () => routesReady, () => false);
}

export function useRoutesError(): string {
  useEffect(() => { void refreshRoutes(); }, []);
  return useSyncExternalStore(subscribeRoutes, () => routesError, () => "");
}

function parseViews(raw: string): Record<string, number> {
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([, count]) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0));
  } catch { return {}; }
}

export function useRouteViews(): Record<string, number> {
  const raw = useSyncExternalStore(subscribeStorage, () => readStorage(VIEWS_KEY), () => EMPTY);
  return useMemo(() => parseViews(raw), [raw]);
}

// These counts belong to this browser until the team's post API is connected.
export function recordRouteView(id: string): void {
  if (viewedThisSession.has(id)) return;
  const views = parseViews(readStorage(VIEWS_KEY));
  try {
    persist(VIEWS_KEY, { ...views, [id]: (views[id] ?? 0) + 1 });
    viewedThisSession.add(id);
  } catch { /* Viewing a route must still work if browser storage is unavailable. */ }
}

function parseLikes(raw: string): string[] {
  try { const result: unknown = JSON.parse(raw); return Array.isArray(result) ? result.filter(id => typeof id === "string") : []; }
  catch { return []; }
}

export function useLikedRoutes(): string[] {
  const raw = useSyncExternalStore(subscribeStorage, () => readStorage(LIKES_KEY), () => EMPTY);
  return useMemo(() => parseLikes(raw), [raw]);
}

export function toggleRouteLike(id: string): void {
  const likes = parseLikes(readStorage(LIKES_KEY));
  persist(LIKES_KEY, likes.includes(id) ? likes.filter(item => item !== id) : [...likes, id]);
}

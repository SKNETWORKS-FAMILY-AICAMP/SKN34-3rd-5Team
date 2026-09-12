"use client";

import { useMemo, useSyncExternalStore } from "react";

export type RouteStop = { name: string; lat: number; lng: number; category: string; placeId?: string; address?: string; tourContentId?: string; isMapPoint?: boolean; isDrawnPoint?: boolean };
export function areValidCoordinates(lat: unknown, lng: unknown): boolean {
  return typeof lat === "number" && typeof lng === "number" && Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}
export type TripRoute = {
  id: string; title: string; stadium: string; description: string; content: string;
  tags: string[]; duration: string; cover: string; stops: RouteStop[];
  author: string; likes: number; isSample: boolean; createdAt: string;
  views?: number; contentFormat?: "html";
  start?: { lat: number; lng: number };
};

export const sampleRoutes: TripRoute[] = [
  {
    id: "jamsil-day", title: "잠실에서 보내는 완벽한 야구 하루", stadium: "잠실야구장",
    description: "호수 산책부터 야구장의 함성까지, 여유롭게 즐기는 잠실 코스.",
    content: "경기 전에는 석촌호수를 가볍게 걸으며 하루를 시작해 보세요. 근처에서 식사한 뒤 여유 있게 구장으로 이동하는 코스예요.\n\n잠실야구장에서는 입장과 좌석 찾기에 충분한 시간을 남겨 두세요. 경기 후 일정은 종료 시간과 교통 상황에 맞춰 조정하면 좋아요.\n\n이 코스는 화면을 둘러보기 위한 예시입니다. 실제 방문 전 경기 일정과 각 장소의 운영 여부를 확인해 주세요.",
    tags: ["첫 직관", "산책", "친구와"], duration: "경기 전후 반나절", cover: "/images/stadium-night.jpg",
    stops: [{ name: "석촌호수", lat: 37.507, lng: 127.102, category: "산책" }, { name: "잠실야구장", lat: 37.5161987797456, lng: 127.075940589715, category: "경기 관람" }, { name: "잠실새내역", lat: 37.5117, lng: 127.0863, category: "경기 후 식사" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-01T09:00:00.000Z",
  },
  {
    id: "gocheok-day", title: "날씨 걱정 없이, 고척 돔 나들이", stadium: "고척스카이돔",
    description: "가볍게 만나고 신나게 응원하는, 처음 가도 편한 고척 코스.",
    content: "동양미래대학교 주변에서 친구들과 만나 식사하고, 고척스카이돔으로 이동해 보세요.\n\n돔 구장에서 경기를 즐긴 후에는 혼잡 상황을 보며 귀가 동선을 정해 보세요. 방문 날짜에 맞는 경기 시간과 운영 정보를 확인하는 것도 잊지 마세요.\n\n실제 이용 후기가 아닌 샘플 코스입니다.",
    tags: ["돔 구장", "첫 직관", "친구와"], duration: "경기 전후 반나절", cover: "/images/stadium-day.jpg",
    stops: [{ name: "동양미래대학교 앞", lat: 37.5001, lng: 126.8676, category: "식사" }, { name: "고척스카이돔", lat: 37.4982, lng: 126.8671, category: "경기 관람" }, { name: "구일역", lat: 37.4969, lng: 126.8708, category: "귀가" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-02T09:00:00.000Z",
  },
  {
    id: "incheon-day", title: "노을과 응원으로 채우는 인천 직관", stadium: "인천 SSG 랜더스필드",
    description: "문학에서 만나는 야구의 즐거움. 함께 걸으며 시작하는 하루.",
    content: "문학경기장역에서 만나 구장 주변을 둘러보며 직관을 시작해 보세요. 먹거리와 입장 동선을 미리 확인하면 더 여유롭게 경기를 즐길 수 있어요.\n\n경기 후에는 문학경기장역으로 돌아오는 단순한 동선으로 마무리해 보세요.\n\n경기 및 시설 운영 시간은 별도로 확인해야 하는 샘플 코스입니다.",
    tags: ["주말 나들이", "친구와", "응원"], duration: "경기 중심 반나절", cover: "/images/stadium-sunset.jpg",
    stops: [{ name: "문학경기장역", lat: 37.4345, lng: 126.6987, category: "만남" }, { name: "인천 SSG 랜더스필드", lat: 37.4350819826381, lng: 126.690759830613, category: "경기 관람" }, { name: "문학경기장역", lat: 37.4345, lng: 126.6987, category: "귀가" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-03T09:00:00.000Z",
  },
  {
    id: "suwon-day", title: "수원 산책에 야구 한 스푼", stadium: "수원 KT 위즈 파크",
    description: "수원의 풍경을 걷고, 야구장에서 하루의 하이라이트를 만나세요.",
    content: "장안공원에서 산책한 후 경기 시간에 맞춰 수원KT위즈파크로 이동하는 예시 코스예요.\n\n구장까지의 이동 수단과 시간을 확인하고, 식사와 입장 시간을 여유롭게 잡아 보세요. 경기 후에는 수원종합운동장 주변에서 귀가 동선을 확인해 주세요.\n\n실제 이용 후기가 아닌 샘플 코스입니다.",
    tags: ["산책", "주말 나들이"], duration: "경기 전후 반나절", cover: "/images/stadium-day.jpg",
    stops: [{ name: "장안공원", lat: 37.2888, lng: 127.0125, category: "산책" }, { name: "수원 KT 위즈 파크", lat: 37.2978428909635, lng: 127.011348102567, category: "경기 관람" }, { name: "수원종합운동장", lat: 37.2985, lng: 127.011, category: "귀가" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-04T09:00:00.000Z",
  },
  {
    id: "daejeon-day", title: "대전의 하루, 야구로 마무리", stadium: "대전 한화생명 볼파크",
    description: "도심 구경과 직관을 함께 담은 대전 나들이 코스.",
    content: "대전 중앙로 주변을 둘러본 뒤 구장으로 이동하는 하루를 계획해 보세요.\n\n식사와 이동 시간을 넉넉하게 잡고, 대전한화생명볼파크에서 응원의 즐거움을 느껴 보세요. 종료 후에는 교통편에 맞춰 일정을 마무리하면 좋아요.\n\n장소 영업 여부와 이동 시간을 방문 전에 확인해야 하는 샘플 코스입니다.",
    tags: ["도심 나들이", "첫 직관"], duration: "경기 전후 반나절", cover: "/images/stadium-sunset.jpg",
    stops: [{ name: "중앙로역", lat: 36.3287, lng: 127.4256, category: "도심 구경" }, { name: "대전 한화생명 볼파크", lat: 36.3173370007388, lng: 127.428013823451, category: "경기 관람" }, { name: "중앙로역", lat: 36.3287, lng: 127.4256, category: "귀가" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-05T09:00:00.000Z",
  },
  {
    id: "daegu-day", title: "라팍으로 떠나는 설레는 첫 직관", stadium: "대구 삼성 라이온즈 파크",
    description: "지하철에서 구장까지, 응원에 집중하는 간단한 하루.",
    content: "대공원역에서 만나 대구삼성라이온즈파크로 이동하는 간단한 코스예요.\n\n경기 전 구장 주변을 둘러보며 사진도 남기고, 입장 후에는 좌석 위치를 확인해 보세요. 종료 시간에 맞춰 대중교통 운행 정보를 확인하면 좋아요.\n\n실제 이용 후기가 아닌 샘플 코스입니다.",
    tags: ["첫 직관", "대중교통", "응원"], duration: "경기 중심 반나절", cover: "/images/stadium-night.jpg",
    stops: [{ name: "대공원역", lat: 35.8428, lng: 128.6798, category: "만남" }, { name: "대구 삼성 라이온즈 파크", lat: 35.8411289243023, lng: 128.681236372268, category: "경기 관람" }, { name: "대공원역", lat: 35.8428, lng: 128.6798, category: "귀가" }],
    author: "KBO 코스 에디터", likes: 0, isSample: true, createdAt: "2026-09-06T09:00:00.000Z",
  },
];

const ROUTES_KEY = "kbo-trip-routes-v1";
const LIKES_KEY = "kbo-trip-likes-v1";
const VIEWS_KEY = "kbo-trip-views-v1";
const viewedThisSession = new Set<string>();
const CHANGE_EVENT = "kbo-routes-change";
const EMPTY = "[]";

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
    && (item.start === undefined || (item.start !== null && typeof item.start === "object" && areValidCoordinates((item.start as Record<string, unknown>).lat, (item.start as Record<string, unknown>).lng)))
    && Array.isArray(item.tags) && item.tags.every(tag => typeof tag === "string")
    && Array.isArray(item.stops) && item.stops.every(stop => stop && typeof stop === "object" && typeof stop.name === "string" && typeof stop.category === "string" && (stop.placeId === undefined || typeof stop.placeId === "string") && (stop.address === undefined || typeof stop.address === "string") && (stop.tourContentId === undefined || typeof stop.tourContentId === "string") && (stop.isMapPoint === undefined || typeof stop.isMapPoint === "boolean") && (stop.isDrawnPoint === undefined || typeof stop.isDrawnPoint === "boolean") && areValidCoordinates(stop.lat, stop.lng));
}

function parseStoredRoutes(raw: string): TripRoute[] {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRoute).filter(route => !route.isSample && !sampleRoutes.some(sample => sample.id === route.id));
  } catch { return []; }
}

function subscribe(callback: () => void) {
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
  return [...parseStoredRoutes(readStorage(ROUTES_KEY)), ...sampleRoutes];
}

export function saveRoute(route: TripRoute): void {
  if (!isRoute(route) || route.isSample || sampleRoutes.some(sample => sample.id === route.id)) throw new Error("저장할 코스 정보를 다시 확인해 주세요.");
  const stored = parseStoredRoutes(readStorage(ROUTES_KEY));
  persist(ROUTES_KEY, [route, ...stored.filter(item => item.id !== route.id)]);
}

export function deleteRoute(id: string): void {
  persist(ROUTES_KEY, parseStoredRoutes(readStorage(ROUTES_KEY)).filter(route => route.id !== id));
}

export function useRoutes(): TripRoute[] {
  const raw = useSyncExternalStore(subscribe, () => readStorage(ROUTES_KEY), () => EMPTY);
  return useMemo(() => [...parseStoredRoutes(raw), ...sampleRoutes], [raw]);
}

const subscribeToHydration = () => () => {};
export function useRoutesReady(): boolean {
  return useSyncExternalStore(subscribeToHydration, () => true, () => false);
}

function parseViews(raw: string): Record<string, number> {
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([, count]) => typeof count === "number" && Number.isSafeInteger(count) && count >= 0));
  } catch { return {}; }
}

export function useRouteViews(): Record<string, number> {
  const raw = useSyncExternalStore(subscribe, () => readStorage(VIEWS_KEY), () => EMPTY);
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
  const raw = useSyncExternalStore(subscribe, () => readStorage(LIKES_KEY), () => EMPTY);
  return useMemo(() => parseLikes(raw), [raw]);
}

export function toggleRouteLike(id: string): void {
  const likes = parseLikes(readStorage(LIKES_KEY));
  persist(LIKES_KEY, likes.includes(id) ? likes.filter(item => item !== id) : [...likes, id]);
}

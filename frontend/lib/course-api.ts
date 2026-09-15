import type { RouteStop, TripRoute } from "./routes";

const TOKEN_PREFIX = "kbo-course-edit-token:";
const sessionTokens = new Map<string, string>();
const TOKEN_WARNING = "코스는 공개 저장됐지만 편집 권한을 브라우저에 저장하지 못했어요. 이 페이지를 새로고침하면 읽기 전용이 됩니다.";

type ApiStop = RouteStop & { position: number };
type ApiCourse = {
  id: string; title: string; stadium: string; content?: string; contentFormat?: "html";
  duration: string; tags: string[]; author: string; createdAt: string; updatedAt: string;
  sampleId?: string; description?: string; cover?: string; likes?: number; views?: number; isSample?: boolean;
  startLat?: number; startLng?: number; stops: ApiStop[]; editToken?: string;
};

function token(id: string) {
  if (sessionTokens.has(id)) return sessionTokens.get(id)!;
  try { return window.localStorage.getItem(`${TOKEN_PREFIX}${id}`) || ""; } catch { return ""; }
}

function rememberToken(id: string, value: string) {
  sessionTokens.set(id, value);
  try { window.localStorage.setItem(`${TOKEN_PREFIX}${id}`, value); return ""; }
  catch { return TOKEN_WARNING; }
}

function routeFromApi(value: ApiCourse, owned = Boolean(token(value.id)), saveWarning = ""): TripRoute {
  if (!value || typeof value.id !== "string" || !Array.isArray(value.stops)) throw new Error("코스 서버 응답을 확인해 주세요.");
  const stops = [...value.stops].sort((a, b) => a.position - b.position).map(stop => { const copy = { ...stop }; Reflect.deleteProperty(copy, "position"); return copy; });
  const description = value.description || (value.content?.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim() || stops.map(stop => stop.name).join(" → ")).slice(0, 100);
  return {
    id: value.sampleId ?? value.id, title: value.title, stadium: value.stadium, description, content: value.content ?? "",
    ...(value.contentFormat ? { contentFormat: value.contentFormat } : {}), tags: value.tags, duration: value.duration,
    cover: value.cover || "/images/stadium-night.jpg", stops, ...(value.startLat !== undefined && value.startLng !== undefined ? { start: { lat: value.startLat, lng: value.startLng } } : {}),
    author: value.author, likes: value.likes ?? 0, views: value.views ?? 0, isSample: value.isSample ?? false, owned: value.isSample ? false : owned, createdAt: value.createdAt, ...(saveWarning ? { saveWarning } : {}),
  };
}

function payload(route: TripRoute, editing: boolean) {
  return {
    title: route.title, stadium: route.stadium, content: route.content, contentFormat: route.contentFormat ?? "",
    duration: route.duration, tags: route.tags, ...(route.start ? { startLat: route.start.lat, startLng: route.start.lng } : editing ? { startLat: null, startLng: null } : {}),
    stops: route.stops.map((stop, position) => ({ ...stop, position })),
  };
}

async function json(response: Response) {
  const value = await response.json().catch(() => null);
  if (!response.ok) throw new Error(value?.detail || value?.error || "코스를 저장하지 못했어요. 다시 시도해 주세요.");
  return value;
}

async function courseRequest(fetcher: typeof fetch, url: string, init: RequestInit = {}) {
  try { return await fetcher(url, { ...init, redirect: "error", signal: AbortSignal.timeout(40000) }); }
  catch { throw new Error("코스 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."); }
}

export async function fetchCourses(fetcher: typeof fetch = fetch): Promise<TripRoute[]> {
  const value = await json(await courseRequest(fetcher, "/api/courses/", { cache: "no-store" }));
  if (!Array.isArray(value)) throw new Error("코스 서버 응답을 확인해 주세요.");
  return value.map(course => routeFromApi(course));
}

export async function persistCourse(route: TripRoute, fetcher: typeof fetch = fetch): Promise<TripRoute> {
  const editToken = route.id ? token(route.id) : "";
  if (route.id && route.owned && !route.legacy && !editToken) throw new Error("이 코스의 편집 토큰을 찾을 수 없어 읽기만 가능해요.");
  const response = await json(await courseRequest(fetcher, editToken ? `/api/courses/${encodeURIComponent(route.id)}/` : "/api/courses/", {
    method: editToken ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json", ...(editToken ? { "X-Course-Edit-Token": editToken } : {}) },
    body: JSON.stringify(payload(route, Boolean(editToken))),
  }));
  let saveWarning = "";
  if (!editToken) {
    if (typeof response.editToken !== "string" || !response.editToken) throw new Error("코스 편집 토큰을 받지 못했어요.");
    saveWarning = rememberToken(response.id, response.editToken);
  } else saveWarning = rememberToken(response.id, editToken);
  return routeFromApi(response, true, saveWarning);
}

export async function removeCourse(id: string, fetcher: typeof fetch = fetch): Promise<void> {
  const editToken = token(id);
  if (!editToken) throw new Error("이 코스의 편집 토큰을 찾을 수 없어 삭제할 수 없어요.");
  await json(await courseRequest(fetcher, `/api/courses/${encodeURIComponent(id)}/`, { method: "DELETE", headers: { "X-Course-Edit-Token": editToken } }));
  sessionTokens.delete(id);
  try { window.localStorage.removeItem(`${TOKEN_PREFIX}${id}`); } catch {}
}

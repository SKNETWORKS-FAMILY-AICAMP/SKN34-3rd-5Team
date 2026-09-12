"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { loadKakaoMaps, type KakaoMap, type KakaoMaps, type KakaoOverlay } from "@/lib/kakao-maps";
import { collectNearbyPlaces, resolveStadium } from "@/lib/nearby-search";
import { distanceMeters, MAX_ROUTE_STOPS, mergePlaces, moveStop, NEARBY_RADIUS, NEARBY_SEARCHES, PLACE_CATEGORIES, sameStop, visiblePlaces, type CategoryFilter, type NearbyPlace, type NearbyStadium, type PlaceCategory } from "@/lib/nearby-places";
import type { RouteStop, TripRoute } from "@/lib/routes";
import { coursePointLabel, renumberMapPoints, undoDrawnPoint } from "@/lib/drawn-course";
import { CourseTravelPanel, useCourseDirections, useTravelOverlay } from "./course-travel";
import type { TourResult } from "@/lib/tour-places";

type PlannerProps = {
  stadium: NearbyStadium; stops: RouteStop[]; onChange: (stops: RouteStop[]) => void;
  initialStart?: TripRoute["start"]; onStartChange: (start: TripRoute["start"]) => void;
  courseName: string; onCourseNameChange: (name: string) => void;
  onSaveCourse: () => Promise<void>; saving: boolean; saveError: string;
};
const distanceLabel = (distance: number) => distance < 1000 ? `${Math.round(distance)}m` : `${(distance / 1000).toFixed(1)}km`;
const placeLink = (place: RouteStop) => place.placeId && /^\d+$/.test(place.placeId) ? `https://place.map.kakao.com/${place.placeId}` : `https://map.kakao.com/link/map/${encodeURIComponent(place.name)},${place.lat},${place.lng}`;

function CategoryIcon({ kind }: { kind: PlaceCategory }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={PLACE_CATEGORIES.find((c) => c.id === kind)!.icon} /></svg>;
}

function RouteStops({ stops, onChange, onFocus, separateStart = false }: { stops: RouteStop[]; onChange: PlannerProps["onChange"]; onFocus?: (stop: RouteStop) => void; separateStart?: boolean }) {
  return <div className="planner-route-list">
    <div className="planner-route-heading"><strong>내가 고른 방문 순서</strong><span>{stops.length} / {MAX_ROUTE_STOPS}</span></div>
    {stops.length === 0 ? <div className="planner-empty"><span aria-hidden="true">출발 → 1 → 2</span><strong>첫 번째 지점을 골라보세요</strong><p>빈 지도에 직접 지점을 찍거나<br />장소 정보를 보고 ‘코스에 담기’를 누르세요.</p></div> : <ol>{stops.map((stop, index) => <li key={stop.placeId ?? `${stop.name}:${stop.category}:${stop.lat}:${stop.lng}`}>
      <span className="planner-stop-number">{coursePointLabel(stops, index, separateStart)}</span>
      <button type="button" className="planner-stop-name" onClick={() => onFocus?.(stop)}><strong>{stop.name}</strong><small>{stop.category}</small></button>
      <div className="planner-stop-actions">
        <button type="button" disabled={index === 0} aria-label={`${stop.name} 위로 이동`} onClick={() => onChange(moveStop(stops, index, -1))}>↑</button>
        <button type="button" disabled={index === stops.length - 1} aria-label={`${stop.name} 아래로 이동`} onClick={() => onChange(moveStop(stops, index, 1))}>↓</button>
        <button type="button" aria-label={`${stop.name} 코스에서 삭제`} onClick={() => onChange(stops.filter((_, i) => i !== index))}>×</button>
      </div>
    </li>)}</ol>}
    <p className="planner-small">위아래 화살표로 순서를 바꿀 수 있어요.<br />{(stops[0]?.isMapPoint || stops[0]?.isDrawnPoint) ? "출발지를 포함해 최대 12개 지점을 담을 수 있어요." : "최대 12곳까지 코스에 담을 수 있어요."}</p>
  </div>;
}

export function NearbyRoutePlanner(props: PlannerProps) {
  const [ready, setReady] = useState<{ maps: KakaoMaps; stadium: NearbyStadium } | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    loadKakaoMaps().then(async (maps) => {
      const stadium = await resolveStadium(maps, props.stadium, controller.signal);
      if (!controller.signal.aborted) setReady({ maps, stadium });
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "지도를 불러오지 못했어요.");
    });
    return () => controller.abort();
  }, [props.stadium, attempt]);
  if (ready) return <LoadedPlanner {...props} maps={ready.maps} stadium={ready.stadium} />;
  return <div className="planner-workspace">
    <div className="planner-loading" role="status">{error ? <><strong>지도를 연결하지 못했어요</strong><p>{error}</p><button type="button" className="button button-secondary" onClick={() => { setError(""); setAttempt((a) => a + 1); }}>다시 연결</button></> : <><span className="writer-spinner" aria-hidden="true" /><strong>구장 위치와 지도를 불러오고 있어요</strong><p>반경 2.5km에서 나만의 하루를 찾아보세요.</p></>}</div>
    <aside className="planner-side"><RouteStops stops={props.stops} onChange={props.onChange} /></aside>
  </div>;
}

function LoadedPlanner({ maps, stadium, stops, onChange: onStopsChange, initialStart, onStartChange, courseName, onCourseNameChange, onSaveCourse, saving, saveError }: PlannerProps & { maps: KakaoMaps }) {
  const stopSnapshot = useRef(stops);
  useLayoutEffect(() => { stopSnapshot.current = stops; }, [stops]);
  const onChange = useCallback((next: RouteStop[]) => {
    const numbered = renumberMapPoints(next);
    stopSnapshot.current = numbered;
    onStopsChange(numbered);
  }, [onStopsChange]);
  const [drawHistory, setDrawHistory] = useState<string[]>(() => stops.filter((stop) => (stop.isMapPoint || stop.isDrawnPoint) && stop.placeId).map((stop) => stop.placeId!));
  const [courseCompleted, setCourseCompleted] = useState(false);
  const travel = useCourseDirections(stops, courseCompleted, initialStart);
  useEffect(() => { onStartChange(travel.location ?? undefined); }, [travel.location, onStartChange]);
  const canComplete = stops.length > 0 && !travel.picking && !travel.locating && (travel.origin === "first" || Boolean(travel.location));
  const canSaveCourse = canComplete && Boolean(courseName.trim()) && !saving;
  const separateStart = travel.origin !== "first";
  const drawing = !travel.picking;
  const mapNode = useRef<HTMLDivElement>(null);
  useEffect(() => { if (travel.picking) mapNode.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [travel.picking]);
  const [map, setMap] = useState<KakaoMap | null>(null);
  useTravelOverlay(map, maps, travel);
  const [viewport, setViewport] = useState(0);
  const [listArea, setListArea] = useState<{ stadium: string; south: number; north: number; west: number; east: number } | null>(null);
  const activeListArea = listArea?.stadium === stadium.code ? listArea : null;
  const [nearPoint, setNearPoint] = useState<{ stadium: string; lat: number; lng: number } | null>(null);
  const activeNearPoint = nearPoint?.stadium === stadium.code ? nearPoint : null;
  const [places, setPlaces] = useState<NearbyPlace[]>([]);
  const [categories, setCategories] = useState<PlaceCategory[]>(() => PLACE_CATEGORIES.map((category) => category.id));
  const allSelected = categories.length === PLACE_CATEGORIES.length;
  const preferred = useRef<CategoryFilter>("all");
  const [subcategories, setSubcategories] = useState<Partial<Record<PlaceCategory, string[]>>>({});
  const [openCategory, setOpenCategory] = useState<PlaceCategory | null>(null);
  const filtersNode = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!openCategory) return;
    const closeOutside = (event: PointerEvent) => {
      if (!filtersNode.current?.contains(event.target as Node)) setOpenCategory(null);
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [openCategory]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<RouteStop | NearbyPlace | null>(null);
  const [hovered, setHovered] = useState<RouteStop | NearbyPlace | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const holdPreview = useCallback(() => clearTimeout(hoverTimer.current), []);
  const showPreview = useCallback((place: RouteStop) => {
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(place), 1000);
  }, []);
  const hidePreview = useCallback(() => { clearTimeout(hoverTimer.current); hoverTimer.current = setTimeout(() => setHovered(null), 200); }, []);
  useEffect(() => () => clearTimeout(hoverTimer.current), []);
  const [sideTab, setSideTab] = useState<"places" | "route">("places");
  const [progress, setProgress] = useState({ done: false, completed: 0, failures: 0 });
  const [attempt, setAttempt] = useState(0);
  const [listLimit, setListLimit] = useState(30);
  const [notice, setNotice] = useState("");
  const [tour, setTour] = useState<{ status: TourResult["status"] | "loading"; truncated: boolean }>({ status: "loading", truncated: false });
  const [tourAttempt, setTourAttempt] = useState(0);

  const undoPoint = useCallback(() => {
    const result = undoDrawnPoint(stopSnapshot.current, drawHistory);
    setDrawHistory(result.history);
    if (!result.removed) return;
    onChange(result.stops);
    setSelected(null); setHovered(null); clearTimeout(hoverTimer.current);
    setNotice(`${result.removed.name} 한 곳을 되돌렸어요.`);
  }, [drawHistory, onChange]);

  function resetCourse() {
    onChange([]);
    setDrawHistory([]); setCourseCompleted(false);
    travel.reset();
    clearTimeout(hoverTimer.current); setSelected(null); setHovered(null);
    setNearPoint(null); setListLimit(30); setSideTab("route");
    setNotice("코스의 모든 지점과 경로를 초기화했어요.");
  }

  useEffect(() => {
    if (!map || !drawing) return;
    const addPoint = (event: { latLng: { getLat(): number; getLng(): number } }) => {
      const current = stopSnapshot.current;
      const lat = event.latLng.getLat(), lng = event.latLng.getLng();
      setNearPoint({ stadium: stadium.code, lat, lng });
      setListArea(null); setListLimit(30); setSideTab("places");
      if (current.length >= MAX_ROUTE_STOPS) { setNotice("출발지를 포함해 최대 12개 지점까지 담을 수 있어요."); return; }
      const previous = current.at(-1);
      if (previous && Math.abs(previous.lat - lat) < .000001 && Math.abs(previous.lng - lng) < .000001) return;
      const placeId = `map:${crypto.randomUUID()}`;
      onChange([...current, { name: "", category: "직접 지정", lat, lng, placeId, isMapPoint: true }]);
      setDrawHistory((history) => [...history, placeId]);
      setSelected(null); setHovered(null); clearTimeout(hoverTimer.current);
      setNotice(current.length ? "지점을 추가했어요. 우클릭하면 방금 찍은 지점만 되돌려요." : "출발지를 정했어요. 다음 지점을 좌클릭하세요.");
    };
    const canvas = mapNode.current;
    const suppressMenu = (event: MouseEvent) => event.preventDefault();
    maps.event.addListener(map, "click", addPoint);
    maps.event.addListener(map, "rightclick", undoPoint);
    canvas?.addEventListener("contextmenu", suppressMenu);
    return () => {
      maps.event.removeListener(map, "click", addPoint);
      maps.event.removeListener(map, "rightclick", undoPoint);
      canvas?.removeEventListener("contextmenu", suppressMenu);
    };
  }, [map, maps, drawing, onChange, undoPoint, stadium.code]);

  useEffect(() => {
    if (!map) return;
    const idleCursor = drawing || travel.picking ? "default" : "grab";
    const dragStart = () => map.setCursor("grabbing");
    const dragEnd = () => map.setCursor(idleCursor);
    map.setCursor(idleCursor);
    maps.event.addListener(map, "dragstart", dragStart);
    maps.event.addListener(map, "dragend", dragEnd);
    return () => {
      maps.event.removeListener(map, "dragstart", dragStart);
      maps.event.removeListener(map, "dragend", dragEnd);
    };
  }, [map, maps, drawing, travel.picking]);

  const fitArea = useCallback((target: KakaoMap) => {
    const latDelta = NEARBY_RADIUS / 111195;
    const lngDelta = latDelta / Math.cos(stadium.lat * Math.PI / 180);
    const bounds = new maps.LatLngBounds();
    bounds.extend(new maps.LatLng(stadium.lat - latDelta, stadium.lng - lngDelta));
    bounds.extend(new maps.LatLng(stadium.lat + latDelta, stadium.lng + lngDelta));
    target.setBounds(bounds, 35, 30, 35, 30);
  }, [maps, stadium]);

  useEffect(() => {
    if (!mapNode.current) return;
    const element = mapNode.current;
    const target = new maps.Map(element, { center: new maps.LatLng(stadium.lat, stadium.lng), level: 6 });
    fitArea(target);
    // Apply the initial zoom synchronously, before the map is painted.
    target.setLevel(Math.max(1, target.getLevel() - 2));
    target.setCenter(new maps.LatLng(stadium.lat, stadium.lng));
    const frame = requestAnimationFrame(() => setMap(target));
    const circle = new maps.Circle({ map: target, center: new maps.LatLng(stadium.lat, stadium.lng), radius: NEARBY_RADIUS, strokeWeight: 2, strokeColor: "#4f82d8", strokeOpacity: .55, strokeStyle: "dash", fillColor: "#608eed", fillOpacity: .035 });
    const idle = () => setViewport((v) => v + 1);
    maps.event.addListener(target, "idle", idle);
    const observer = new ResizeObserver(() => { target.relayout(); idle(); });
    observer.observe(element);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); maps.event.removeListener(target, "idle", idle); circle.setMap(null); element.replaceChildren(); };
  }, [maps, stadium, fitArea]);

  useEffect(() => {
    const controller = new AbortController();
    collectNearbyPlaces(maps, stadium, controller.signal, () => preferred.current, (incoming, completed, failures) => {
      setPlaces((previous) => mergePlaces(previous, incoming));
      setProgress({ done: false, completed, failures });
    }).then(({ completed, failures }) => {
      if (!controller.signal.aborted) setProgress({ done: true, completed, failures });
    }).catch(() => { /* Aborted requests cannot update a different stadium. */ });
    return () => controller.abort();
  }, [maps, stadium, attempt]);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    let active = true;
    const params = new URLSearchParams({ stadium: stadium.code, lat: String(stadium.lat), lng: String(stadium.lng) });
    fetch(`/tour-api?${params}`, { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error("Tourism places unavailable");
      const result: TourResult = await response.json();
      if (!Array.isArray(result.places) || !["ok", "partial", "unconfigured", "error"].includes(result.status)) throw new Error("Invalid tourism response");
      if (!active || controller.signal.aborted) return;
      setPlaces((previous) => mergePlaces(previous, result.places));
      setTour({ status: result.status, truncated: result.truncated });
    }).catch(() => { if (active) setTour({ status: "error", truncated: false }); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [stadium, tourAttempt]);

  const subcategoryLabel = (place: NearbyPlace) => place.kind === "food" ? place.cuisine : place.subcategory ?? place.category;
  const visible = useMemo(() => {
    const matching = places.filter((place) => {
      const choices = subcategories[place.kind];
      return (!choices?.length || choices.includes(subcategoryLabel(place))) && `${place.name} ${place.detail}`.toLowerCase().includes(query.trim().toLowerCase());
    });
    return visiblePlaces(matching, categories);
  }, [places, categories, subcategories, query]);
  // Keep the last requested area until the user applies a new area or resets it.
  // Map pins remain available when panning outside that area.
  const listedPlaces = activeNearPoint ? visible.filter((place) => distanceMeters(activeNearPoint, place) <= 70) : activeListArea ? visible.filter((place) =>
    place.lat >= activeListArea.south && place.lat <= activeListArea.north &&
    place.lng >= activeListArea.west && place.lng <= activeListArea.east
  ) : visible;
  const showCurrentArea = () => {
    if (!map) return;
    const bounds = map.getBounds();
    const sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
    setNearPoint(null);
    setListArea({ stadium: stadium.code, south: sw.getLat(), north: ne.getLat(), west: sw.getLng(), east: ne.getLng() });
    setListLimit(30);
    setSideTab("places");
  };
  const tourCount = places.filter((place) => place.tourContentId).length;
  const loading = !progress.done || tour.status === "loading";
  const preview = hovered ?? selected;
  const selectedPlace = places.find((place) => preview && sameStop(place, preview));
  const currentSelection = selectedPlace ?? preview;
  const addCoursePlace = useCallback((place: RouteStop) => {
    const current = stopSnapshot.current;
    if (current.some((stop) => sameStop(stop, place))) { setNotice("이미 코스에 담은 장소예요."); return; }
    if (current.length >= MAX_ROUTE_STOPS) { setNotice("코스에는 최대 12개 지점까지 담을 수 있어요."); return; }
    const stop: RouteStop = { name: place.name, lat: place.lat, lng: place.lng, category: place.category, placeId: place.placeId ?? `place:${crypto.randomUUID()}`, tourContentId: place.tourContentId, address: place.address, ...(drawing ? { isDrawnPoint: true } : {}) };
    onChange([...current, stop]);
    if (drawing) setDrawHistory((history) => [...history, stop.placeId!]);
    clearTimeout(hoverTimer.current); setHovered(null); setSelected(place); setSideTab("route");
    setNotice(`${place.name}을(를) 코스에 담았어요.`);
  }, [drawing, onChange]);
  const selectPlace = useCallback((place: RouteStop) => {
    clearTimeout(hoverTimer.current); setHovered(null);
    setSelected(place);
    setNotice("");
    if (map) map.setCenter(new maps.LatLng(place.lat, place.lng));
  }, [map, maps]);

  useEffect(() => {
    if (!map) return;
    const overlays: KakaoOverlay[] = [];
    const overlay = (content: HTMLElement, lat: number, lng: number, zIndex: number, yAnchor = .5) => {
      overlays.push(new maps.CustomOverlay({ map, position: new maps.LatLng(lat, lng), content, yAnchor, zIndex, clickable: drawing }));
    };
    const unselected = visible.filter((p) => !stops.some((stop) => sameStop(stop, p)));
    const stadiumPlace: RouteStop = { name: stadium.name, lat: stadium.lat, lng: stadium.lng, address: stadium.address, category: "야구장", placeId: `stadium:${stadium.code}` };
    if (!stops.some((stop) => sameStop(stop, stadiumPlace))) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "planner-stadium-marker";
      button.textContent = `⚾ ${stadium.name}`;
      button.setAttribute("aria-label", `야구장: ${stadium.name}`);
      button.onmouseenter = () => showPreview(stadiumPlace);
      button.onmouseleave = hidePreview;
      button.onfocus = () => showPreview(stadiumPlace);
      button.onblur = hidePreview;
      button.onclick = (event) => { event.stopPropagation(); maps.event.preventMap(); selectPlace(stadiumPlace); };
      button.oncontextmenu = (event) => { if (drawing) { event.preventDefault(); event.stopPropagation(); maps.event.preventMap(); undoPoint(); } };
      overlay(button, stadium.lat, stadium.lng, 8, 1);
    }
    const projection = map.getProjection();
    const positions = unselected.map((place) => ({
      place,
      point: projection.containerPointFromCoords(new maps.LatLng(place.lat, place.lng)),
    }));
    // Recompute screen-space crowding after zoom/pan; isolated places keep icons.
    const crowded = new Set(positions.filter((entry, index) => positions.some((other, otherIndex) =>
      index !== otherIndex && Math.hypot(entry.point.x - other.point.x, entry.point.y - other.point.y) < 40
    )).map(({ place }) => place.placeId));
    const makePin = (place: NearbyPlace) => {
      const focused = Boolean(selected && sameStop(place, selected));
      const compact = crowded.has(place.placeId) && !focused;
      const category = PLACE_CATEGORIES.find((c) => c.id === place.kind)!;
      const button = document.createElement("button");
      button.type = "button"; button.className = `planner-pin planner-pin-${place.kind}${focused ? " is-focused" : ""}${compact ? " planner-pin-dot" : ""}`;
      button.style.setProperty("--pin-color", category.color);
      button.setAttribute("aria-label", `${category.label}: ${place.name}`);
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", category.icon); svg.appendChild(path); button.appendChild(svg);
      button.onmouseenter = () => showPreview(place);
      button.onmouseleave = hidePreview;
      button.onfocus = () => showPreview(place);
      button.onblur = hidePreview;
      button.onclick = (event) => { event.stopPropagation(); maps.event.preventMap(); selectPlace(place); };
      button.oncontextmenu = (event) => { if (drawing) { event.preventDefault(); event.stopPropagation(); maps.event.preventMap(); undoPoint(); } };
      overlay(button, place.lat, place.lng, selected && sameStop(place, selected) ? 10 : 3);
    };
    unselected.forEach(makePin);
    for (const [index, stop] of stops.entries()) {
      const button = document.createElement("button"); button.type = "button"; button.className = `${stop.isMapPoint || stop.isDrawnPoint ? "planner-drawn-pin" : "planner-number-pin"}${selected && sameStop(stop, selected) ? " is-focused" : ""}`;
      const label = document.createElement("span"); label.textContent = coursePointLabel(stops, index, separateStart); button.appendChild(label);
      button.setAttribute("aria-label", `코스 ${coursePointLabel(stops, index, separateStart)}: ${stop.name}`);
      const place = places.find((p) => sameStop(p, stop)) ?? stop;
      button.onmouseenter = () => showPreview(place);
      button.onmouseleave = hidePreview;
      button.onfocus = () => showPreview(place);
      button.onblur = hidePreview;
      button.onclick = (event) => { event.stopPropagation(); maps.event.preventMap(); if (drawing) { setSelected(place); setNotice("이미 코스에 담은 지점이에요."); } else selectPlace(place); };
      button.oncontextmenu = (event) => { if (drawing) { event.preventDefault(); event.stopPropagation(); maps.event.preventMap(); undoPoint(); } };
      overlay(button, stop.lat, stop.lng, 12, stop.isMapPoint || stop.isDrawnPoint ? 1 : .5);
    }
    return () => overlays.forEach((item) => item.setMap(null));
  }, [map, maps, visible, stops, selected, selectPlace, viewport, places, drawing, undoPoint, showPreview, hidePreview, stadium, separateStart]);

  function chooseCategory(next: CategoryFilter) {
    clearTimeout(hoverTimer.current); setHovered(null);
    preferred.current = next !== "all" && !categories.includes(next) ? next : "all";
    setCategories((current) => next === "all" ? (current.length === PLACE_CATEGORIES.length ? [] : PLACE_CATEGORIES.map((category) => category.id)) : current.includes(next) ? current.filter((category) => category !== next) : [...current, next]);
    if (next === "all" && !allSelected) setSubcategories({});
    setOpenCategory(null);
    setQuery(""); setListLimit(30); setSideTab("places"); setSelected(null); setNotice("");
  }
  function addStop() {
    if (currentSelection) addCoursePlace(currentSelection);
  }
  const alreadyAdded = currentSelection && stops.some((stop) => sameStop(stop, currentSelection));

  return <div className="nearby-planner">
    <div ref={filtersNode} className="planner-filters" aria-label="장소 카테고리" onKeyDown={(event) => { if (event.key === "Escape") { setOpenCategory(null); filtersNode.current?.querySelector<HTMLButtonElement>(`[data-category-arrow="${openCategory}"]`)?.focus(); } }}>
      <button type="button" className="planner-filter" aria-pressed={allSelected} onClick={() => chooseCategory("all")}>전체</button>
      {PLACE_CATEGORIES.map((category) => {
        const categoryPlaces = places.filter((place) => place.kind === category.id);
        const options = [...new Set(categoryPlaces.map(subcategoryLabel))].sort((a, b) => a.localeCompare(b, "ko"));
        const choices = subcategories[category.id] ?? [];
        const active = categories.includes(category.id);
        const toggleSubcategory = (label: string) => {
          setSubcategories((previous) => {
            const values = previous[category.id] ?? [];
            return { ...previous, [category.id]: values.includes(label) ? values.filter((value) => value !== label) : [...values, label] };
          });
          setCategories((previous) => previous.includes(category.id) ? previous : [...previous, category.id]);
          preferred.current = category.id;
          setListLimit(30); setSelected(null); setSideTab("places");
        };
        return <div className="planner-category-group" key={category.id} style={{ "--pin-color": category.color } as CSSProperties}>
          <div className="planner-category-controls">
            <button type="button" className="planner-filter" aria-pressed={active} onClick={() => chooseCategory(category.id)}><CategoryIcon kind={category.id} />{category.label}<span>{categoryPlaces.length}</span></button>
            <button type="button" className="planner-category-arrow" data-category-arrow={category.id} aria-label={`${category.label} 소분류 선택`} aria-expanded={openCategory === category.id} aria-controls={`planner-subcategories-${category.id}`} onClick={() => setOpenCategory((current) => current === category.id ? null : category.id)}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg></button>
          </div>
          {openCategory === category.id && <div className="planner-subcategory-menu" id={`planner-subcategories-${category.id}`} role="group" aria-label={`${category.label} 소분류`}>
            <strong>{category.label} 소분류</strong>
            <button type="button" className="planner-subcategory-reset" onClick={() => { setSubcategories((previous) => ({ ...previous, [category.id]: [] })); setCategories((previous) => previous.includes(category.id) ? previous : [...previous, category.id]); setListLimit(30); setSelected(null); setSideTab("places"); }}>소분류 전체 보기</button>
            {options.length === 0 ? <p>조회된 장소가 없어요.</p> : options.map((label) => <label key={label}><input type="checkbox" checked={choices.includes(label)} onChange={() => toggleSubcategory(label)} /><span>{label}</span><small>{categoryPlaces.filter((place) => subcategoryLabel(place) === label).length}</small></label>)}
          </div>}
        </div>;
      })}
    </div>
    <div className="planner-drawing-toolbar">
      <span id="drawing-help">빈 곳 클릭: 지점 추가 · 장소 핀 클릭: 정보 확인 후 코스에 담기 · 우클릭: 마지막 지점 되돌리기</span><button type="button" className="planner-draw-undo" disabled={!canComplete} onClick={() => { setCourseCompleted(true); setSideTab("route"); }}>코스 완성</button><button type="button" className="planner-draw-undo" disabled={stops.length === 0 && !travel.location && !travel.picking && !travel.locating} onClick={resetCourse}><span aria-hidden="true">↶ </span>초기화</button>
    </div>
    <div className="planner-workspace">
      <div className={`planner-map-stage${travel.picking ? " is-picking-start" : ""}${drawing ? " is-drawing-course" : ""}`}>
        {travel.picking && <div className="course-pick-hint">지도를 눌러 출발 위치를 지정하세요 <button type="button" onClick={travel.cancelPicking}>취소</button></div>}
        <div ref={mapNode} className="planner-map-canvas" aria-label={`${stadium.name} 주변 장소 지도`} aria-describedby={drawing ? "drawing-help" : undefined} />
        <button type="button" className="planner-current-area" disabled={!map} onClick={showCurrentArea}>지금 지도에서 보기</button>
        <div className="planner-map-controls"><button type="button" title="구장 주변 전체 보기" aria-label="구장 주변 전체 보기" onClick={() => map && fitArea(map)}>⌖</button><button type="button" aria-label="지도 확대" onClick={() => map && map.setLevel(Math.max(1, map.getLevel() - 1))}>+</button><button type="button" aria-label="지도 축소" onClick={() => map && map.setLevel(Math.min(10, map.getLevel() + 1))}>−</button></div>
        {currentSelection && <section className="planner-place-card" aria-label="선택한 장소" onMouseEnter={holdPreview} onMouseLeave={hidePreview}>
          <button type="button" className="planner-card-close" aria-label="장소 상세 닫기" onClick={() => { clearTimeout(hoverTimer.current); setSelected(null); setHovered(null); }}>×</button>
          <span className="planner-place-category">{selectedPlace?.subcategory ?? currentSelection.category}{selectedPlace ? ` · 구장에서 ${distanceLabel(selectedPlace.distance)}` : ""}</span><h3>{currentSelection.name}</h3>
          {currentSelection.tourContentId && <span className="planner-source-badge">{currentSelection.placeId?.startsWith("tour:") ? "한국관광공사" : "카카오 · 한국관광공사"}</span>}
          <p>{currentSelection.address || "주소 정보가 없는 장소예요."}</p>
          {selectedPlace?.phone && <p>{selectedPlace.phone}</p>}
          <div className="planner-card-actions"><a href={placeLink(currentSelection)} target="_blank" rel="noreferrer">{currentSelection.placeId && /^\d+$/.test(currentSelection.placeId) ? "카카오맵 상세 ↗" : "카카오맵 위치 보기 ↗"}</a><button type="button" disabled={Boolean(alreadyAdded) || stops.length >= MAX_ROUTE_STOPS} onClick={addStop}>{alreadyAdded ? "✓ 코스에 담았어요" : stops.length >= MAX_ROUTE_STOPS ? "최대 12곳까지" : "+ 코스에 담기"}</button></div>
        </section>}
      </div>
      <aside className="planner-side">
        <div className="planner-side-tabs" role="tablist" aria-label="장소 목록"><button type="button" role="tab" id="nearby-places-tab" aria-controls="nearby-side-panel" aria-selected={sideTab === "places"} onClick={() => setSideTab("places")}>주변 장소 <b>{listedPlaces.length}</b></button><button type="button" role="tab" id="nearby-route-tab" aria-controls="nearby-side-panel" aria-selected={sideTab === "route"} onClick={() => setSideTab("route")}>내 코스 <b>{stops.length}</b></button></div>
        <div id="nearby-side-panel" role="tabpanel" aria-labelledby={sideTab === "places" ? "nearby-places-tab" : "nearby-route-tab"} className="planner-side-content">
          {sideTab === "route" ? <><CourseTravelPanel travel={travel} stops={stops} showDirections={courseCompleted} originReplacement={courseCompleted ? <div className="course-save" aria-busy={saving}>
            <label htmlFor="planner-course-name">코스 이름</label>
            <input id="planner-course-name" value={courseName} maxLength={80} disabled={saving} placeholder="코스 이름을 입력하세요" onChange={(event) => onCourseNameChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSaveCourse) void onSaveCourse(); } }} />
            <button type="button" className="course-save-button" disabled={!canSaveCourse} onClick={() => void onSaveCourse()}>{saving ? "저장 중…" : "코스 저장"}</button>
            <small>이 브라우저에 저장돼요.</small>
            {saveError && <p role="alert" className="course-save-error">{saveError}</p>}
          </div> : undefined} onFit={() => {
            if (!map) return;
            const bounds = new maps.LatLngBounds();
            const points = [...travel.points, ...(travel.data?.legs.flatMap((leg) => leg.paths.flat()) ?? [])];
            points.forEach((point) => bounds.extend(new maps.LatLng(point.lat, point.lng)));
            if (points.length) map.setBounds(bounds, 40, 30, 40, 30);
          }} /><RouteStops stops={stops} onChange={onChange} separateStart={separateStart} onFocus={(stop) => selectPlace(places.find((p) => sameStop(stop, p)) ?? stop)} /></> : <>
            <label className="planner-search"><span className="sr-only">불러온 장소에서 찾기</span><input type="search" value={query} placeholder="불러온 장소에서 찾기" onChange={(event) => { setQuery(event.target.value); setListLimit(30); }} onKeyDown={(event) => { if (event.key === "Enter") event.preventDefault(); }} /></label>
            <div className="planner-list-caption"><span>{activeNearPoint ? "찍은 지점에서 가까운 순 · 직선거리" : "구장에서 가까운 순 · 직선거리"}{activeNearPoint && <small>찍은 지점 반경 70m 내 시설</small>}{activeListArea && <small>선택한 지도 범위 내 장소</small>}</span><button type="button" disabled={!activeListArea && !activeNearPoint} title="지도 범위 해제" aria-label="지도 범위 해제" onClick={() => { setListArea(null); setNearPoint(null); setListLimit(30); }}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 10a9 9 0 1 1 2 8M3 4v6h6" /></svg></button></div>
            {listedPlaces.length === 0 ? <div className="planner-empty"><strong>{loading ? "주변 장소를 찾고 있어요" : "조건에 맞는 장소가 없어요"}</strong><p>{loading ? "조회되는 장소부터 차례로 표시할게요." : activeNearPoint ? "이 지점의 70m 안에는 현재 조건에 맞는 시설이 없어요. 다른 지점을 누르거나 범위를 해제해 보세요." : activeListArea ? "다른 위치에서 ‘지금 지도에서 보기’를 누르거나 지도 범위를 해제해 보세요." : "다른 카테고리나 검색어로 살펴보세요."}</p></div> : <ul className="planner-place-list">{[...listedPlaces].sort((a, b) => activeNearPoint ? distanceMeters(activeNearPoint, a) - distanceMeters(activeNearPoint, b) : a.distance - b.distance).slice(0, listLimit).map((place) => <li key={place.placeId}><button type="button" aria-pressed={Boolean(selected && sameStop(place, selected))} onClick={() => selectPlace(place)}>
              <span className={`planner-list-icon planner-pin-${place.kind}`} style={{ "--pin-color": PLACE_CATEGORIES.find((c) => c.id === place.kind)!.color } as CSSProperties}><CategoryIcon kind={place.kind} /></span>
              <span className="planner-list-name"><strong>{place.name}</strong><small>{place.subcategory ?? place.category}{place.kind === "food" ? ` · ${place.cuisine}` : ""} · {distanceLabel(activeNearPoint ? distanceMeters(activeNearPoint, place) : place.distance)}</small>{place.tourContentId && <span className="planner-source-badge">관광공사</span>}</span><span className="planner-list-arrow">{stops.some((stop) => sameStop(stop, place)) ? "✓" : "›"}</span>
            </button></li>)}</ul>}
            {listedPlaces.length > listLimit && <button type="button" className="planner-more" onClick={() => setListLimit((n) => n + 30)}>장소 더 보기 ({Math.min(listLimit, listedPlaces.length)}/{listedPlaces.length})</button>}
          </>}
        </div>
      </aside>
    </div>
    <div className="planner-status" role="status"><span>{!progress.done && <span className="writer-spinner" aria-hidden="true" />}{progress.done ? `${places.length}곳 조회 · 현재 ${visible.length}곳 표시` : `주변 장소 불러오는 중 (${progress.completed}/${NEARBY_SEARCHES.length})`}{progress.failures > 0 ? ` · 일부 검색 실패 (${progress.failures})` : ""}</span>{progress.done && progress.failures > 0 && <button type="button" onClick={() => { setProgress({ done: false, completed: 0, failures: 0 }); setAttempt((a) => a + 1); }}>실패한 검색 다시 시도</button>}<span>{notice}</span></div>
    <div className="planner-tour-status" role="status"><span>{tour.status === "loading" ? "관광공사 장소도 찾고 있어요…" : tour.status === "unconfigured" ? "관광공사 장소는 아직 연결되지 않았어요." : tour.status === "error" ? "관광공사 장소를 불러오지 못했어요." : `관광공사 ${tourCount}곳 반영${tour.status === "partial" ? " · 일부 조회에 실패했어요." : ""}${tour.truncated ? " · 가까운 장소부터 일부 조회했어요." : ""}`}</span>{(tour.status === "error" || tour.status === "partial") && <button type="button" onClick={() => { setTour({ status: "loading", truncated: false }); setTourAttempt((value) => value + 1); }}>관광공사 다시 불러오기</button>}</div>
    <p className="planner-help">가까이 모인 장소는 작은 점으로 보여요. 확대해서 장소 사이가 벌어지면 카테고리 아이콘으로 바뀌어요. 점이나 아이콘을 눌러 장소를 확인하세요.<br />코스에 장소를 담으면 내 코스에서 실제 경로와 예상 이동 시간을 확인할 수 있어요.</p>
    <details className="planner-data-note"><summary>장소 표시 기준</summary><p>구장 중심에서 직선거리 2.5km 안의 카카오 검색 결과와 한국관광공사의 관광·문화·일부 레포츠 장소를 표시해요. 공원·산책길, 관광 명소, 박물관·전시관 등으로 분류하고 두 곳에 등록된 장소는 이름·주소·위치가 일치하는 경우 합쳐요. 이름이 다르게 등록된 장소는 중복될 수 있어요. 구장 주소·명칭·중심 인접 여부로 내부 시설을 제외하며, 실제 경계와 차이가 있을 수 있어요. 카테고리를 눌러 표시하거나 숨길 수 있고, 전체 버튼으로 모두 선택하거나 해제할 수 있어요. 선택한 분류에서 조회된 장소는 개수 제한 없이 지도에 모두 표시해요. 오른쪽 목록은 더 보기를 눌러 이어서 확인할 수 있어요. 제공되는 정보와 검색 결과 수에 제한이 있어 주변의 모든 장소가 포함되지는 않아요.</p></details>
  </div>;
}

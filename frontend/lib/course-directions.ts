export type TravelMode = "walk" | "car" | "transit";
export type TravelPoint = { lat: number; lng: number };
export type TravelLeg = { status: "ok" | "error"; distance?: number; seconds?: number; paths: TravelPoint[][]; instructions: string[]; error?: string };
export type CourseDirections = { mode: TravelMode; legs: TravelLeg[]; distance: number | null; seconds: number | null };
export const TRAVEL_MODES = [{ id: "walk", label: "도보", color: "#278469" }, { id: "car", label: "자동차", color: "#2868dc" }, { id: "transit", label: "대중교통", color: "#8054b5" }] as const;
export function travelTime(seconds: number) {
  const minutes = Math.ceil(seconds / 60);
  return minutes >= 60 ? `${Math.floor(minutes / 60)}시간${minutes % 60 ? ` ${minutes % 60}분` : ""}` : `${minutes}분`;
}
export function travelDistance(meters: number) { return meters < 1000 ? `${Math.round(meters)}m` : `${(meters / 1000).toFixed(1)}km`; }
export function validTravelPoint(value: unknown): value is TravelPoint {
  if (!value || typeof value !== "object") return false;
  const p = value as TravelPoint;
  return typeof p.lat === "number" && typeof p.lng === "number" && Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180;
}

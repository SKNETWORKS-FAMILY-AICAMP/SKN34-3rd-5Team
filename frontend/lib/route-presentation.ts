type Point = { x: number; y: number };
type ProjectedPoint = Point & { lat: number; lng: number };
type Viewport = { left: number; right: number; top: number; bottom: number };

// Sample across a whole path, including dense provider geometry. Never connect
// separate paths (e.g. transit legs with missing geometry).
export function directionMarker(paths: ProjectedPoint[][], viewport: Viewport, stops: Point[], used: Point[]) {
  const candidates: (ProjectedPoint & { angle: number; score: number })[] = [];
  const center = { x: (viewport.left + viewport.right) / 2, y: (viewport.top + viewport.bottom) / 2 };
  for (const path of paths) {
    let next = 12;
    for (let i = 1; i < path.length; i++) {
      const a = path[i - 1], b = path[i];
      const length = Math.hypot(b.x - a.x, b.y - a.y);
      if (length < .001) continue;
      for (; next <= length; next += 16) {
        const t = next / length, x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t;
        if (x < viewport.left + 32 || x > viewport.right - 32 || y < viewport.top + 32 || y > viewport.bottom - 32) continue;
        if (stops.some((p) => Math.hypot(p.x - x, p.y - y) < 44) || used.some((p) => Math.hypot(p.x - x, p.y - y) < 140)) continue;
        candidates.push({ x, y, lat: a.lat + (b.lat - a.lat) * t, lng: a.lng + (b.lng - a.lng) * t, angle: Math.atan2(b.y - a.y, b.x - a.x), score: Math.hypot(center.x - x, center.y - y) });
      }
      next -= length;
    }
  }
  return candidates.sort((a, b) => a.score - b.score)[0];
}

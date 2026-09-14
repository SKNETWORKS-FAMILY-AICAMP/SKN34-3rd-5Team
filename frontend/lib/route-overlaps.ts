export type RouteCoordinate = { lat: number; lng: number };
export type RouteBand = { legs: number[]; path: RouteCoordinate[] };
type XY = { x: number; y: number };
type Segment = { leg: number; chain: number; a: RouteCoordinate; b: RouteCoordinate; start: XY; end: XY; length: number; cuts: number[]; overlaps: { from: number; to: number; leg: number }[] };
const EPSILON = 1e-7;
const lerp = (a: RouteCoordinate, b: RouteCoordinate, t: number): RouteCoordinate => ({ lat: a.lat + (b.lat - a.lat) * t, lng: a.lng + (b.lng - a.lng) * t });

// Work in metres, not zoom-dependent pixels: crossing streets or nearby parallel
// roads must not become a shared route when the user zooms out.
export function splitRouteOverlaps(legs: RouteCoordinate[][][]): RouteBand[] {
  const origin = legs.flatMap((paths) => paths.flat())[0];
  if (!origin) return [];
  const longitudeScale = 111195 * Math.cos(origin.lat * Math.PI / 180);
  const xy = (p: RouteCoordinate): XY => ({ x: (p.lng - origin.lng) * longitudeScale, y: (p.lat - origin.lat) * 111195 });
  const segments: Segment[] = [];
  let chain = 0;
  legs.forEach((paths, leg) => paths.forEach((path) => {
    chain++;
    for (let i = 1; i < path.length; i++) {
      const a = path[i - 1], b = path[i], start = xy(a), end = xy(b);
      const length = Math.hypot(end.x - start.x, end.y - start.y);
      if (length < .01) continue;
      segments.push({ leg, chain, a, b, start, end, length, cuts: [0, 1], overlaps: [] });
    }
  }));
  for (let i = 0; i < segments.length; i++) {
    const a = segments[i], dx = a.end.x - a.start.x, dy = a.end.y - a.start.y;
    for (let j = i + 1; j < segments.length; j++) {
      const b = segments[j];
      if (a.leg === b.leg) continue;
      if (Math.max(a.start.x, a.end.x) + .75 < Math.min(b.start.x, b.end.x) || Math.max(b.start.x, b.end.x) + .75 < Math.min(a.start.x, a.end.x) || Math.max(a.start.y, a.end.y) + .75 < Math.min(b.start.y, b.end.y) || Math.max(b.start.y, b.end.y) + .75 < Math.min(a.start.y, a.end.y)) continue;
      const bx = b.end.x - b.start.x, by = b.end.y - b.start.y;
      if (Math.abs(dx * bx + dy * by) / (a.length * b.length) < .9995) continue;
      if (Math.max(Math.abs(dx * (b.start.y - a.start.y) - dy * (b.start.x - a.start.x)), Math.abs(dx * (b.end.y - a.start.y) - dy * (b.end.x - a.start.x))) / a.length > .75) continue;
      const interval = (owner: Segment, other: Segment) => {
        const x = owner.end.x - owner.start.x, y = owner.end.y - owner.start.y;
        const at = (p: XY) => ((p.x - owner.start.x) * x + (p.y - owner.start.y) * y) / (owner.length * owner.length);
        const first = at(other.start), last = at(other.end);
        return { from: Math.max(0, Math.min(first, last)), to: Math.min(1, Math.max(first, last)), leg: other.leg };
      };
      const overlapA = interval(a, b), overlapB = interval(b, a);
      if ((overlapA.to - overlapA.from) * a.length < .1 || (overlapB.to - overlapB.from) * b.length < .1) continue;
      a.cuts.push(overlapA.from, overlapA.to); a.overlaps.push(overlapA);
      b.cuts.push(overlapB.from, overlapB.to); b.overlaps.push(overlapB);
    }
  }
  const bands: (RouteBand & { chain: number })[] = [];
  for (const segment of segments) {
    const cuts = segment.cuts.sort((a, b) => a - b).filter((value, i, all) => !i || value - all[i - 1] > EPSILON);
    for (let i = 1; i < cuts.length; i++) {
      const from = cuts[i - 1], to = cuts[i], middle = (from + to) / 2;
      const shared = [...new Set([segment.leg, ...segment.overlaps.filter((o) => middle > o.from - EPSILON && middle < o.to + EPSILON).map((o) => o.leg)])].sort((a, b) => a - b);
      // The earliest traversal owns the centre line and the lane orientation.
      // Reverse traversals use the same bands instead of painting over them.
      if (shared[0] !== segment.leg) continue;
      const a = lerp(segment.a, segment.b, from), b = lerp(segment.a, segment.b, to), previous = bands.at(-1);
      if (previous && previous.legs.join() === shared.join() && Math.hypot(previous.path.at(-1)!.lat - a.lat, previous.path.at(-1)!.lng - a.lng) < 1e-9) previous.path.push(b);
      else bands.push({ legs: shared, path: [a, b], chain: segment.chain });
    }
  }
  return bands.map(({ legs, path }) => ({ legs, path }));
}

// Offset only within the route stroke. Limit sharp-corner mitres to avoid the
// arrow-like spikes that appear when thick paths reverse direction.
export function offsetRouteBand(path: XY[], offset: number): XY[] {
  const points = path.filter((p, i) => !i || Math.hypot(p.x - path[i - 1].x, p.y - path[i - 1].y) > .001);
  if (points.length < 2 || offset === 0) return points;
  const normals = points.slice(1).map((p, i) => {
    const dx = p.x - points[i].x, dy = p.y - points[i].y, length = Math.hypot(dx, dy);
    return { x: -dy / length, y: dx / length };
  });
  return points.map((point, i) => {
    const before = normals[Math.max(0, i - 1)], after = normals[Math.min(i, normals.length - 1)];
    const denominator = 1 + before.x * after.x + before.y * after.y;
    let x = after.x * offset, y = after.y * offset;
    if (denominator > .1) {
      x = (before.x + after.x) * offset / denominator;
      y = (before.y + after.y) * offset / denominator;
      const ratio = Math.min(1, Math.abs(offset) * 2 / Math.max(.001, Math.hypot(x, y)));
      x *= ratio; y *= ratio;
    }
    return { x: point.x + x, y: point.y + y };
  });
}

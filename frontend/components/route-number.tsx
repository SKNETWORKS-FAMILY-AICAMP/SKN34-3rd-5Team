"use client";

import { useRouteNumber } from "@/lib/route-number";
import type { TripRoute } from "@/lib/routes";

export function RouteNumber({ route }: { route: TripRoute }) {
  const number = useRouteNumber(route.id, route.routeNumber);
  return <span aria-label={`루트 번호 ${number}`}>{number}</span>;
}

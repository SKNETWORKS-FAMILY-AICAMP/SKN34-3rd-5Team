"use client";

import Image from "next/image";
import Link from "next/link";
import { type TripRoute, useLikedRoutes, useRouteViews } from "@/lib/routes";
import { withCourseStart } from "@/lib/drawn-course";

export function formatRouteDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "날짜 미정" : new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: "Asia/Seoul" }).format(date);
}

function stadiumTeam(stadium: string) {
  const teams: [string, string][] = [["잠실", "LG · 두산"], ["고척", "키움"], ["인천", "SSG"], ["수원", "KT"], ["대전", "한화"], ["대구", "삼성"], ["광주", "KIA"], ["사직", "롯데"], ["창원", "NC"]];
  return teams.find(([name]) => stadium.includes(name))?.[1] ?? "KBO";
}

export function RouteCard({ route }: { route: TripRoute }) {
  const liked = useLikedRoutes().includes(route.id);
  const views = useRouteViews();
  const stops = withCourseStart(route.stops, route.start);
  return (
    <article className="route-card">
      <Link href={`/routes/${encodeURIComponent(route.id)}`} className="route-card-link">
        <div className="route-card-image">
          <Image src={route.cover.startsWith("/images/") ? route.cover : "/images/stadium-night.jpg"} alt="야구장 분위기 이미지" fill sizes="(max-width: 767px) 100vw, (max-width: 1023px) 50vw, 33vw" />
          <span className="route-card-sample">{route.isSample ? "샘플 코스" : "내가 만든 코스"}</span>
          <div className="route-card-image-caption"><span>{route.duration}</span><span>{stops.length}개 장소</span></div>
        </div>
        <div className="route-card-content">
          <div className="route-card-badges"><span className="route-stadium-pill">{route.stadium}</span><span className="route-team-badge">{stadiumTeam(route.stadium)}</span></div>
          <h3>{route.title}</h3>
          <p className="route-card-stops">{stops.map(stop => stop.name).join(" → ")}</p>
          <div className="route-card-tags">{route.tags.slice(0, 3).map(tag => <span key={tag}>#{tag}</span>)}</div>
          <div className="route-card-footer">
            <span className="route-card-author"><span className="route-avatar" aria-hidden="true">{route.isSample ? "K" : "나"}</span><span>{route.author}<time dateTime={route.createdAt}>{formatRouteDate(route.createdAt)}</time></span></span>
            <div className="route-card-metrics"><span className={liked ? "route-card-like is-liked" : "route-card-like"} aria-label={`좋아요 ${route.likes + Number(liked)}개`}><svg viewBox="0 0 24 24" fill={liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /></svg>{route.likes + Number(liked)}</span><span className="route-card-views" aria-label={`이 브라우저 조회 ${(route.views ?? 0) + (views[route.id] ?? 0)}회`}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M2 12s3.7-7 10-7 10 7 10 7-3.7 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>{(route.views ?? 0) + (views[route.id] ?? 0)}</span></div>
          </div>
        </div>
      </Link>
    </article>
  );
}

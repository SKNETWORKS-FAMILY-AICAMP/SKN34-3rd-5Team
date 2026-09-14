"use client";

import { useEffect, useState } from "react";
import type { KboGame } from "@/lib/kbo/types";

const venues: [string, string[]][] = [["JAMSIL", ["잠실"]], ["GOCHEOK", ["고척"]], ["MUNHAK", ["문학", "인천", "랜더스"]], ["SUWON", ["수원", "위즈"]], ["DAEJEON", ["대전", "한화생명"]], ["DAEGU", ["대구", "라이온즈"]], ["GWANGJU", ["광주", "챔피언스"]], ["SAJIK", ["사직"]], ["CHANGWON", ["창원", "NC파크"]]];
type Weather = { label: string; temperature: number; issuedAt: string; forecastDate: string; forecastTime: string };
export function GameWeather({ game }: { game: KboGame }) {
  const stadium = venues.find(([, aliases]) => aliases.some(alias => game.stadium.includes(alias)))?.[0];
  const query = new URLSearchParams({ stadium: stadium ?? "", date: game.date, time: game.time }).toString();
  const [result, setResult] = useState<{ query: string; weather: Weather | null } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => fetch(`/weather-api?${query}`, { signal: controller.signal }).then(response => response.json()).then(body => { if (!controller.signal.aborted) setResult({ query, weather: body.weather ?? null }); }).catch(() => { if (!controller.signal.aborted) setResult({ query, weather: null }); });
    refresh(); const timer = setInterval(refresh, 600000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [query]);
  const weather = result?.query === query ? result.weather : null;
  return <span className="game-weather" title={weather ? `기상청 · ${weather.issuedAt} 발표 · ${weather.forecastDate} ${weather.forecastTime} 예보${stadium === "GOCHEOK" ? " (구장 외부 날씨)" : ""}` : "해당 경기 시간의 예보를 확인하지 못했어요."}><span>{weather?.label ?? (result?.query === query ? "날씨 정보 없음" : "날씨 확인 중")}</span><span>{weather ? `${weather.temperature}°C` : "—"}</span></span>;
}

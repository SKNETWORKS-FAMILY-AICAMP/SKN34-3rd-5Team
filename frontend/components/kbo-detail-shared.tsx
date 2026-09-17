"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { TeamLogo } from "./team-logo";

export const kboTeams = [
  { code: "SS", name: "삼성" },
  { code: "KT", name: "KT" },
  { code: "LG", name: "LG" },
  { code: "HT", name: "KIA" },
  { code: "OB", name: "두산" },
  { code: "NC", name: "NC" },
  { code: "HH", name: "한화" },
  { code: "LT", name: "롯데" },
  { code: "SK", name: "SSG" },
  { code: "WO", name: "키움" },
] as const;

export function DetailTeamMark({ code, name }: { code: string; name: string }) {
  return <TeamLogo code={code} name={name} className="kbo-detail-team-mark" />;
}

export function koreaToday() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function detailDate(date: string, includeYear = false) {
  const value = new Date(`${date}T12:00:00+09:00`);
  if (!Number.isFinite(value.getTime())) return date;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", year: includeYear ? "numeric" : undefined, month: "long", day: "numeric", weekday: "long",
  }).format(value);
}

export function detailCheckedAt(date: string) {
  const value = new Date(date);
  if (!Number.isFinite(value.getTime())) return date;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(value);
}

type ResourceState<T> = { url: string; data: T | null; error: boolean; pending: boolean };

export function useKboResource<T>(url: string, pollMs: number | ((data: T | null) => number) = 0) {
  const [state, setState] = useState<ResourceState<T>>({ url: "", data: null, error: false, pending: true });
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let disposed = false;
    let request: AbortController | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const visible = () => document.visibilityState !== "hidden";

    const load = async () => {
      if (disposed || !visible() || request) return;
      const controller = new AbortController();
      request = controller;
      let timedOut = false;
      let nextPoll = typeof pollMs === "number" ? pollMs : pollMs(null);
      const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 65_000);
      try {
        const response = await fetch(url, { cache: "no-store", signal: controller.signal });
        const result: { data: T | null; error: string | null } = await response.json();
        if (!response.ok || !result.data) throw new Error("KBO data unavailable");
        nextPoll = typeof pollMs === "number" ? pollMs : pollMs(result.data);
        if (!disposed && !controller.signal.aborted) setState({ url, data: result.data, error: false, pending: false });
      } catch {
        if (!disposed && (timedOut || !controller.signal.aborted)) {
          setState(previous => ({ url, data: previous.url === url ? previous.data : null, error: true, pending: false }));
        }
      } finally {
        clearTimeout(timeout);
        if (request === controller) {
          request = null;
          if (!disposed && visible() && nextPoll > 0) timer = setTimeout(load, nextPoll);
        }
      }
    };

    const onVisibility = () => {
      clearTimeout(timer);
      if (!visible()) request?.abort();
      else {
        if (request?.signal.aborted) request = null;
        void load();
      }
    };

    void load();
    document.addEventListener("visibilitychange", onVisibility);
    return () => { disposed = true; clearTimeout(timer); request?.abort(); document.removeEventListener("visibilitychange", onVisibility); };
  }, [url, pollMs, revision]);

  const refresh = () => {
    setState(previous => ({ ...previous, pending: true, error: previous.data ? previous.error : false }));
    setRevision(value => value + 1);
  };

  return {
    data: state.url === url ? state.data : null,
    error: state.url === url && state.error,
    loading: state.url !== url || (!state.data && state.pending),
    refreshing: state.url === url && state.pending,
    refresh,
  };
}

export function KboDetailHeading({ active }: { active: "schedule" | "standings" | "highlights" }) {
  const copy = {
    schedule: { eyebrow: "EVERY GAME, EVERY MOMENT", title: "경기 일정", intro: "응원하는 팀의 다음 경기부터, 지난 경기의 결과까지." },
    standings: { eyebrow: "THE SEASON AT A GLANCE", title: "순위·기록", intro: "열 팀이 만들어가는 시즌, 순위와 기록으로 만나보세요." },
    highlights: { eyebrow: "KBO LEAGUE HIGHLIGHTS", title: "KBO 리그 H/L", intro: "KBO 공식 채널의 최근 경기를 큰 화면으로 다시 만나보세요." },
  }[active];
  return <>
    <div className="kbo-detail-heading">
      <Link href="/" className="kbo-detail-back"><span aria-hidden="true">←</span> 메인으로</Link>
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p className="kbo-detail-intro">{copy.intro}</p>
    </div>
    <nav className="kbo-detail-tabs" aria-label="KBO 경기 정보">
      <Link href="/schedule" aria-current={active === "schedule" ? "page" : undefined}>경기 일정</Link>
      <Link href="/standings" aria-current={active === "standings" ? "page" : undefined}>순위·기록</Link>
      <Link href="/highlights" aria-current={active === "highlights" ? "page" : undefined}>KBO 리그 H/L</Link>
    </nav>
  </>;
}

export function KboDetailSource({ source, fetchedAt, sourceUpdatedAt }: {
  source: { name: string; url: string }; fetchedAt: string; sourceUpdatedAt?: string | null;
}) {
  return <div className="kbo-detail-source">
    <a href={source.url} target="_blank" rel="noreferrer">출처 {source.name} <span aria-hidden="true">↗</span><span className="sr-only"> 새 창</span></a>
    <div>{sourceUpdatedAt && <p>출처 갱신 시각 {detailCheckedAt(sourceUpdatedAt)}</p>}
      <p>마지막 확인 <time dateTime={fetchedAt}>{detailCheckedAt(fetchedAt)}</time> · 한국시간</p></div>
  </div>;
}

export function KboDetailWarning({ pending, onRetry, text = "최신 정보를 확인하지 못해 마지막으로 확인한 자료를 보여드려요." }: {
  pending: boolean; onRetry: () => void; text?: string;
}) {
  return <div className="kbo-detail-warning" role="status"><p>{text}</p><button type="button" disabled={pending} onClick={onRetry}>{pending ? "확인 중…" : "다시 확인"}</button></div>;
}

export function KboDetailEmpty({ title, description, retry, pending = false }: {
  title: string; description: string; retry?: () => void; pending?: boolean;
}) {
  return <div className="kbo-detail-empty" role="status"><Icon name="stadium" size={35} /><strong>{title}</strong><p>{description}</p>
    {retry && <button type="button" className="button button-secondary" disabled={pending} onClick={retry}>{pending ? "확인 중…" : "다시 불러오기"}</button>}
  </div>;
}

export function KboDetailLoading({ label, rows = 5 }: { label: string; rows?: number }) {
  return <div className="kbo-detail-loading" role="status"><span className="sr-only">{label}</span>
    {Array.from({ length: rows }, (_, index) => <div key={index} aria-hidden="true"><i /><span /><span /></div>)}
  </div>;
}

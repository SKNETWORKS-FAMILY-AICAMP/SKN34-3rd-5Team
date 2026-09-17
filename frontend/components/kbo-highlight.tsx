"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import type { KboHighlight, KboHighlightApiResponse } from "@/lib/youtube/types";
import { formatHighlightRelativeTime, formatHighlightViews } from "@/lib/youtube/format";
import { YouTubeVideoPlayer } from "@/components/youtube-video-player";

const KBO_CHANNEL_URL = "https://www.youtube.com/@KBO1982";

export function KboHighlightSection() {
  const [highlights, setHighlights] = useState<KboHighlight[]>([]);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [previewVideoId, setPreviewVideoId] = useState<string | null>(null);
  const [loadedPreviews, setLoadedPreviews] = useState<string[]>([]);

  function startPreview(videoId: string) {
    setLoadedPreviews(current => current.includes(videoId) ? current : [...current, videoId]);
    setPreviewVideoId(videoId);
  }

  function stopPreview(videoId: string) {
    setPreviewVideoId(current => current === videoId ? null : current);
  }

  useEffect(() => {
    const request = new AbortController();
    const load = async () => {
      try {
        const response = await fetch("/youtube-api", { cache: "no-store", signal: request.signal });
        const result: KboHighlightApiResponse = await response.json();
        if (!response.ok || !result.data.length) throw new Error(result.error || "YouTube highlights unavailable");
        setHighlights(result.data);
        setError(false);
      } catch {
        if (!request.signal.aborted) setError(true);
      }
    };
    void load();
    return () => request.abort();
  }, [revision]);

  useEffect(() => {
    const stopHiddenPreview = () => {
      if (document.hidden) setPreviewVideoId(null);
    };
    document.addEventListener("visibilitychange", stopHiddenPreview);
    return () => document.removeEventListener("visibilitychange", stopHiddenPreview);
  }, []);

  return (
    <section className="home-highlight-section" aria-labelledby="highlight-heading">
      <div className="container">
        <div className="highlight-heading-row">
          <h2 id="highlight-heading">2026 KBO 리그 H/L</h2>
          <Link className="highlight-channel-link" href="/highlights"><span aria-hidden="true">▶</span> 전체 보기</Link>
        </div>

        {!highlights.length && !error ? (
          <div className="highlight-grid highlight-grid-loading" role="status"><span className="sr-only">최신 경기 하이라이트를 불러오고 있어요.</span>{[0, 1, 2].map(index => <div className="highlight-card-skeleton" key={index}><div /><span /><span /></div>)}</div>
        ) : highlights.length ? (
          <div className="highlight-grid" aria-label="최근 KBO 경기 하이라이트 3개">
            {highlights.map(highlight => (
              <Link className={`highlight-card${previewVideoId === highlight.videoId ? " is-previewing" : ""}`} href={`/highlights?video=${encodeURIComponent(highlight.videoId)}`} key={highlight.videoId} aria-label={`${highlight.title}, 크게 재생하기`} onPointerEnter={event => { if (event.pointerType === "mouse") startPreview(highlight.videoId); }} onPointerLeave={() => stopPreview(highlight.videoId)} onFocus={event => { if (event.currentTarget.matches(":focus-visible")) startPreview(highlight.videoId); }} onBlur={() => stopPreview(highlight.videoId)}>
                <span className="highlight-thumbnail">
                  <Image src={highlight.thumbnailUrl} alt="" fill sizes="(max-width: 760px) 78vw, 33vw" unoptimized />
                  {loadedPreviews.includes(highlight.videoId) && <span className="highlight-hover-preview" aria-hidden="true"><YouTubeVideoPlayer videoId={highlight.videoId} title={highlight.title} active={previewVideoId === highlight.videoId} preview /></span>}
                  {highlight.duration && previewVideoId !== highlight.videoId && <span className="highlight-duration">{highlight.duration}</span>}
                </span>
                <span className="highlight-card-copy">
                  <span className="highlight-title-line"><strong>{highlight.title}</strong><i aria-hidden="true">⋮</i></span>
                  <span className="highlight-channel">{highlight.channelTitle} <i aria-label="공식 채널">✓</i></span>
                  <span className="highlight-card-meta">{formatHighlightViews(highlight.viewCount) && <span>{formatHighlightViews(highlight.viewCount)}</span>}<time dateTime={highlight.publishedAt}>{formatHighlightRelativeTime(highlight.publishedAt)}</time>{highlight.stale && <span>마지막 확인</span>}</span>
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="highlight-error" role="status"><div><strong>최신 하이라이트를 불러오지 못했어요.</strong><p>KBO 공식 유튜브 채널에서는 바로 확인할 수 있어요.</p></div><button type="button" onClick={() => { setError(false); setRevision(value => value + 1); }}>다시 확인</button><a href={KBO_CHANNEL_URL} target="_blank" rel="noopener noreferrer">채널 열기 ↗</a></div>
        )}
      </div>
    </section>
  );
}

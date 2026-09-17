"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { KboDetailHeading } from "@/components/kbo-detail-shared";
import { YouTubeVideoPlayer } from "@/components/youtube-video-player";
import { formatHighlightPublishedAt, formatHighlightRelativeTime, formatHighlightViews } from "@/lib/youtube/format";
import type { KboHighlight, KboHighlightApiResponse } from "@/lib/youtube/types";

const KBO_CHANNEL_URL = "https://www.youtube.com/@KBO1982";

export function KboHighlightBoard({ initialVideoId }: { initialVideoId: string }) {
  const [highlights, setHighlights] = useState<KboHighlight[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState(initialVideoId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const playerSection = useRef<HTMLElement>(null);
  const selected = highlights.find(item => item.videoId === selectedVideoId) ?? highlights[0] ?? null;

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch("/youtube-api?limit=12", { cache: "no-store", signal: controller.signal });
        const result: KboHighlightApiResponse = await response.json();
        if (!response.ok || !result.data.length) throw new Error(result.error || "YouTube highlights unavailable");
        setHighlights(result.data);
        setSelectedVideoId(current => result.data.some(item => item.videoId === current) ? current : result.data[0].videoId);
        setError(false);
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    return () => controller.abort();
  }, [revision]);

  function selectVideo(videoId: string) {
    setSelectedVideoId(videoId);
    window.history.replaceState(null, "", `/highlights?video=${encodeURIComponent(videoId)}`);
    requestAnimationFrame(() => {
      playerSection.current?.focus({ preventScroll: true });
      playerSection.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }

  return (
    <main className="container kbo-detail-page highlight-board-page">
      <KboDetailHeading active="highlights" />
      <div className="highlight-board-body">
        {loading && !selected ? (
          <div className="highlight-board-loading" role="status"><span className="sr-only">KBO 하이라이트 게시판을 불러오고 있어요.</span><div /><span /><span /></div>
        ) : selected ? (
          <>
            <section className="highlight-feature-player" ref={playerSection} tabIndex={-1} aria-labelledby="selected-highlight-heading">
              <div className="highlight-board-player">
                <YouTubeVideoPlayer key={selected.videoId} videoId={selected.videoId} title={selected.title} />
              </div>
              <div className="highlight-board-info">
                <h2 id="selected-highlight-heading">{selected.title}</h2>
                <div className="highlight-board-meta"><strong>{selected.channelTitle} <i aria-label="공식 채널">✓</i></strong>{formatHighlightViews(selected.viewCount) && <span>{formatHighlightViews(selected.viewCount)}</span>}<time dateTime={selected.publishedAt}>{formatHighlightPublishedAt(selected.publishedAt)}</time></div>
                <a href={selected.watchUrl} target="_blank" rel="noopener noreferrer">YouTube에서 보기 <span aria-hidden="true">↗</span></a>
              </div>
            </section>

            <section className="highlight-library" aria-labelledby="highlight-library-heading">
              <div className="highlight-library-heading"><div><p className="eyebrow">RECENT VIDEOS</p><h2 id="highlight-library-heading">최근 경기 하이라이트</h2></div><a href={KBO_CHANNEL_URL} target="_blank" rel="noopener noreferrer">KBO 공식 채널 <span aria-hidden="true">↗</span></a></div>
              <div className="highlight-library-grid">
                {highlights.map(highlight => (
                  <button type="button" className="highlight-library-card" aria-pressed={highlight.videoId === selected.videoId} onClick={() => selectVideo(highlight.videoId)} key={highlight.videoId}>
                    <span className="highlight-library-thumbnail"><Image src={highlight.thumbnailUrl} alt="" fill sizes="(max-width: 640px) 44vw, (max-width: 900px) 30vw, 25vw" unoptimized />{highlight.duration && <span>{highlight.duration}</span>}</span>
                    <span className="highlight-library-copy"><strong>{highlight.title}</strong><span>{highlight.channelTitle} · {formatHighlightViews(highlight.viewCount) ?? formatHighlightRelativeTime(highlight.publishedAt)}</span></span>
                  </button>
                ))}
              </div>
            </section>
          </>
        ) : (
          <div className="highlight-board-error" role="status"><strong>하이라이트 영상을 불러오지 못했어요.</strong><p>KBO 공식 채널에서 영상을 확인하거나 다시 불러와 주세요.</p><div><button type="button" onClick={() => { setError(false); setRevision(value => value + 1); }}>다시 불러오기</button><a href={KBO_CHANNEL_URL} target="_blank" rel="noopener noreferrer">공식 채널 열기</a></div></div>
        )}
        {error && selected && <div className="highlight-board-warning" role="status">최신 목록을 확인하지 못해 마지막으로 불러온 영상을 보여드려요.</div>}
      </div>
    </main>
  );
}

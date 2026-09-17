export type KboHighlight = {
  videoId: string;
  title: string;
  publishedAt: string;
  channelTitle: string;
  watchUrl: string;
  thumbnailUrl: string;
  duration: string | null;
  viewCount: number | null;
  fetchedAt: string;
  stale: boolean;
};

export type KboHighlightApiResponse = {
  data: KboHighlight[];
  error: string | null;
};

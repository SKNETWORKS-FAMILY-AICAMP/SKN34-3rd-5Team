export type YouTubePlayer = {
  mute: () => void;
  playVideo: () => void;
  pauseVideo: () => void;
  destroy: () => void;
};

type YouTubePlayerEvent = { target: YouTubePlayer };

export type YouTubePlayerApi = {
  Player: new (element: HTMLElement, options: {
    videoId?: string;
    width?: number | string;
    height?: number | string;
    playerVars?: Record<string, number | string>;
    events?: {
      onReady?: (event: YouTubePlayerEvent) => void;
      onStateChange?: (event: YouTubePlayerEvent & { data: number }) => void;
      onError?: (event: YouTubePlayerEvent & { data: number }) => void;
      onAutoplayBlocked?: (event: YouTubePlayerEvent) => void;
    };
  }) => YouTubePlayer;
};

declare global {
  interface Window {
    YT?: YouTubePlayerApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let iframeApiPromise: Promise<YouTubePlayerApi> | null = null;

export function loadYouTubeIframeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (iframeApiPromise) return iframeApiPromise;

  iframeApiPromise = new Promise<YouTubePlayerApi>((resolve, reject) => {
    const previousReady = window.onYouTubeIframeAPIReady;
    const script = document.createElement("script");
    const cleanup = () => {
      window.clearTimeout(timeout);
      if (window.onYouTubeIframeAPIReady === ready) window.onYouTubeIframeAPIReady = previousReady;
    };
    const fail = () => {
      cleanup();
      script.remove();
      reject(new Error("YouTube iframe API failed to load"));
    };
    const ready = () => {
      cleanup();
      if (window.YT?.Player) resolve(window.YT);
      else fail();
      previousReady?.();
    };
    const timeout = window.setTimeout(fail, 15_000);
    window.onYouTubeIframeAPIReady = ready;
    script.src = "https://www.youtube.com/iframe_api";
    script.async = true;
    script.addEventListener("error", fail, { once: true });
    document.head.appendChild(script);
  }).catch(error => {
    iframeApiPromise = null;
    throw error;
  });

  return iframeApiPromise;
}

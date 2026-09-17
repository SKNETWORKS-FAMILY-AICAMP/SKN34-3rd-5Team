import "server-only";
import { ChatError } from "./chat/validation";

export function teamBackendUrl(path: string, configuredBase = process.env.CHAT_BACKEND_URL) {
  const base = configuredBase?.trim();
  if (!base) throw new ChatError("팀 백엔드 주소가 설정되지 않았어요.", 503);
  const url = new URL(base.endsWith("/") ? base : `${base}/`);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new ChatError("팀 백엔드 주소 설정을 확인해 주세요.", 503);
  return new URL(path, url);
}

export function checkSameOrigin(request: Request) {
  const configured = process.env.APP_ORIGIN?.trim();
  let expectedOrigin = new URL(request.url).origin;
  if (configured) {
    // Docker/proxies may expose a different origin; never trust forwarded request headers here.
    let url: URL;
    try { url = new URL(configured); } catch { throw new ChatError("서비스 주소 설정을 확인해 주세요.", 503); }
    if (!["http:", "https:"].includes(url.protocol) || configured !== url.origin) throw new ChatError("서비스 주소 설정을 확인해 주세요.", 503);
    expectedOrigin = url.origin;
  }
  const origin = request.headers.get("origin");
  if ((origin && origin !== expectedOrigin) || request.headers.get("sec-fetch-site") === "cross-site") throw new ChatError("같은 사이트에서 요청해 주세요.", 403);
}

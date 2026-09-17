export function formatHighlightPublishedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "최근 공개";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatHighlightViews(value: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  if (value >= 100_000_000) return `조회수 ${(value / 100_000_000).toFixed(value >= 1_000_000_000 ? 0 : 1).replace(".0", "")}억회`;
  if (value >= 10_000) return `조회수 ${(value / 10_000).toFixed(value >= 100_000 ? 0 : 1).replace(".0", "")}만회`;
  if (value >= 1_000) return `조회수 ${(value / 1_000).toFixed(1).replace(".0", "")}천회`;
  return `조회수 ${value.toLocaleString("ko-KR")}회`;
}

export function formatHighlightRelativeTime(value: string) {
  const published = new Date(value).getTime();
  if (!Number.isFinite(published)) return "최근 공개";
  const elapsed = Math.max(0, Date.now() - published);
  const hours = Math.floor(elapsed / 3_600_000);
  if (hours < 1) return `${Math.max(1, Math.floor(elapsed / 60_000))}분 전`;
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}일 전`;
  return formatHighlightPublishedAt(value);
}

export type RouteContentFormat = "html" | undefined;

/** Legacy routes contain plain text. Only explicitly marked editor data is HTML. */
export function routeContentToText(content: string, format?: RouteContentFormat): string {
  if (format !== "html") return content;
  return content
    .replace(/<(script|style|iframe|object)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, "")
    .replace(/<\/(?:p|h[1-6]|blockquote)>/gi, "\n\n")
    .replace(/<br\s*\/?\s*>|<\/(?:div|li|tr)>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&(?:nbsp|amp|lt|gt|quot|apos|#39|#x27);/gi, (entity) => ({
      "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'", "&#39;": "'", "&#x27;": "'",
    }[entity.toLowerCase()] ?? entity))
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function plainTextToHtml(text: string): string {
  if (!text.trim()) return "";
  const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  return escaped.split(/\n\n+/).map((paragraph) => `<p>${paragraph.replace(/\n/g, "<br>")}</p>`).join("");
}

export function safeRouteLink(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ["https:", "http:", "mailto:"].includes(url.protocol) && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}

export type ShareOutcome = "shared" | "copied" | "manual" | "cancelled";

function legacyCopy(text: string): boolean {
  const active = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const field = document.createElement("textarea");
  field.value = text;
  field.readOnly = true;
  field.setAttribute("aria-hidden", "true");
  Object.assign(field.style, { position: "fixed", inset: "0 auto auto -9999px", opacity: "0" });
  document.body.appendChild(field);
  field.focus();
  field.select();
  field.setSelectionRange(0, field.value.length);
  let copied = false;
  try { copied = document.execCommand("copy"); } catch { copied = false; }
  field.remove();
  active?.focus({ preventScroll: true });
  return copied;
}

/** Uses native share/clipboard on HTTPS and a user-gesture copy fallback on HTTP. */
export async function shareOrCopy(data: ShareData, copyText: string): Promise<ShareOutcome> {
  if (window.isSecureContext && typeof navigator.share === "function" && (!navigator.canShare || navigator.canShare(data))) {
    try {
      await navigator.share(data);
      return "shared";
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return "cancelled";
    }
  }
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(copyText);
      return "copied";
    } catch { /* Continue with the HTTP-compatible selection copy. */ }
  }
  return legacyCopy(copyText) ? "copied" : "manual";
}

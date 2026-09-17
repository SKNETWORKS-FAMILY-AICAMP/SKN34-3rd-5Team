let fallbackCounter = 0;

const hex = (value: number) => value.toString(16).padStart(2, "0");

/**
 * Creates a local UI identifier without crypto.randomUUID().
 * getRandomValues() works on ordinary HTTP pages; the fallback is only for
 * older browsers and is never used for authentication or secrets.
 */
export function createClientId(): string {
  const bytes = new Uint8Array(16);
  const source = globalThis.crypto;
  if (source?.getRandomValues) {
    source.getRandomValues(bytes);
  } else {
    fallbackCounter = (fallbackCounter + 1) >>> 0;
    const seed = `${Date.now()}:${fallbackCounter}:${Math.random()}`;
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = (seed.charCodeAt(index % seed.length) + index * 37 + fallbackCounter) & 0xff;
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const parts = Array.from(bytes, hex);
  return `${parts.slice(0, 4).join("")}-${parts.slice(4, 6).join("")}-${parts.slice(6, 8).join("")}-${parts.slice(8, 10).join("")}-${parts.slice(10).join("")}`;
}

import "server-only";
import { createHash, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";

const directory = path.join(process.cwd(), ".member-preview");
const file = path.join(directory, "credentials.json");
export function previewCredentialsEnabled() {
  return process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_MEMBER_PREVIEW === "true";
}
export async function verifyPreviewPassword(password: string) {
  try {
    const stored = JSON.parse(await readFile(file, "utf8"));
    if (stored.username !== process.env.MEMBER_PREVIEW_USERNAME) return false;
    const expected = Buffer.from(stored.hash, "hex");
    const actual = scryptSync(password, stored.salt, 64);
    return expected.length === actual.length && timingSafeEqual(expected, actual);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const expected = process.env.MEMBER_PREVIEW_PASSWORD;
    if (!expected) return false;
    const digest = (value: string) => createHash("sha256").update(value).digest();
    return timingSafeEqual(digest(password), digest(expected));
  }
}
export async function changePreviewPassword(password: string) {
  const salt = randomBytes(32).toString("hex");
  await mkdir(directory, { recursive: true });
  await writeFile(file, JSON.stringify({ username: process.env.MEMBER_PREVIEW_USERNAME, salt, hash: scryptSync(password, salt, 64).toString("hex") }), { mode: 0o600 });
}

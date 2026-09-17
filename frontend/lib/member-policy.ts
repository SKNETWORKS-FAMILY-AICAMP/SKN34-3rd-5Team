import type { MemberUser } from "./api/auth";

export const memberRoleLabel = (user: Pick<MemberUser, "is_superuser" | "is_staff">) =>
  user.is_superuser ? "마스터 관리자" : user.is_staff ? "운영 관리자" : "일반 회원";

export type MemberLevel = 1 | 2 | 3;
export function memberLevelForPoints(points: number): MemberLevel {
  if (!Number.isSafeInteger(points) || points < 0) return 1;
  return points <= 500 ? 1 : points <= 1000 ? 2 : 3;
}
// Award amounts are pending team agreement; no automatic point grants yet.
export const POINT_SOURCES = ["attendance", "course_recommendation", "prediction"] as const;
export const MEMBER_LEVELS: Record<MemberLevel, { label: string; image: string }> = {
  1: { label: "1단계", image: "/images/member-levels/level-1.png" },
  2: { label: "2단계", image: "/images/member-levels/level-2.png" },
  3: { label: "3단계", image: "/images/member-levels/level-3.png" },
};

// Six calendar months in KST; clamp month-end dates (Aug 31 -> Feb 28/29).
export function nextNicknameChangeAt(changedAt: string | null): string | null {
  if (!changedAt || !Number.isFinite(Date.parse(changedAt))) return null;
  const date = new Date(Date.parse(changedAt) + 9 * 3600000);
  const day = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + 6);
  const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
  date.setUTCDate(Math.min(day, lastDay));
  return new Date(date.getTime() - 9 * 3600000).toISOString();
}

export function nicknameChangeTimestamp(previous: string, next: string, changedAt: string | null, now: Date): string | null {
  if (previous === next.trim()) return changedAt;
  const allowedAt = nextNicknameChangeAt(changedAt);
  if (allowedAt && now.getTime() < Date.parse(allowedAt)) throw new Error("닉네임은 변경 후 6개월이 지나야 다시 바꿀 수 있어요.");
  return now.toISOString();
}

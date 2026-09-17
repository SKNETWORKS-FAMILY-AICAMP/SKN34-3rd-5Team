export type CommunityVote = "up" | "down";

export function nextCommunityVote(current: CommunityVote | null, requested: CommunityVote) {
  return current === requested ? null : requested;
}

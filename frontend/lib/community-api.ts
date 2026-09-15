"use client";

import { useEffect, useSyncExternalStore } from "react";
import { teamBoards, type TeamCommunityPost } from "./team-community";

type CommunityState = { posts: TeamCommunityPost[]; loading: boolean; error: string };
const listeners = new Set<() => void>();
const teamCodes = new Set(teamBoards.map(team => team.code));
let state: CommunityState = { posts: [], loading: true, error: "" };
let request: Promise<void> | undefined;

function isPost(value: unknown): value is TeamCommunityPost {
  if (!value || typeof value !== "object") return false;
  const post = value as Record<string, unknown>;
  return typeof post.id === "string" && post.sourceId === post.id && /^\d{6}$/.test(String(post.postNumber))
    && (post.board === "free" || post.board === "teams")
    && typeof post.teamCode === "string" && (post.board === "free" ? post.teamCode === "" : teamCodes.has(post.teamCode as typeof teamBoards[number]["code"]))
    && ["author", "title", "content", "category"].every(field => typeof post[field] === "string")
    && (post.createdAt === null || typeof post.createdAt === "string")
    && ["views", "recommendations", "commentCount"].every(field => Number.isSafeInteger(post[field]) && Number(post[field]) >= 0)
    && typeof post.isSample === "boolean";
}

export async function fetchCommunityPosts(fetcher: typeof fetch = fetch): Promise<TeamCommunityPost[]> {
  const response = await fetcher("/api/community/posts/", { cache: "no-store", signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Community API ${response.status}`);
  const data: unknown = await response.json();
  if (!Array.isArray(data) || !data.every(isPost)) throw new Error("Invalid community response");
  return data;
}

function publish(next: CommunityState) {
  state = next;
  listeners.forEach(listener => listener());
}

export function retryCommunityPosts() {
  if (!request) {
    publish({ ...state, loading: true, error: "" });
    request = fetchCommunityPosts()
      .then(posts => publish({ posts, loading: false, error: "" }))
      .catch(() => publish({ ...state, loading: false, error: "게시글을 불러오지 못했어요." }))
      .finally(() => { request = undefined; });
  }
  return request;
}

const subscribe = (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener); };
const serverState: CommunityState = { posts: [], loading: true, error: "" };

export function useCommunityPosts(enabled = true) {
  useEffect(() => { if (enabled) void retryCommunityPosts(); }, [enabled]);
  return useSyncExternalStore(subscribe, () => state, () => serverState);
}

import { getCommunityCategoryGroup, type CommunityPostCategory } from "@/lib/community-post-category";

export function PostCategory({ category, freeBoard = false }: { category: CommunityPostCategory; freeBoard?: boolean }) {
  const [name, group] = getCommunityCategoryGroup(category);
  const color = freeBoard && category === "질문" ? "#d52a32" : freeBoard && category === "잡담" ? "#1455eb" : group.color;
  return <span data-category-group={name} style={{ color, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0 }}>[{category}]</span>;
}

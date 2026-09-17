export function PostCommentCount({ count }: { count?: number }) {
  if (!count || !Number.isInteger(count) || count < 1) return null;

  return <span aria-label={`댓글 ${count}개`} style={{ marginLeft: "0.35em", color: "#2563eb", fontSize: "0.9em", fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0 }}>({count})</span>;
}

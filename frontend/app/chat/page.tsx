import type { Metadata } from "next";
import { ChatWorkspace } from "@/components/chat-workspace";

export const metadata: Metadata = {
  title: "직관 도우미",
  description: "야구와 구장 이야기부터 나만의 직관 코스까지, 함께 준비하는 AI 대화.",
};

export default function ChatPage() {
  return <ChatWorkspace />;
}

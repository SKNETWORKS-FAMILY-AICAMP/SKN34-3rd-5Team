"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { markMessageRead, useMemberMessages } from "@/lib/member-messages";

export function MemberInbox() {
  const messages = useMemberMessages();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pathname = usePathname();
  const open = openedAt === pathname;
  const selected = messages.find(m => m.id === selectedId);
  const unread = messages.filter(m => !m.read).length;
  const root = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpenedAt(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpenedAt(null); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  return <div className="member-notifications" ref={root}>
    <button ref={trigger} className="notification-bell" type="button" aria-label={`받은 메시지, 읽지 않은 메시지 ${unread}개`} aria-expanded={open} aria-controls="member-inbox-panel" onClick={() => { setOpenedAt(open ? null : pathname); setSelectedId(null); setError(""); }}>
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>
      {unread > 0 && <span className="notification-count">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <section id="member-inbox-panel" className="notification-panel" aria-label="받은 메시지함">
      <header><strong>받은 메시지</strong>{selected && <button type="button" onClick={() => setSelectedId(null)}>목록으로</button>}</header>
      {selected ? <div className="inbox-detail"><strong>{selected.subject}</strong><small>{selected.sender} · {new Date(selected.createdAt).toLocaleDateString("ko-KR")}</small><p>{selected.body}</p></div> : messages.length ? <ul>{messages.map(m => <li key={m.id}><button type="button" className={m.read ? "" : "is-unread"} onClick={() => { setSelectedId(m.id); try { markMessageRead(m.id); setError(""); } catch { setError("읽음 상태를 저장하지 못했어요."); } }}><strong>{m.subject}</strong><small>{m.sender} · {m.read ? "읽음" : "읽지 않음"}</small></button></li>)}</ul> : <p>아직 받은 메시지가 없어요.</p>}
      {error && <p role="alert">{error}</p>}
    </section>}
  </div>;
}

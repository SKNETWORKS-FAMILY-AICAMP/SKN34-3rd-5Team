"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { markNoticesRead, useMemberSettings } from "@/lib/member-settings";
export function MemberNotifications() {
  const settings = useMemberSettings();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const [error, setError] = useState("");
  const pathname = usePathname();
  const open = openedAt === pathname;
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const unread = settings.notices.filter(n => !n.read).length;
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpenedAt(null); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpenedAt(null); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  function mark(id?: string) { try { markNoticesRead(id); setError(""); } catch { setError("읽음 상태를 저장하지 못했어요."); } }
  return <div className="member-notifications" ref={root}>
    <button ref={trigger} type="button" className="notification-bell" aria-label={`알림, 읽지 않은 알림 ${unread}개`} aria-expanded={open} aria-controls="member-notification-panel" onClick={() => setOpenedAt(open ? null : pathname)}>
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 20a3 3 0 0 0 6 0" /></svg>
      {unread > 0 && <span className="notification-count">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <section id="member-notification-panel" className="notification-panel" aria-label="알림 목록"><header><strong>알림</strong>{unread > 0 && <button type="button" onClick={() => mark()}>모두 읽음</button>}</header>
      {settings.notices.length ? <ul>{settings.notices.map(n => <li key={n.id}><button type="button" className={n.read ? "" : "is-unread"} onClick={() => mark(n.id)}>{n.text}<small>{n.read ? "읽음" : "읽지 않음"}</small></button></li>)}</ul> : <p>아직 받은 알림이 없어요.</p>}
      {error && <p role="alert">{error}</p>}
    </section>}
  </div>;
}

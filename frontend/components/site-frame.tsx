"use client";

import { usePathname } from "next/navigation";
import { SiteHeader, SiteFooter } from "./site-shell";
import { MobileNavigation } from "./mobile-navigation";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  const chatPage = usePathname() === "/chat";
  return (
    <div className={chatPage ? "app-frame app-frame-chat" : "app-frame"}>
      <a className="skip-link" href="#main-content">본문으로 바로가기</a>
      {!chatPage && <SiteHeader />}
      <div id="main-content" className="site-content">{children}</div>
      {!chatPage && <><SiteFooter /><MobileNavigation /></>}
    </div>
  );
}

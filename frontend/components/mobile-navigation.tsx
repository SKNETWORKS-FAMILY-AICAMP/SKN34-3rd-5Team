"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";

const items = [
  { href: "/", title: "홈", icon: "home" },
  { href: "/routes", title: "루트", icon: "route" },
  { href: "/routes/new", title: "작성", icon: "sparkles" },
  { href: "/stadiums", title: "구장", icon: "stadium" },
] as const;

export function MobileNavigation() {
  const pathname = usePathname();
  return <nav className="mobile-bottom-nav" aria-label="모바일 주요 메뉴">{items.map(item => {
    const active = item.href === "/routes" ? pathname.startsWith("/routes") && pathname !== "/routes/new" : pathname === item.href;
    return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}><Icon name={item.icon} size={21} /><span>{item.title}</span></Link>;
  })}</nav>;
}

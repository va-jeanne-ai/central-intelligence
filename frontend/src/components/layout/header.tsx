"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HeaderProps {
  title: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// ─── Main Header Component ────────────────────────────────────────────────────

// ─── Department-aware action button ──────────────────────────────────────────

interface ActionButton {
  href: string;
  label: string;
  icon: string;
  primary?: boolean;
}

function getActionButton(pathname: string): ActionButton {
  if (pathname === "/" || pathname === "/dashboard") {
    return { href: "/chat", label: "Ask Central Intelligence", icon: "👑", primary: true };
  }
  if (pathname.startsWith("/marketing") || pathname.startsWith("/ci-")) {
    return { href: "/marketing-director", label: "Marketing Director", icon: "📣" };
  }
  if (pathname.startsWith("/leads") || pathname.startsWith("/sales") || pathname.startsWith("/appointments")) {
    return { href: "/sales-director", label: "Sales Director", icon: "💼" };
  }
  if (pathname.startsWith("/members") || pathname.startsWith("/coaching") || pathname.startsWith("/accountability") || pathname.startsWith("/tech-sos")) {
    return { href: "/chat", label: "Fulfillment Director", icon: "🏆" };
  }
  return { href: "/chat", label: "Central Intelligence", icon: "👑" };
}

// ─── Main Header Component ────────────────────────────────────────────────────

export function Header({ title }: HeaderProps) {
  const pathname = usePathname();
  const today = formatDate(new Date());
  const action = getActionButton(pathname);

  return (
    <header className="flex items-center justify-between px-7 h-[60px] bg-white border-b border-gray-200 flex-shrink-0">
      {/* Page Title */}
      <h1 className="text-base font-semibold text-gray-900">{title}</h1>

      {/* Right Side */}
      <div className="flex items-center gap-4">
        {/* Current Date */}
        <span className="text-sm text-gray-400 hidden sm:block">{today}</span>

        {/* Context-Sensitive Action Button */}
        <Link
          href={action.href}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-150 hover:opacity-90 active:scale-95 ${
            action.primary
              ? "text-white"
              : "text-gray-600 bg-gray-100 hover:bg-gray-200"
          }`}
          style={action.primary ? { backgroundColor: "#6366F1" } : undefined}
        >
          <span className="text-base leading-none">{action.icon}</span>
          {action.label}
        </Link>
      </div>
    </header>
  );
}

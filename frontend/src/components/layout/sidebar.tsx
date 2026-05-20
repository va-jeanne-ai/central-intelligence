"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { APP_CONFIG } from "@/lib/config";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ────────────────────────────────────────────────────────────────────

type Department = "sales" | "fulfillment" | "marketing" | "admin" | "core";

interface NavItem {
  label: string;
  icon: string;
  href: string;
  department: Department;
}

interface NavSection {
  id: string;
  label: string;
  department: Department;
  items: NavItem[];
}

// ─── Navigation Definition ────────────────────────────────────────────────────

const TOP_NAV: NavItem[] = [
  { label: "Dashboard", icon: "📊", href: "/dashboard", department: "core" },
  { label: "Central Intelligence Chat", icon: "👑", href: "/chat", department: "core" },
];

const NAV_SECTIONS: NavSection[] = [
  {
    id: "sales",
    label: "Sales",
    department: "sales",
    items: [
      { label: "Leads", icon: "🧲", href: "/leads", department: "sales" },
      { label: "Sales Calls", icon: "📞", href: "/sales-calls", department: "sales" },
      { label: "Appointments", icon: "📅", href: "/appointments", department: "sales" },
    ],
  },
  {
    id: "fulfillment",
    label: "Fulfillment",
    department: "fulfillment",
    items: [
      { label: "Members", icon: "👥", href: "/members", department: "fulfillment" },
      { label: "Coaching Calls", icon: "🎯", href: "/coaching-calls", department: "fulfillment" },
      { label: "Accountability", icon: "✅", href: "/accountability", department: "fulfillment" },
      { label: "Tech SOS", icon: "🛠", href: "/tech-sos", department: "fulfillment" },
    ],
  },
  {
    id: "marketing",
    label: "Marketing",
    department: "marketing",
    items: [
      { label: "Marketing Overview", icon: "📊", href: "/marketing", department: "marketing" },
      { label: "Marketing Director", icon: "📣", href: "/marketing-director", department: "marketing" },
      { label: "CI Insights", icon: "🔍", href: "/ci-insights", department: "marketing" },
      { label: "Market Signals", icon: "📶", href: "/ci-market-signals", department: "marketing" },
      { label: "CI Transcripts", icon: "📋", href: "/ci-transcript-upload", department: "marketing" },
      { label: "Content Ideas", icon: "💡", href: "/ci-content-ideas", department: "marketing" },
      { label: "Social Media", icon: "📱", href: "/marketing/social", department: "marketing" },
      { label: "Email", icon: "✉", href: "/marketing/email", department: "marketing" },
      { label: "Funnels", icon: "📈", href: "/marketing/funnels", department: "marketing" },
      { label: "Ads", icon: "📢", href: "/marketing/ads", department: "marketing" },
      { label: "DM", icon: "💬", href: "/marketing/dm", department: "marketing" },
      { label: "Offers", icon: "🎁", href: "/marketing/offers", department: "marketing" },
      { label: "Promo Calendar", icon: "📅", href: "/marketing/promo-calendar", department: "marketing" },
    ],
  },
  {
    id: "admin",
    label: "Admin",
    department: "admin",
    items: [
      { label: "Data Import", icon: "📥", href: "/data-import", department: "admin" },
    ],
  },
];

// ─── Department Style Maps ─────────────────────────────────────────────────────

const SECTION_LABEL_CLASSES: Record<Department, string> = {
  sales: "text-blue-500",
  fulfillment: "text-orange-500",
  marketing: "text-emerald-500",
  admin: "text-gray-400",
  core: "text-gray-400",
};

const ACTIVE_ITEM_CLASSES: Record<Department, string> = {
  sales: "border-l-[3px] border-blue-500 bg-blue-50 text-blue-600",
  fulfillment: "border-l-[3px] border-orange-500 bg-orange-50 text-orange-600",
  marketing: "border-l-[3px] border-emerald-500 bg-emerald-50 text-emerald-600",
  admin: "border-l-[3px] border-gray-400 bg-gray-50 text-gray-700",
  core: "border-l-[3px] border-indigo-400 bg-indigo-50 text-indigo-700",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function NavLink({ item, isActive }: { item: NavItem; isActive: boolean }) {
  const activeClasses = ACTIVE_ITEM_CLASSES[item.department];
  const inactiveClasses = "border-l-[3px] border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-800";

  return (
    <Link
      href={item.href}
      className={`flex items-center gap-2.5 px-4 py-2 text-sm font-medium rounded-r-md transition-all duration-150 ${
        isActive ? activeClasses : inactiveClasses
      }`}
    >
      <span className="text-base leading-none">{item.icon}</span>
      <span>{item.label}</span>
    </Link>
  );
}

function SectionLabel({ section }: { section: NavSection }) {
  const colorClass = SECTION_LABEL_CLASSES[section.department];
  return (
    <div className={`px-4 pt-5 pb-1 text-[10px] font-bold tracking-widest uppercase ${colorClass}`}>
      {section.label}
    </div>
  );
}

// ─── User Footer ──────────────────────────────────────────────────────────────

function getInitials(nameOrEmail: string): string {
  // Try to build initials from a full name ("Jade Doe" → "JD").
  const parts = nameOrEmail.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  // Fall back to first two characters of the email local-part.
  return nameOrEmail.slice(0, 2).toUpperCase();
}

function UserFooter() {
  const { user, signOut } = useAuth();

  const displayName =
    user && "name" in user && user.name
      ? user.name
      : user?.email ?? "Unknown";

  const displayRole =
    user && "role" in user && user.role ? user.role : "User";

  const initials = getInitials(displayName);

  return (
    <div className="flex items-center gap-3 px-4 py-4 border-t border-gray-100 bg-gray-50">
      <div
        className="flex items-center justify-center w-8 h-8 rounded-full text-white text-xs font-bold flex-shrink-0"
        style={{ backgroundColor: "#6366F1" }}
        aria-label="User avatar"
      >
        {initials}
      </div>
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-sm font-semibold text-gray-800 truncate">
          {displayName}
        </span>
        <span className="text-xs text-gray-400 capitalize">{displayRole}</span>
      </div>
      <button
        type="button"
        onClick={() => void signOut()}
        aria-label="Sign out"
        className="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
        title="Sign out"
      >
        <LogOut size={15} aria-hidden="true" />
      </button>
    </div>
  );
}

// ─── Main Sidebar Component ───────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <aside className="flex flex-col w-[228px] h-screen bg-white border-r border-gray-200 overflow-y-auto overflow-x-hidden">
      {/* Logo Area */}
      <div className="flex flex-col px-5 pt-6 pb-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl leading-none">🧠</span>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-gray-900 leading-tight">
              {APP_CONFIG.name}
            </span>
            <span className="text-[10px] text-gray-400 font-medium tracking-wide">
              {APP_CONFIG.subtitle}
            </span>
          </div>
        </div>
      </div>

      {/* Top Nav — Dashboard & Central Intelligence Chat */}
      <nav className="pt-3 pb-1" aria-label="Main navigation">
        {TOP_NAV.map((item) => (
          <NavLink key={item.href} item={item} isActive={isActive(item.href)} />
        ))}
      </nav>

      {/* Sectioned Nav */}
      <nav className="flex-1 pb-3" aria-label="Department navigation">
        {NAV_SECTIONS.map((section) => (
          <div key={section.id}>
            <SectionLabel section={section} />
            {section.items.map((item) => (
              <NavLink key={item.href} item={item} isActive={isActive(item.href)} />
            ))}
          </div>
        ))}
      </nav>

      {/* User Footer — dynamic from auth context */}
      <UserFooter />
    </aside>
  );
}

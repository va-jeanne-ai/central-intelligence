"use client";

import { useMemo, useState } from "react";
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

/** A collapsible group of links nested inside a section. */
interface NavGroup {
  id: string;
  label: string;
  icon: string;
  department: Department;
  children: NavItem[];
}

/** A section's entries can be either a direct link or a nested group. */
type NavEntry = NavItem | NavGroup;

interface NavSection {
  id: string;
  label: string;
  department: Department;
  /** When true the whole section is collapsible via its label. */
  collapsible: boolean;
  entries: NavEntry[];
}

function isGroup(entry: NavEntry): entry is NavGroup {
  return (entry as NavGroup).children !== undefined;
}

// ─── Navigation Definition ────────────────────────────────────────────────────

const TOP_NAV: NavItem[] = [
  { label: "Dashboard", icon: "📊", href: "/dashboard", department: "core" },
  { label: "Central Intelligence Chat", icon: "👑", href: "/chat", department: "core" },
  { label: "Calendar", icon: "📅", href: "/calendar", department: "core" },
];

const NAV_SECTIONS: NavSection[] = [
  {
    id: "sales",
    label: "Sales",
    department: "sales",
    collapsible: true,
    entries: [
      { label: "Sales Overview", icon: "📊", href: "/sales", department: "sales" },
      { label: "Sales Director", icon: "💼", href: "/sales-director", department: "sales" },
      { label: "Leads", icon: "🧲", href: "/leads", department: "sales" },
      { label: "Sales Calls", icon: "📞", href: "/sales-calls", department: "sales" },
      { label: "All Calls", icon: "☎️", href: "/calls", department: "sales" },
      { label: "Appointments", icon: "📅", href: "/appointments", department: "sales" },
    ],
  },
  {
    id: "fulfillment",
    label: "Fulfillment",
    department: "fulfillment",
    collapsible: true,
    entries: [
      { label: "Fulfillment Overview", icon: "📊", href: "/fulfillment", department: "fulfillment" },
      { label: "Fulfillment Director", icon: "🏆", href: "/fulfillment-director", department: "fulfillment" },
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
    collapsible: true,
    entries: [
      // Standalone links first…
      { label: "Marketing Overview", icon: "📊", href: "/marketing", department: "marketing" },
      { label: "Marketing Director", icon: "📣", href: "/marketing-director", department: "marketing" },
      // …then nested groups.
      {
        id: "marketing-ci",
        label: "Central Intelligence",
        icon: "🔍",
        department: "marketing",
        children: [
          { label: "CI Insights", icon: "🔍", href: "/ci-insights", department: "marketing" },
          { label: "Market Signals", icon: "📶", href: "/ci-market-signals", department: "marketing" },
          { label: "CI Transcripts", icon: "📋", href: "/ci-transcript-upload", department: "marketing" },
          { label: "Content Ideas", icon: "💡", href: "/ci-content-ideas", department: "marketing" },
        ],
      },
      {
        id: "marketing-channels",
        label: "Channels",
        icon: "📡",
        department: "marketing",
        children: [
          { label: "Social Media", icon: "📱", href: "/marketing/social", department: "marketing" },
          { label: "Email", icon: "✉", href: "/marketing/email", department: "marketing" },
          { label: "Funnels", icon: "📈", href: "/marketing/funnels", department: "marketing" },
          { label: "Ads", icon: "📢", href: "/marketing/ads", department: "marketing" },
          { label: "DM", icon: "💬", href: "/marketing/dm", department: "marketing" },
          { label: "Offers", icon: "🎁", href: "/marketing/offers", department: "marketing" },
          { label: "Promo Calendar", icon: "📅", href: "/marketing/promo-calendar", department: "marketing" },
        ],
      },
    ],
  },
  {
    id: "admin",
    label: "Admin",
    department: "admin",
    collapsible: false,
    entries: [
      { label: "Data Import", icon: "📥", href: "/data-import", department: "admin" },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    department: "admin",
    collapsible: false,
    entries: [
      { label: "Integrations", icon: "🔌", href: "/integrations", department: "admin" },
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

// ─── Active-route helper ────────────────────────────────────────────────────────

function routeIsActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard";
  return pathname === href || pathname.startsWith(href + "/");
}

function groupHasActiveChild(pathname: string, group: NavGroup): boolean {
  return group.children.some((c) => routeIsActive(pathname, c.href));
}

function sectionHasActiveDescendant(pathname: string, section: NavSection): boolean {
  return section.entries.some((e) =>
    isGroup(e) ? groupHasActiveChild(pathname, e) : routeIsActive(pathname, e.href),
  );
}

// ─── Chevron ────────────────────────────────────────────────────────────────────

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={`w-3 h-3 text-gray-400 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
    >
      <path
        fillRule="evenodd"
        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function NavLink({
  item,
  isActive,
  indented = false,
}: {
  item: NavItem;
  isActive: boolean;
  indented?: boolean;
}) {
  const activeClasses = ACTIVE_ITEM_CLASSES[item.department];
  const inactiveClasses =
    "border-l-[3px] border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-800";

  return (
    <Link
      href={item.href}
      className={`flex items-center gap-2.5 py-2 text-sm font-medium rounded-r-md transition-all duration-150 ${
        indented ? "pl-9 pr-4" : "px-4"
      } ${isActive ? activeClasses : inactiveClasses}`}
    >
      <span className="text-base leading-none">{item.icon}</span>
      <span>{item.label}</span>
    </Link>
  );
}

/** A collapsible group of links (third level), nested inside a section. */
function NavGroupNode({
  group,
  pathname,
}: {
  group: NavGroup;
  pathname: string;
}) {
  const [open, setOpen] = useState(() => groupHasActiveChild(pathname, group));

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-800 border-l-[3px] border-transparent transition-all duration-150"
      >
        <span className="text-base leading-none">{group.icon}</span>
        <span className="flex-1 text-left">{group.label}</span>
        <Chevron open={open} />
      </button>
      {open && (
        <div>
          {group.children.map((child) => (
            <NavLink
              key={child.href}
              item={child}
              isActive={routeIsActive(pathname, child.href)}
              indented
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** A department section: collapsible label + its entries (links and/or groups). */
function SectionNode({
  section,
  pathname,
}: {
  section: NavSection;
  pathname: string;
}) {
  const colorClass = SECTION_LABEL_CLASSES[section.department];
  const [open, setOpen] = useState(() =>
    section.collapsible ? sectionHasActiveDescendant(pathname, section) : true,
  );

  const renderEntries = () =>
    section.entries.map((entry) =>
      isGroup(entry) ? (
        <NavGroupNode key={entry.id} group={entry} pathname={pathname} />
      ) : (
        <NavLink
          key={entry.href}
          item={entry}
          isActive={routeIsActive(pathname, entry.href)}
        />
      ),
    );

  // Non-collapsible sections (Admin, Settings) render as a static label + items.
  if (!section.collapsible) {
    return (
      <div>
        <div className={`px-4 pt-5 pb-1 text-[10px] font-bold tracking-widest uppercase ${colorClass}`}>
          {section.label}
        </div>
        {renderEntries()}
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`w-full flex items-center gap-1.5 px-4 pt-5 pb-1 text-[10px] font-bold tracking-widest uppercase hover:opacity-80 transition-opacity ${colorClass}`}
      >
        <span className="flex-1 text-left">{section.label}</span>
        <Chevron open={open} />
      </button>
      {open && <div>{renderEntries()}</div>}
    </div>
  );
}

// ─── User Footer ──────────────────────────────────────────────────────────────

function getInitials(nameOrEmail: string): string {
  const parts = nameOrEmail.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
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

  // SectionNode/NavGroupNode seed their open-state from the active route at
  // mount; keying the tree on the active section ensures a hard navigation to
  // a different department re-seeds auto-expansion correctly.
  const activeSectionId = useMemo(() => {
    const match = NAV_SECTIONS.find((s) => sectionHasActiveDescendant(pathname, s));
    return match?.id ?? "none";
  }, [pathname]);

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

      {/* Top Nav — Dashboard, CI Chat, Calendar */}
      <nav className="pt-3 pb-1" aria-label="Main navigation">
        {TOP_NAV.map((item) => (
          <NavLink key={item.href} item={item} isActive={routeIsActive(pathname, item.href)} />
        ))}
      </nav>

      {/* Sectioned Nav — collapsible departments + nested groups */}
      <nav className="flex-1 pb-3" aria-label="Department navigation" key={activeSectionId}>
        {NAV_SECTIONS.map((section) => (
          <SectionNode key={section.id} section={section} pathname={pathname} />
        ))}
      </nav>

      {/* User Footer — dynamic from auth context */}
      <UserFooter />
    </aside>
  );
}

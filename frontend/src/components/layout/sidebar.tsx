"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
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
  { label: "Insights", icon: "🧠", href: "/insights", department: "core" },
  { label: "Calendar", icon: "📅", href: "/calendar", department: "core" },
];

const NAV_SECTIONS: NavSection[] = [
  {
    id: "sales",
    label: "Sales",
    department: "sales",
    collapsible: true,
    entries: [
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

// Muted department-tinted section labels per the mockup (.nav-section-label.*),
// readable on the dark sidebar. core/admin fall back to the neutral heading gray.
const SECTION_LABEL_CLASSES: Record<Department, string> = {
  sales: "text-blue-400/70",
  fulfillment: "text-orange-400/70",
  marketing: "text-emerald-400/70",
  admin: "text-sidebar-heading",
  core: "text-sidebar-heading",
};

// Mockup uses one uniform active treatment for every item (gold left-bar +
// gold-tinted bg + gold text), regardless of department.
const ACTIVE_ITEM_CLASS =
  "border-l-[3px] border-accent-500 bg-sidebar-active-bg text-sidebar-active-text";

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

// ─── Collapsible-node bookkeeping ───────────────────────────────────────────────
// Ids of every collapsible node (sections + nested groups), in render order.
// Drives Expand-all and the "are all open?" check for the toggle's label.
const ALL_COLLAPSIBLE_IDS: string[] = NAV_SECTIONS.flatMap((s) =>
  s.collapsible
    ? [s.id, ...s.entries.filter(isGroup).map((g) => g.id)]
    : s.entries.filter(isGroup).map((g) => g.id),
);

/** Ids that should be open for the current route — the section containing the
 * active page plus any group containing it. Preserves the prior auto-expand. */
function routeSeededOpenIds(pathname: string): Set<string> {
  const open = new Set<string>();
  for (const section of NAV_SECTIONS) {
    if (section.collapsible && sectionHasActiveDescendant(pathname, section)) {
      open.add(section.id);
    }
    for (const entry of section.entries) {
      if (isGroup(entry) && groupHasActiveChild(pathname, entry)) {
        open.add(entry.id);
      }
    }
  }
  return open;
}

// ─── Chevron ────────────────────────────────────────────────────────────────────

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={`w-3 h-3 text-sidebar-heading transition-transform duration-150 ${open ? "rotate-90" : ""}`}
    >
      <path
        fillRule="evenodd"
        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
        clipRule="evenodd"
      />
    </svg>
  );
}

/**
 * Smoothly animates a collapsible region's height + opacity using the
 * grid-rows 0fr→1fr technique — no fixed pixel height or JS measurement needed,
 * works for arbitrary content, and the inner wrapper's `overflow-hidden` clips
 * the children while they slide. Children stay mounted so it animates both ways.
 */
function Collapsible({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div
      className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out ${
        open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
      }`}
    >
      <div className="overflow-hidden">{children}</div>
    </div>
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
  const inactiveClasses =
    "border-l-[3px] border-transparent text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-hover";

  return (
    <Link
      href={item.href}
      className={`flex items-center gap-2.5 py-2 text-sm font-medium transition-all duration-150 ${
        indented ? "pl-9 pr-4" : "px-4"
      } ${isActive ? ACTIVE_ITEM_CLASS : inactiveClasses}`}
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
  open,
  onToggle,
}: {
  group: NavGroup;
  pathname: string;
  open: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={() => onToggle(group.id)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 px-4 py-2 text-sm font-medium text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-hover border-l-[3px] border-transparent transition-all duration-150"
      >
        <span className="text-base leading-none">{group.icon}</span>
        <span className="flex-1 text-left">{group.label}</span>
        <Chevron open={open} />
      </button>
      <Collapsible open={open}>
        {group.children.map((child) => (
          <NavLink
            key={child.href}
            item={child}
            isActive={routeIsActive(pathname, child.href)}
            indented
          />
        ))}
      </Collapsible>
    </div>
  );
}

/** A department section: collapsible label + its entries (links and/or groups). */
function SectionNode({
  section,
  pathname,
  isOpen,
  onToggle,
}: {
  section: NavSection;
  pathname: string;
  isOpen: (id: string) => boolean;
  onToggle: (id: string) => void;
}) {
  const colorClass = SECTION_LABEL_CLASSES[section.department];
  const open = isOpen(section.id);

  const renderEntries = () =>
    section.entries.map((entry) =>
      isGroup(entry) ? (
        <NavGroupNode
          key={entry.id}
          group={entry}
          pathname={pathname}
          open={isOpen(entry.id)}
          onToggle={onToggle}
        />
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
        onClick={() => onToggle(section.id)}
        aria-expanded={open}
        className={`w-full flex items-center gap-1.5 px-4 pt-5 pb-1 text-[10px] font-bold tracking-widest uppercase hover:opacity-80 transition-opacity ${colorClass}`}
      >
        <span className="flex-1 text-left">{section.label}</span>
        <Chevron open={open} />
      </button>
      <Collapsible open={open}>{renderEntries()}</Collapsible>
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
    <div className="flex items-center gap-3 px-4 py-4 border-t border-sidebar-border">
      <div
        className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-accent-500 to-accent-600 text-white text-xs font-bold flex-shrink-0"
        aria-label="User avatar"
      >
        {initials}
      </div>
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-sm font-semibold text-sidebar-text-hover truncate">
          {displayName}
        </span>
        <span className="text-xs text-sidebar-heading capitalize">{displayRole}</span>
      </div>
      <button
        type="button"
        onClick={() => void signOut()}
        aria-label="Sign out"
        className="flex-shrink-0 text-sidebar-heading hover:text-sidebar-text-hover transition-colors"
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

  // Open-state for every collapsible node lives here (lifted out of the nodes)
  // so the Expand-all / Collapse-all control can drive them together. Seeded
  // from the active route so a deep-link still reveals its section.
  const [openIds, setOpenIds] = useState<Set<string>>(() => routeSeededOpenIds(pathname));

  // On navigation, make sure the section/group containing the new page is open
  // (union, not replace — manual toggles elsewhere are preserved).
  useEffect(() => {
    const seeded = routeSeededOpenIds(pathname);
    setOpenIds((prev) => {
      // already open? (avoid Set spread — tsconfig target predates Set iteration)
      if (Array.from(seeded).every((id) => prev.has(id))) return prev;
      const next = new Set(prev);
      seeded.forEach((id) => next.add(id));
      return next;
    });
  }, [pathname]);

  const isOpen = useCallback((id: string) => openIds.has(id), [openIds]);

  const toggle = useCallback((id: string) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const allOpen = openIds.size >= ALL_COLLAPSIBLE_IDS.length;

  const toggleAll = useCallback(() => {
    setOpenIds(allOpen ? new Set<string>() : new Set(ALL_COLLAPSIBLE_IDS));
  }, [allOpen]);

  return (
    <aside className="flex flex-col w-[228px] h-screen bg-sidebar-bg overflow-y-auto overflow-x-hidden">
      {/* Logo Area */}
      <div className="flex flex-col px-5 pt-6 pb-5 border-b border-sidebar-border">
        <div className="flex items-center gap-2.5">
          <span className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent-500 to-accent-600 text-lg">
            🧠
          </span>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-white leading-tight">
              {APP_CONFIG.name}
            </span>
            <span className="text-[10px] text-accent-300 font-medium tracking-wide uppercase">
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

      {/* Expand-all / Collapse-all control */}
      <div className="flex justify-end px-4 pt-3">
        <button
          type="button"
          onClick={toggleAll}
          aria-label={allOpen ? "Collapse all menu sections" : "Expand all menu sections"}
          className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-heading hover:text-sidebar-text-hover transition-colors"
        >
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>

      {/* Sectioned Nav — collapsible departments + nested groups */}
      <nav className="flex-1 pb-3" aria-label="Department navigation">
        {NAV_SECTIONS.map((section) => (
          <SectionNode
            key={section.id}
            section={section}
            pathname={pathname}
            isOpen={isOpen}
            onToggle={toggle}
          />
        ))}
      </nav>

      {/* User Footer — dynamic from auth context */}
      <UserFooter />
    </aside>
  );
}

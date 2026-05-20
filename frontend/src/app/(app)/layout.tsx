import { Sidebar } from "@/components/layout/sidebar";

// ─── Authenticated App Layout ────────────────────────────────────────────────
// Wraps all authenticated pages with sidebar + main content area.
// The login page lives outside this route group and gets no sidebar.

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="grid grid-cols-[228px_1fr] h-screen overflow-hidden">
      {/* Left — Sidebar */}
      <Sidebar />

      {/* Right — Header + Page Content */}
      <div className="flex flex-col min-w-0 bg-gray-50 overflow-hidden">
        {children}
      </div>
    </div>
  );
}

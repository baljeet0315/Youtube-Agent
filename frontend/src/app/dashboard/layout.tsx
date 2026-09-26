"use client";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Video, PlusCircle, Clock, Settings } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/dashboard", label: "Create", icon: PlusCircle },
  { href: "/dashboard/videos", label: "My videos", short: "Videos", icon: Video },
  { href: "/dashboard/history", label: "History", icon: Clock },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const isActive = (href: string) =>
    href === "/dashboard" ? path === "/dashboard" || path.startsWith("/dashboard/jobs") : path.startsWith(href);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Desktop sidebar (md and up) ─────────────────────── */}
      <aside className="hidden md:flex w-56 bg-white border-r border-gray-100 flex-col fixed inset-y-0 left-0 z-10">
        <div className="px-5 py-5 border-b border-gray-100">
          <p className="font-semibold text-gray-900 text-sm">Video Agent</p>
          <p className="text-xs text-gray-400 mt-0.5">Create · Upload · Grow</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                isActive(href) ? "bg-brand-50 text-brand-600 font-medium" : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-gray-100 flex items-center gap-3">
          <UserButton afterSignOutUrl="/sign-in" />
          <span className="text-xs text-gray-400">Account</span>
        </div>
      </aside>

      {/* ── Mobile top bar ──────────────────────────────────── */}
      <header className="md:hidden sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-gray-100 px-4 h-14 flex items-center justify-between">
        <p className="font-semibold text-gray-900 text-sm">Video Agent</p>
        <UserButton afterSignOutUrl="/sign-in" />
      </header>

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="md:ml-56 px-4 py-5 pb-24 md:p-8 md:pb-8 max-w-3xl mx-auto md:mx-0 w-full">
        {children}
      </main>

      {/* ── Mobile bottom tabs ──────────────────────────────── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-white border-t border-gray-100 grid grid-cols-4"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {nav.map(({ href, label, short, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] transition-colors",
              isActive(href) ? "text-brand-600 font-medium" : "text-gray-400"
            )}
          >
            <Icon size={20} strokeWidth={isActive(href) ? 2.4 : 1.8} />
            {short || label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

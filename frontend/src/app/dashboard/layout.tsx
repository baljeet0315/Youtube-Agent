"use client";
import { useEffect, useState } from "react";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Video, PlusCircle, Clock, Settings, Menu, X } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/dashboard", label: "Create", icon: PlusCircle },
  { href: "/dashboard/videos", label: "My videos", icon: Video },
  { href: "/dashboard/history", label: "History", icon: Clock },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/dashboard" ? path === "/dashboard" || path.startsWith("/dashboard/jobs") : path.startsWith(href);

  // Close the drawer on navigation and lock scroll while it's open
  useEffect(() => { setOpen(false); }, [path]);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const NavLinks = ({ onClick }: { onClick?: () => void }) => (
    <nav className="flex-1 px-3 py-4 space-y-0.5">
      {nav.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          onClick={onClick}
          className={clsx(
            "flex items-center gap-3 px-3 py-3 md:py-2.5 rounded-lg text-[15px] md:text-sm transition-colors",
            isActive(href) ? "bg-brand-50 text-brand-600 font-medium" : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
          )}
        >
          <Icon size={18} />
          {label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Desktop sidebar ─────────────────────────────────── */}
      <aside className="hidden md:flex w-56 bg-white border-r border-gray-100 flex-col fixed inset-y-0 left-0 z-10">
        <div className="px-5 py-5 border-b border-gray-100">
          <p className="font-semibold text-gray-900 text-sm">Video Agent</p>
          <p className="text-xs text-gray-400 mt-0.5">Create · Upload · Grow</p>
        </div>
        <NavLinks />
        <div className="px-5 py-4 border-t border-gray-100 flex items-center gap-3">
          <UserButton afterSignOutUrl="/sign-in" />
          <span className="text-xs text-gray-400">Account</span>
        </div>
      </aside>

      {/* ── Mobile top bar ──────────────────────────────────── */}
      <header className="md:hidden sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-gray-100 px-3 h-14 flex items-center justify-between">
        <button
          onClick={() => setOpen(true)}
          aria-label="Open menu"
          className="p-2 -ml-1 rounded-lg text-gray-700 hover:bg-gray-100 active:bg-gray-200"
        >
          <Menu size={22} />
        </button>
        <p className="font-semibold text-gray-900 text-sm">Video Agent</p>
        <UserButton afterSignOutUrl="/sign-in" />
      </header>

      {/* ── Mobile drawer ───────────────────────────────────── */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white shadow-xl flex flex-col drawer-in">
            <div className="px-5 h-14 border-b border-gray-100 flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900 text-sm">Video Agent</p>
                <p className="text-[11px] text-gray-400">Create · Upload · Grow</p>
              </div>
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="p-2 -mr-2 rounded-lg text-gray-500 hover:bg-gray-100">
                <X size={20} />
              </button>
            </div>
            <NavLinks onClick={() => setOpen(false)} />
            <div className="px-5 py-4 border-t border-gray-100 flex items-center gap-3" style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}>
              <UserButton afterSignOutUrl="/sign-in" />
              <span className="text-xs text-gray-400">Account</span>
            </div>
          </aside>
        </div>
      )}

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="md:ml-56 px-4 py-5 md:p-8 max-w-3xl w-full">
        {children}
      </main>
    </div>
  );
}

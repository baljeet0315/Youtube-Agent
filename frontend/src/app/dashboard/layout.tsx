"use client";
import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Video, PlusCircle, Clock, Settings } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/dashboard", label: "Create", icon: PlusCircle },
  { href: "/dashboard/videos", label: "My videos", icon: Video },
  { href: "/dashboard/history", label: "History", icon: Clock },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-56 bg-white border-r border-gray-100 flex flex-col fixed h-full z-10">
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
                path === href
                  ? "bg-brand-50 text-brand-600 font-medium"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
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

      {/* Main content */}
      <main className="ml-56 flex-1 p-8 max-w-3xl">
        {children}
      </main>
    </div>
  );
}

"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn, getInitials } from "@/lib/utils";
import { DASHBOARD_NAV_LINKS } from "@/lib/dashboard-data";
import { useAuth } from "@/contexts/AuthContext";
import { API_ORIGIN } from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Administrator",
  USER: "Learner",
};

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <aside className="flex w-[4.5rem] shrink-0 flex-col items-center border-r border-border bg-surface-elevated px-2 py-6 lg:w-64 lg:items-stretch lg:px-4">
      <div className="px-2 text-center lg:text-left">
        <span className="font-serif text-2xl font-semibold tracking-tight text-primary">
          S
          <span className="hidden lg:inline">peeky</span>
        </span>
        <p className="hidden text-xs font-medium tracking-wide text-muted-foreground lg:block">
          AI COACH
        </p>
      </div>

      <nav
        aria-label="Dashboard"
        className="mt-8 flex w-full flex-col items-center gap-1 lg:items-stretch"
      >
        {DASHBOARD_NAV_LINKS.map((link) => {
          const isActive = pathname === link.href;
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-label={link.label}
              title={link.label}
              className={cn(
                "flex items-center justify-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors lg:justify-start",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-surface hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="hidden lg:inline">{link.label}</span>
            </Link>
          );
        })}
      </nav>

      {user ? (
        <Link
          href="/dashboard/profile"
          aria-label={`View profile — ${user.name}`}
          title={user.name}
          className="mt-auto flex w-full items-center justify-center gap-3 rounded-xl border-t border-border px-2 pt-4 transition-colors hover:text-primary lg:justify-start"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-sm font-semibold text-primary">
            {user.avatarUrl && user.avatarUrl !== "user.webp" ? (
              <Image
                src={`${API_ORIGIN}/uploads/avatars/${user.avatarUrl}`}
                alt=""
                width={40}
                height={40}
                className="h-full w-full object-cover"
                unoptimized
              />
            ) : (
              getInitials(user.name)
            )}
          </span>
          <span className="hidden min-w-0 flex-col lg:flex">
            <span className="truncate text-sm font-medium text-foreground">
              {user.name}
            </span>
            <span className="truncate text-xs text-muted-foreground">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </span>
        </Link>
      ) : null}
    </aside>
  );
}

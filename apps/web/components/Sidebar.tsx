"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getUserEmail, logout } from "@/lib/api-client";

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function KeyIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 7a2 2 0 012 2m4 0a6 6 0 11-12 0 6 6 0 0112 0zM7 9l-6 6v3h3l6-6"
      />
    </svg>
  );
}

function NavItem({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  const pathname = usePathname();
  const active = pathname === href;
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-primary-accent/10 text-primary-accent"
          : "text-muted-text hover:bg-surface-card-hover hover:text-foreground"
      }`}
    >
      {icon}
      {label}
    </Link>
  );
}

export function Sidebar() {
  const [email, setEmail] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    setEmail(getUserEmail());
    api
      .getMe()
      .then((me) => setIsAdmin(me.is_admin))
      .catch(() => setIsAdmin(false));
  }, []);

  const initials = email ? email.slice(0, 2).toUpperCase() : "?";

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-surface-border bg-surface-base">
      <div className="border-b border-surface-border p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-foreground text-sm font-semibold text-background">
            K
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Koya Lead Agent</p>
            <p className="text-xs text-muted-text">Lead Research & Outreach</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <p className="px-3 text-xs font-semibold uppercase tracking-wider text-muted-text">Workspace</p>
        <nav className="mt-2 space-y-1">
          <NavItem href="/" icon={<PlusIcon />} label="New run" />
          <NavItem href="/runs" icon={<ListIcon />} label="My runs" />
          {isAdmin && <NavItem href="/access" icon={<KeyIcon />} label="Access" />}
        </nav>
      </div>

      <div className="border-t border-surface-border p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-card-hover text-xs font-semibold text-foreground">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-foreground">{email ?? "Not signed in"}</p>
            {email && (
              <p className="flex items-center gap-1 text-xs text-muted-text">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Signed in
              </p>
            )}
          </div>
        </div>
        {email && (
          <button
            onClick={logout}
            className="mt-3 w-full rounded-lg border border-surface-border px-3 py-1.5 text-left text-xs font-medium text-muted-text transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            Sign out
          </button>
        )}
      </div>
    </aside>
  );
}

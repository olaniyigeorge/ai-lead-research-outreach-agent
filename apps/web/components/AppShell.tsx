"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";

function MenuIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-surface-base">
      <Sidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="flex h-full flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-surface-border bg-surface-base px-4 py-3 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="rounded-lg p-1.5 text-muted-text transition-colors hover:bg-surface-card-hover hover:text-foreground"
            aria-label="Open menu"
          >
            <MenuIcon />
          </button>
          <p className="text-sm font-semibold text-foreground">Koya Lead Agent</p>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

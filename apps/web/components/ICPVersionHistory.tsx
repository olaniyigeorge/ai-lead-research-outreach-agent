"use client";

import type { ICPCriteria } from "@/lib/api-client";

export function ICPVersionHistory({
  versions,
  currentVersion,
  viewingVersion,
  onView,
}: {
  versions: ICPCriteria[];
  currentVersion: number;
  viewingVersion: number;
  onView: (version: number) => void;
}) {
  if (versions.length <= 1) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-text">History</span>
      <div className="flex flex-wrap gap-1.5">
        {versions.map((v) => {
          const isViewing = v.version === viewingVersion;
          const isCurrent = v.version === currentVersion;
          return (
            <button
              key={v.version}
              type="button"
              onClick={() => onView(v.version)}
              className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                isViewing
                  ? "border-primary-accent bg-primary-accent/10 text-primary-accent"
                  : "border-surface-border bg-surface-base text-muted-text hover:text-foreground"
              }`}
            >
              v{v.version}
              {isCurrent && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" title="Currently in use" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

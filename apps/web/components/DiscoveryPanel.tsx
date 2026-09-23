"use client";

import { useState } from "react";
import type { Lead, RunOut } from "@/lib/api-client";

const STATUS_STYLES: Record<string, string> = {
  discovered: "bg-sky-100 text-sky-700",
  scraped: "bg-sky-100 text-sky-700",
  qualified: "bg-emerald-100 text-emerald-700",
  disqualified: "bg-rose-100 text-rose-700",
  needs_review: "bg-amber-100 text-amber-700",
  error: "bg-rose-100 text-rose-700",
};

function LeadRow({ lead }: { lead: Lead }) {
  const [expanded, setExpanded] = useState(false);
  const hasRaw = Object.keys(lead.source_raw ?? {}).length > 0;

  return (
    <div className="border-b border-surface-border last:border-b-0">
      <button
        type="button"
        onClick={() => hasRaw && setExpanded((v) => !v)}
        className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left ${
          hasRaw ? "cursor-pointer hover:bg-surface-base" : "cursor-default"
        }`}
      >
        <div>
          <p className="text-sm font-medium text-foreground">{lead.company_name}</p>
          <p className="text-xs text-muted-text">{lead.company_domain}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {lead.is_buffer && (
            <span
              className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700"
              title="Spare candidate from the discovery buffer -- not scraped until promoted"
            >
              spare
            </span>
          )}
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              STATUS_STYLES[lead.qualification_status] ?? "bg-surface-base text-muted-text"
            }`}
          >
            {lead.qualification_status.replace("_", " ")}
          </span>
          {hasRaw && (
            <span className="text-xs text-muted-text">{expanded ? "Hide details ▲" : "Details ▼"}</span>
          )}
        </div>
      </button>
      {expanded && hasRaw && (
        <div className="border-t border-surface-border bg-surface-base px-4 py-3">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-text">
            Raw discovery data (from Apify)
          </p>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-background p-3 text-xs text-foreground">
            {JSON.stringify(lead.source_raw, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function DiscoveryPanel({ run }: { run: RunOut }) {
  if (run.status === "draft" || run.status === "awaiting_icp_confirmation") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Discovery</h1>
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Confirm your target profile on the ICP phase first.</p>
        </div>
      </div>
    );
  }

  if (run.status === "queued") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Discovery</h1>
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">
            Your target profile is confirmed. Start discovery below to search for up to {run.lead_count_limit}{" "}
            candidate companies.
          </p>
        </div>
      </div>
    );
  }

  if (run.status === "failed" && run.leads.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Discovery</h1>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center">
          <p className="text-sm text-rose-900">No candidate companies were found for this target profile.</p>
        </div>
      </div>
    );
  }

  const primaryCount = run.leads.filter((l) => !l.is_buffer).length;
  const spareCount = run.leads.length - primaryCount;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold text-foreground">Discovery</h1>
        <p className="text-xs text-muted-text">
          {primaryCount} of {run.lead_count_limit} found
          {spareCount > 0 && ` (+${spareCount} spare)`}
        </p>
      </div>
      {run.status === "running" ? (
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Searching for candidate companies...</p>
        </div>
      ) : (
        <>
          <div className="glow-card overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
            {run.leads.map((lead) => (
              <LeadRow key={lead.id} lead={lead} />
            ))}
          </div>
          {(run.status === "completed" || run.status === "partially_completed" || run.status === "failed") &&
            run.leads.length > 0 && (
              <p className="text-xs text-muted-text">
                Discovery is done for this run -- head to the Scraping tab to verify and enrich these candidates.
                If you end up short of the target after scraping, come back here to request more.
              </p>
            )}
        </>
      )}
    </div>
  );
}

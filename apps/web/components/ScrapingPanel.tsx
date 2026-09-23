"use client";

import { useState } from "react";
import type { Lead, RunOut } from "@/lib/api-client";

const STATUS_STYLES: Record<string, string> = {
  discovered: "bg-sky-100 text-sky-700",
  scraped: "bg-emerald-100 text-emerald-700",
  qualified: "bg-emerald-100 text-emerald-700",
  disqualified: "bg-rose-100 text-rose-700",
  needs_review: "bg-amber-100 text-amber-700",
  error: "bg-rose-100 text-rose-700",
};

// Groups leads by where they are in the pipeline so a long list reads as
// "what's left to do, then what's done, then what needs attention" instead
// of scattered in whatever order they happened to be created/updated in.
const STATUS_ORDER: Record<string, number> = {
  discovered: 0,
  scraped: 1,
  needs_review: 2,
  qualified: 3,
  disqualified: 4,
  error: 5,
};

function sortByStatus(leads: Lead[]): Lead[] {
  return [...leads].sort((a, b) => {
    const diff = (STATUS_ORDER[a.qualification_status] ?? 99) - (STATUS_ORDER[b.qualification_status] ?? 99);
    return diff !== 0 ? diff : a.created_at.localeCompare(b.created_at);
  });
}

function LeadRow({ lead }: { lead: Lead }) {
  const [expanded, setExpanded] = useState(false);
  const source = lead.sources[0];
  const hasSummary = Boolean(source?.content_summary);
  const hasError = lead.qualification_status === "error" && Boolean(lead.last_error);
  const hasDetail = hasSummary || hasError;

  return (
    <div className="border-b border-surface-border last:border-b-0">
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((v) => !v)}
        className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left ${
          hasDetail ? "cursor-pointer hover:bg-surface-base" : "cursor-default"
        }`}
      >
        <div>
          <p className="text-sm font-medium text-foreground">{lead.company_name}</p>
          <p className="text-xs text-muted-text">{lead.company_domain}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              STATUS_STYLES[lead.qualification_status] ?? "bg-surface-base text-muted-text"
            }`}
          >
            {lead.qualification_status.replace("_", " ")}
          </span>
          {hasDetail && (
            <span className="text-xs text-muted-text">
              {expanded ? "Hide details ▲" : hasError ? "Why it failed ▼" : "Summary ▼"}
            </span>
          )}
        </div>
      </button>
      {expanded && hasSummary && (
        <div className="border-t border-surface-border bg-surface-base px-4 py-3">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-text">
            Source summary &mdash; {source.url}
          </p>
          <p className="whitespace-pre-wrap text-xs text-foreground">{source.content_summary}</p>
        </div>
      )}
      {expanded && hasError && (
        <div className="border-t border-surface-border bg-rose-50 px-4 py-3">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-rose-700">Why this failed</p>
          <p className="whitespace-pre-wrap text-xs text-rose-900">{lead.last_error}</p>
        </div>
      )}
    </div>
  );
}

export function ScrapingPanel({ run }: { run: RunOut }) {
  const scrapableStages = ["draft", "awaiting_icp_confirmation", "queued"];
  if (scrapableStages.includes(run.status) || run.leads.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Scraping</h1>
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Run discovery first to find candidate companies to scrape.</p>
        </div>
      </div>
    );
  }

  const primaryLeads = run.leads.filter((l) => !l.is_buffer);
  const spareCount = run.leads.length - primaryLeads.length;
  const discoveredCount = primaryLeads.filter((l) => l.qualification_status === "discovered").length;
  const scrapedCount = primaryLeads.filter((l) => l.sources.length > 0).length;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold text-foreground">Scraping</h1>
        <p className="text-xs text-muted-text">
          {scrapedCount} of {primaryLeads.length} scraped
          {spareCount > 0 && ` (+${spareCount} spare, not yet in use)`}
        </p>
      </div>
      {run.status === "running" && scrapedCount === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Scraping candidate websites...</p>
        </div>
      ) : (
        <div className="glow-card overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
          {sortByStatus(primaryLeads).map((lead) => (
            <LeadRow key={lead.id} lead={lead} />
          ))}
        </div>
      )}
      {discoveredCount === 0 && scrapedCount > 0 && (
        <p className="text-xs text-muted-text">
          Scraping is done for this run -- head to the Qualification tab to weigh these {scrapedCount} candidates
          against your target profile.
        </p>
      )}
      <p className="text-xs text-muted-text">
        Scraped website text is summarized by a Claude call with <strong>zero tools bound</strong> &mdash; it can
        only read the page and write a summary, so nothing on a scraped site can trigger any action, however it&apos;s
        phrased.
      </p>
    </div>
  );
}

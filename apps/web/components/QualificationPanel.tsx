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

function ConfidenceBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  return (
    <span className="text-xs text-muted-text" title="Confidence in the verdict, given evidence quality">
      {pct}% confidence
    </span>
  );
}

function LeadRow({ lead }: { lead: Lead }) {
  const [expanded, setExpanded] = useState(false);
  const hasVerdict = lead.fit_reasons.length > 0 || lead.concerns.length > 0 || lead.missing_information.length > 0;

  return (
    <div className="border-b border-surface-border last:border-b-0">
      <button
        type="button"
        onClick={() => hasVerdict && setExpanded((v) => !v)}
        className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left ${
          hasVerdict ? "cursor-pointer hover:bg-surface-base" : "cursor-default"
        }`}
      >
        <div>
          <p className="text-sm font-medium text-foreground">{lead.company_name}</p>
          <p className="text-xs text-muted-text">{lead.company_domain}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ConfidenceBadge score={lead.confidence_score} />
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              STATUS_STYLES[lead.qualification_status] ?? "bg-surface-base text-muted-text"
            }`}
          >
            {lead.qualification_status.replace("_", " ")}
          </span>
          {hasVerdict && (
            <span className="text-xs text-muted-text">{expanded ? "Hide reasoning ▲" : "Reasoning ▼"}</span>
          )}
        </div>
      </button>
      {expanded && hasVerdict && (
        <div className="space-y-2 border-t border-surface-border bg-surface-base px-4 py-3">
          {lead.fit_reasons.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">Fit reasons</p>
              <ul className="mt-1 list-inside list-disc text-xs text-foreground">
                {lead.fit_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {lead.concerns.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-amber-700">Concerns</p>
              <ul className="mt-1 list-inside list-disc text-xs text-foreground">
                {lead.concerns.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          )}
          {lead.missing_information.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-text">Missing information</p>
              <ul className="mt-1 list-inside list-disc text-xs text-foreground">
                {lead.missing_information.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function QualificationPanel({ run }: { run: RunOut }) {
  const primaryLeads = run.leads.filter((l) => !l.is_buffer);
  const scrapedLeads = primaryLeads.filter((l) => l.sources.length > 0);

  if (scrapedLeads.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Qualification</h1>
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Scrape candidate sites first to have evidence to qualify against.</p>
        </div>
      </div>
    );
  }

  const pendingCount = primaryLeads.filter((l) => l.qualification_status === "scraped").length;
  const qualifiedCount = primaryLeads.filter((l) => l.qualification_status === "qualified").length;
  const disqualifiedCount = primaryLeads.filter((l) => l.qualification_status === "disqualified").length;
  const needsReviewCount = primaryLeads.filter((l) => l.qualification_status === "needs_review").length;
  const decidedCount = qualifiedCount + disqualifiedCount + needsReviewCount;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold text-foreground">Qualification</h1>
        <p className="text-xs text-muted-text">
          {qualifiedCount} qualified &middot; {disqualifiedCount} disqualified &middot; {needsReviewCount} needs review
        </p>
      </div>
      {run.status === "running" && decidedCount === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Weighing candidates against your target profile...</p>
        </div>
      ) : run.status === "failed" && decidedCount === 0 ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center">
          <p className="text-sm font-medium text-rose-900">Qualification failed before any lead was decided.</p>
          <p className="mt-1 text-xs text-rose-800">
            Open the Logs panel (top right) for what the agent session did before it stopped.
          </p>
        </div>
      ) : (
        <div className="glow-card overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
          {scrapedLeads.map((lead) => (
            <LeadRow key={lead.id} lead={lead} />
          ))}
        </div>
      )}
      {pendingCount === 0 && decidedCount > 0 && qualifiedCount > 0 && (
        <p className="text-xs text-muted-text">
          Qualification is done for this run -- head to the Drafting tab to write outreach for the {qualifiedCount}{" "}
          qualified lead{qualifiedCount === 1 ? "" : "s"}.
        </p>
      )}
    </div>
  );
}

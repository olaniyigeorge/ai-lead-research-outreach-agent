"use client";

import { useState } from "react";
import type { Draft, Lead, RunOut } from "@/lib/api-client";

const CHANNEL_LABELS: Record<string, string> = {
  email_1: "Email 1",
  email_2: "Email 2",
  email_3: "Email 3",
  linkedin: "LinkedIn message",
};

const CHANNEL_ORDER = ["email_1", "email_2", "email_3", "linkedin"];

function DraftCard({ draft }: { draft: Draft }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-base p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">
          {CHANNEL_LABELS[draft.channel] ?? draft.channel}
        </p>
        {draft.cited_source_ids.length > 0 && (
          <span
            className="text-xs text-muted-text"
            title={`Traceable to ${draft.cited_source_ids.length} evidence source(s) scraped for this company`}
          >
            {draft.cited_source_ids.length} citation{draft.cited_source_ids.length === 1 ? "" : "s"}
          </span>
        )}
      </div>
      {draft.subject && <p className="mt-1.5 text-sm font-medium text-foreground">{draft.subject}</p>}
      <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{draft.body}</p>
      {draft.personalization_note && (
        <p className="mt-2 border-t border-surface-border pt-2 text-xs italic text-muted-text">
          Personalization: {draft.personalization_note}
        </p>
      )}
    </div>
  );
}

function LeadDraftRow({ lead }: { lead: Lead }) {
  const [expanded, setExpanded] = useState(false);
  const drafts = [...lead.drafts].sort(
    (a, b) => CHANNEL_ORDER.indexOf(a.channel) - CHANNEL_ORDER.indexOf(b.channel),
  );

  return (
    <div className="border-b border-surface-border last:border-b-0">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-base"
      >
        <div>
          <p className="text-sm font-medium text-foreground">{lead.company_name}</p>
          <p className="text-xs text-muted-text">{lead.company_domain}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
            {drafts.length} draft{drafts.length === 1 ? "" : "s"}
          </span>
          <span className="text-xs text-muted-text">{expanded ? "Hide drafts ▲" : "Show drafts ▼"}</span>
        </div>
      </button>
      {expanded && (
        <div className="grid grid-cols-1 gap-3 border-t border-surface-border bg-surface-card px-4 py-4 sm:grid-cols-2">
          {drafts.map((draft) => (
            <DraftCard key={draft.id} draft={draft} />
          ))}
        </div>
      )}
    </div>
  );
}

export function DraftingPanel({ run }: { run: RunOut }) {
  const qualifiedLeads = run.leads.filter((l) => !l.is_buffer && l.qualification_status === "qualified");

  if (qualifiedLeads.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Drafting</h1>
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Qualify at least one lead first to have someone to draft outreach for.</p>
        </div>
      </div>
    );
  }

  const draftedLeads = qualifiedLeads.filter((l) => l.drafts.length > 0);
  const undraftedCount = qualifiedLeads.length - draftedLeads.length;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold text-foreground">Drafting</h1>
        <p className="text-xs text-muted-text">
          {draftedLeads.length} of {qualifiedLeads.length} qualified lead{qualifiedLeads.length === 1 ? "" : "s"} drafted
        </p>
      </div>
      {run.status === "running" && draftedLeads.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">Writing outreach for your qualified leads...</p>
        </div>
      ) : run.status === "failed" && draftedLeads.length === 0 ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center">
          <p className="text-sm font-medium text-rose-900">Drafting failed before any lead got a draft.</p>
          <p className="mt-1 text-xs text-rose-800">Open the Logs panel (top right) for what happened.</p>
        </div>
      ) : draftedLeads.length > 0 ? (
        <div className="glow-card overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
          {draftedLeads.map((lead) => (
            <LeadDraftRow key={lead.id} lead={lead} />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
          <p className="text-sm text-muted-text">
            {qualifiedLeads.length} qualified lead{qualifiedLeads.length === 1 ? "" : "s"} ready -- draft outreach below.
          </p>
        </div>
      )}
      {undraftedCount === 0 && draftedLeads.length > 0 && (
        <p className="text-xs text-muted-text">
          Every qualified lead has a draft. These are for human review only -- nothing here has been sent.
        </p>
      )}
      <p className="text-xs text-muted-text">
        Each draft cites the evidence it was written from. Review before using any of this outside the app.
      </p>
    </div>
  );
}

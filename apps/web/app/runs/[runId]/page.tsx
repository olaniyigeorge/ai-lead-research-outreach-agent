"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { CriteriaList } from "@/components/CriteriaList";
import { LoadingLine, Spinner } from "@/components/Spinner";
import { Stage, StageStepper } from "@/components/StageStepper";
import { ApiError, RunOut, api, getSession } from "@/lib/api-client";

const HARD_MAX_LEADS = 25;

function Fact({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-text">{label}</p>
      <p className="mt-0.5 text-sm text-foreground">{value}</p>
    </div>
  );
}

function ChipRow({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-text">{label}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-full border border-surface-border bg-surface-base px-2.5 py-0.5 text-xs text-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function CardSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glow-card rounded-2xl border border-surface-border bg-surface-card p-6">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function ComingSoonSection({ id, title, note }: { id: string; title: string; note: string }) {
  return (
    <section id={id} className="scroll-mt-20 space-y-4">
      <h1 className="text-xl font-semibold text-foreground">{title}</h1>
      <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
        <p className="text-sm text-muted-text">{note}</p>
      </div>
    </section>
  );
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunOut | null>(null);
  const [leadCount, setLeadCount] = useState(10);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getSession()) {
      router.push("/sign-in");
      return;
    }
    api
      .getRun(runId)
      .then((r) => {
        setRun(r);
        if (r.lead_count_limit) setLeadCount(r.lead_count_limit);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong"));
  }, [runId, router]);

  async function handleConfirm() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateIcp(runId, { lead_count: leadCount, confirm: true });
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center px-4">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      </AppShell>
    );
  }
  if (!run || !run.icp) {
    return <LoadingLine />;
  }

  const icp = run.icp;
  const icpConfirmed = run.status !== "draft" && run.status !== "awaiting_icp_confirmation";

  const stages: Stage[] = [
    { id: "icp", label: "ICP", status: icpConfirmed ? "completed" : "current" },
    { id: "discovery", label: "Discovery", status: "upcoming" },
    { id: "scraping", label: "Scraping", status: "upcoming" },
    { id: "qualification", label: "Qualification", status: "upcoming" },
    { id: "drafting", label: "Drafting", status: "upcoming" },
  ];

  return (
    <AppShell>
      <div className="flex min-h-full flex-col">
        <StageStepper stages={stages} />

        <div className="flex-1 px-4 py-10 sm:px-8">
          <div className="animate-fade-in-up mx-auto max-w-3xl space-y-10 pb-24">
            <section id="icp" className="scroll-mt-20 space-y-6">
              <div>
                <h1 className="text-2xl font-semibold text-foreground">Review your target profile</h1>
                <p className="mt-2 text-sm italic text-muted-text">&ldquo;{run.objective}&rdquo;</p>
              </div>

              <CardSection title="At a glance">
                <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
                  <Fact label="Target company type" value={icp.target_company_type} />
                  <Fact label="Buyer persona" value={icp.buyer_persona} />
                  <Fact label="Headcount range" value={icp.headcount_range} />
                  <div className="sm:col-span-2">
                    <Fact label="Business problem" value={icp.business_problem} />
                  </div>
                  <ChipRow label="Industries" items={icp.industries} />
                  <ChipRow label="Geography" items={icp.geography} />
                </div>
              </CardSection>

              <CardSection title="Required (must all be true)">
                <CriteriaList items={icp.hard_filters} tone="positive" />
              </CardSection>

              <CardSection title="Preferred (improves fit, not a dealbreaker)">
                <CriteriaList items={icp.soft_preferences} tone="neutral" />
              </CardSection>

              {icp.disqualifiers.length > 0 && (
                <CardSection title="Excluded">
                  <CriteriaList items={icp.disqualifiers} tone="negative" />
                </CardSection>
              )}

              {icp.assumptions_made.length > 0 && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
                  <h2 className="text-sm font-semibold text-amber-900">Assumptions I made</h2>
                  <p className="mt-1 text-xs text-amber-800">Check these are right before confirming.</p>
                  <div className="mt-3">
                    <CriteriaList items={icp.assumptions_made} tone="neutral" maxVisible={3} />
                  </div>
                </div>
              )}

              {icp.needs_confirmation.length > 0 && (
                <div className="rounded-2xl border border-sky-200 bg-sky-50 p-6">
                  <h2 className="text-sm font-semibold text-sky-900">Best-effort only</h2>
                  <p className="mt-1 text-xs text-sky-800">Can&apos;t be reliably verified from web research.</p>
                  <div className="mt-3">
                    <CriteriaList items={icp.needs_confirmation} tone="neutral" maxVisible={3} />
                  </div>
                </div>
              )}
            </section>

            <ComingSoonSection
              id="discovery"
              title="Discovery"
              note="Not started yet -- company discovery (Apify) hasn't been wired up in this build."
            />
            <ComingSoonSection
              id="scraping"
              title="Scraping"
              note="Not started yet -- website scraping runs after discovery finds candidate companies."
            />
            <ComingSoonSection
              id="qualification"
              title="Qualification"
              note="Not started yet -- qualification runs after each candidate is scraped."
            />
            <ComingSoonSection
              id="drafting"
              title="Drafting"
              note="Not started yet -- outreach drafts are generated for qualified leads."
            />
          </div>
        </div>

        <div className="sticky bottom-0 border-t border-surface-border bg-surface-card px-4 py-4 sm:px-8">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <label htmlFor="lead-count" className="text-sm font-medium text-foreground">
                Lead count
              </label>
              <input
                id="lead-count"
                type="number"
                min={1}
                max={HARD_MAX_LEADS}
                value={leadCount}
                disabled={icpConfirmed}
                onChange={(e) => setLeadCount(Math.min(HARD_MAX_LEADS, Number(e.target.value)))}
                className="w-20 rounded-lg border border-surface-border bg-background px-2 py-1.5 text-sm text-foreground outline-none transition-colors focus:border-primary-accent disabled:opacity-60"
              />
              <span className="text-xs text-muted-text">max {HARD_MAX_LEADS}</span>
            </div>

            <div className="flex items-center gap-4">
              {run.total_claude_cost_usd > 0 && (
                <span className="text-xs text-muted-text">
                  Est. Claude spend: ${run.total_claude_cost_usd.toFixed(4)}
                </span>
              )}
              <button
                onClick={handleConfirm}
                disabled={busy || icpConfirmed}
                className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy && <Spinner className="text-white" />}
                {icpConfirmed ? "Confirmed" : busy ? "Confirming..." : "Confirm and continue"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert } from "@/components/Alert";
import { AppShell } from "@/components/AppShell";
import { CriteriaList } from "@/components/CriteriaList";
import { DiscoveryPanel } from "@/components/DiscoveryPanel";
import { DraftingPanel } from "@/components/DraftingPanel";
import { QualificationPanel } from "@/components/QualificationPanel";
import { EditableCriteriaList } from "@/components/EditableCriteriaList";
import { EditableTagList } from "@/components/EditableTagList";
import { ICPVersionHistory } from "@/components/ICPVersionHistory";
import { PhaseCarousel } from "@/components/PhaseCarousel";
import { RunStageSummary } from "@/components/RunStageSummary";
import { ScrapingPanel } from "@/components/ScrapingPanel";
import { LoadingLine, Spinner } from "@/components/Spinner";
import { Stage, StageStepper } from "@/components/StageStepper";
import { ToolCallLogPanel } from "@/components/ToolCallLogPanel";
import { ApiError, ICPCriteria, RunOut, UpdateIcpBody, api, getSession } from "@/lib/api-client";

const HARD_MAX_LEADS = 25;

type DraftICP = {
  target_company_type: string;
  buyer_persona: string;
  headcount_range: string;
  business_problem: string;
  industries: string[];
  geography: string[];
  hard_filters: string[];
  soft_preferences: string[];
  disqualifiers: string[];
};

function draftFromIcp(icp: ICPCriteria): DraftICP {
  return {
    target_company_type: icp.target_company_type ?? "",
    buyer_persona: icp.buyer_persona ?? "",
    headcount_range: icp.headcount_range ?? "",
    business_problem: icp.business_problem ?? "",
    industries: icp.industries,
    geography: icp.geography,
    hard_filters: icp.hard_filters,
    soft_preferences: icp.soft_preferences,
    disqualifiers: icp.disqualifiers,
  };
}

function Fact({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="rounded-xl border border-surface-border bg-surface-base px-3.5 py-2.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">{label}</p>
      <p className="mt-1 text-sm text-foreground">{value}</p>
    </div>
  );
}

function EditableField({
  label,
  value,
  onChange,
  fullWidth = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  fullWidth?: boolean;
}) {
  return (
    <div className={fullWidth ? "sm:col-span-2" : undefined}>
      <label className="text-xs font-medium uppercase tracking-wide text-muted-text">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-surface-border bg-background px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-primary-accent"
      />
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

function CardSection({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="glow-card rounded-2xl border border-surface-border bg-surface-card p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunOut | null>(null);
  const [leadCount, setLeadCount] = useState(5);
  const [topUpCount, setTopUpCount] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [runningStage, setRunningStage] = useState<"discovery" | "scraping" | "qualification" | "drafting" | null>(
    null,
  );
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DraftICP | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [autoContinue, setAutoContinue] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.sessionStorage.getItem(`koya_auto_continue_${runId}`) === "1";
    } catch {
      return false;
    }
  });

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
        setViewingVersion(r.icp?.version ?? null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong"));
  }, [runId, router]);

  function toggleAutoContinue() {
    setAutoContinue((prev) => {
      const next = !prev;
      try {
        window.sessionStorage.setItem(`koya_auto_continue_${runId}`, next ? "1" : "0");
      } catch {
        // best-effort persistence only
      }
      return next;
    });
  }

  // A stage's own POST (e.g. handleStartScrape) doesn't resolve until the
  // whole stage finishes server-side -- for a 12-lead scrape that can be a
  // minute-plus with zero UI feedback, and a page LOAD/RELOAD mid-stage (a
  // second tab, or coming back later) sees a live "running" snapshot with
  // no way to tell it's progressing or to know when it's safe to act again.
  // Poll while status is "running" so the page reflects real progress and
  // re-enables controls the moment the backend actually finishes, instead
  // of sitting frozen on a stale snapshot.
  useEffect(() => {
    if (run?.status !== "running") return;
    const interval = setInterval(() => {
      api.getRun(runId).then(setRun).catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [run?.status, runId]);

  // Opt-in (off by default -- each stage below spends real Apify/Firecrawl/
  // Claude budget, and every other trigger in this app is deliberately
  // manual for exactly that reason). When on, fires the next stage the
  // instant this run has something ready for it and nothing else is in
  // flight -- reusing each canStart* condition's own logic rather than the
  // later-declared consts, since those are computed after the early
  // returns below and hooks can't follow a conditional return.
  useEffect(() => {
    if (!autoContinue || busy || error || !run || !run.icp) return;

    if (run.status === "queued") {
      handleStartDiscovery();
      return;
    }
    if (run.status === "running") return;

    const discoveredCount = run.leads.filter((l) => l.qualification_status === "discovered" && !l.is_buffer).length;
    if (discoveredCount > 0) {
      handleStartScrape();
      return;
    }

    const scrapedCount = run.leads.filter((l) => l.qualification_status === "scraped" && !l.is_buffer).length;
    if (scrapedCount > 0) {
      handleStartQualify();
      return;
    }

    const undraftedQualifiedCount = run.leads.filter(
      (l) => !l.is_buffer && l.qualification_status === "qualified" && l.drafts.length === 0,
    ).length;
    if (undraftedQualifiedCount > 0) {
      handleStartDraft();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoContinue, busy, error, run]);

  function navigateTo(index: number) {
    if (index === activeIndex) return;
    setDirection(index > activeIndex ? 1 : -1);
    setActiveIndex(index);
  }

  async function handleConfirm() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateIcp(runId, { lead_count: leadCount, confirm: true });
      setRun(updated);
      setViewingVersion(updated.icp?.version ?? null);
      navigateTo(1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function handleStartDiscovery() {
    setBusy(true);
    setRunningStage("discovery");
    setError(null);
    try {
      const updated = await api.startRun(runId);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleStartScrape() {
    setBusy(true);
    setRunningStage("scraping");
    setError(null);
    try {
      const updated = await api.startScrape(runId);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleTopUpDiscovery() {
    setBusy(true);
    setRunningStage("discovery");
    setError(null);
    try {
      const updated = await api.topUpDiscovery(runId, topUpCount);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleUseBuffer(count: number) {
    setBusy(true);
    setRunningStage("scraping");
    setError(null);
    try {
      const updated = await api.useDiscoveryBuffer(runId, count);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleStartQualify() {
    setBusy(true);
    setRunningStage("qualification");
    setError(null);
    try {
      const updated = await api.startQualify(runId);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleStartDraft() {
    setBusy(true);
    setRunningStage("drafting");
    setError(null);
    try {
      const updated = await api.startDraft(runId);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
      setRunningStage(null);
    }
  }

  async function handleResetRun() {
    if (
      !window.confirm(
        "Force reset this run's status? Only do this if it's genuinely stuck (not actually still working) -- " +
          "resetting a run that's truly still in progress can let two stages run at once.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.resetRun(runId);
      setRun(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function handleUseVersion(version: number) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.selectIcpVersion(runId, version);
      setRun(updated);
      setViewingVersion(updated.icp?.version ?? version);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveEdit() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const body: UpdateIcpBody = {
        lead_count: leadCount,
        confirm: false,
        target_company_type: draft.target_company_type,
        buyer_persona: draft.buyer_persona,
        headcount_range: draft.headcount_range,
        business_problem: draft.business_problem,
        industries: draft.industries,
        geography: draft.geography,
        hard_filters: draft.hard_filters.filter((v) => v.trim() !== ""),
        soft_preferences: draft.soft_preferences.filter((v) => v.trim() !== ""),
        disqualifiers: draft.disqualifiers.filter((v) => v.trim() !== ""),
      };
      const updated = await api.updateIcp(runId, body);
      setRun(updated);
      setViewingVersion(updated.icp?.version ?? null);
      setEditing(false);
      setDraft(null);
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
          <Alert message={error} />
        </div>
      </AppShell>
    );
  }
  if (!run || !run.icp) {
    return <LoadingLine />;
  }

  const currentVersion = run.icp.version;
  const viewedIcp = run.icp_versions.find((v) => v.version === viewingVersion) ?? run.icp;
  const isViewingCurrent = viewedIcp.version === currentVersion;
  const icpConfirmed = run.status !== "draft" && run.status !== "awaiting_icp_confirmation";
  const canEdit = isViewingCurrent && !icpConfirmed;
  const icp = editing && draft ? draft : viewedIcp;

  const hasDiscoveredLeads = run.leads.length > 0;
  const hasScrapedLeads = run.leads.some((l) => l.sources.length > 0);
  const discoveryDone = icpConfirmed && hasDiscoveredLeads && run.status !== "running";
  // Buffer/spare leads (Lead.is_buffer) aren't scrapeable yet -- they're
  // promoted into the primary pool via "use spare candidates" first.
  const discoveredLeadCount = run.leads.filter((l) => l.qualification_status === "discovered" && !l.is_buffer).length;
  const spareBufferCount = run.leads.filter((l) => l.qualification_status === "discovered" && l.is_buffer).length;
  const canStartScrape = discoveredLeadCount > 0 && run.status !== "running";

  // This is "did discovery+scraping deliver enough raw candidates into the
  // pipeline", not "do we have enough final qualified leads" -- qualifying
  // usually drops a good chunk further (a candidate that scraped fine can
  // still come back disqualified), which is a separate, likely larger
  // shortfall the Qualification tab surfaces on its own. A discovery
  // top-up widens the top of the funnel; it doesn't yet re-trigger itself
  // off a qualified-count shortfall specifically.
  const validLeadCount = run.leads.filter((l) => l.qualification_status === "scraped" || l.qualification_status === "qualified").length;
  const leadShortfall = Math.max(0, (run.lead_count_limit ?? 0) - validLeadCount);
  const canTopUpDiscovery = icpConfirmed && run.status !== "queued" && run.status !== "running" && leadShortfall > 0;

  const scrapedLeadCount = run.leads.filter((l) => l.qualification_status === "scraped" && !l.is_buffer).length;
  const canStartQualify = scrapedLeadCount > 0 && run.status !== "running";
  const hasQualifiedLeads = run.leads.some((l) =>
    ["qualified", "disqualified", "needs_review"].includes(l.qualification_status),
  );

  const undraftedQualifiedCount = run.leads.filter(
    (l) => !l.is_buffer && l.qualification_status === "qualified" && l.drafts.length === 0,
  ).length;
  const canStartDraft = undraftedQualifiedCount > 0 && run.status !== "running";
  const hasDrafts = run.leads.some((l) => l.drafts.length > 0);

  const stages: Stage[] = [
    { id: "icp", label: "ICP", status: icpConfirmed ? "completed" : "current" },
    {
      id: "discovery",
      label: "Discovery",
      status:
        runningStage === "discovery" ? "running" : discoveryDone ? "completed" : icpConfirmed ? "current" : "upcoming",
    },
    {
      id: "scraping",
      label: "Scraping",
      status:
        runningStage === "scraping" ? "running" : hasScrapedLeads ? "completed" : discoveryDone ? "current" : "upcoming",
    },
    {
      id: "qualification",
      label: "Qualification",
      status:
        runningStage === "qualification"
          ? "running"
          : hasQualifiedLeads
            ? "completed"
            : hasScrapedLeads
              ? "current"
              : "upcoming",
    },
    {
      id: "drafting",
      label: "Drafting",
      status:
        runningStage === "drafting"
          ? "running"
          : hasDrafts
            ? "completed"
            : hasQualifiedLeads
              ? "current"
              : "upcoming",
    },
  ];
  const activeStageId = stages[activeIndex].id;

  return (
    <AppShell>
      <ToolCallLogPanel runId={runId} />
      <div className="flex min-h-full flex-col">
        <StageStepper
          stages={stages}
          activeId={activeStageId}
          onSelect={(id) => navigateTo(stages.findIndex((s) => s.id === id))}
        />

        <div className="flex-1 px-4 py-10 sm:px-8">
          <div className="mx-auto max-w-3xl pb-24">
            <PhaseCarousel activeKey={activeStageId} direction={direction}>
              {activeStageId === "icp" && (
                <div className="space-y-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h1 className="text-2xl font-semibold text-foreground">Review your target profile</h1>
                      <p className="mt-2 text-sm italic text-muted-text">&ldquo;{run.objective}&rdquo;</p>
                    </div>
                    <ICPVersionHistory
                      versions={run.icp_versions}
                      currentVersion={currentVersion}
                      viewingVersion={viewedIcp.version}
                      onView={(v) => {
                        setViewingVersion(v);
                        setEditing(false);
                        setDraft(null);
                      }}
                    />
                  </div>

                  {!isViewingCurrent && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-5 py-4">
                      <p className="text-sm text-sky-900">
                        You&apos;re viewing version {viewedIcp.version} for reference. The run is currently set to
                        use version {currentVersion}.
                      </p>
                      {!icpConfirmed && (
                        <button
                          onClick={() => handleUseVersion(viewedIcp.version)}
                          disabled={busy}
                          className="shrink-0 rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-medium text-sky-900 transition-colors hover:bg-sky-100 disabled:opacity-50"
                        >
                          Use this version
                        </button>
                      )}
                    </div>
                  )}

                  <CardSection
                    title="At a glance"
                    action={
                      canEdit &&
                      (editing ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setEditing(false);
                              setDraft(null);
                            }}
                            disabled={busy}
                            className="rounded-lg border border-surface-border px-3 py-1 text-xs font-medium text-muted-text hover:text-foreground disabled:opacity-50"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={handleSaveEdit}
                            disabled={busy}
                            className="flex items-center gap-1.5 rounded-lg bg-primary-accent px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                          >
                            {busy && <Spinner className="text-white" />}
                            Save changes
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setDraft(draftFromIcp(viewedIcp));
                            setEditing(true);
                          }}
                          className="rounded-lg border border-surface-border px-3 py-1 text-xs font-medium text-muted-text hover:text-foreground"
                        >
                          Edit
                        </button>
                      ))
                    }
                  >
                    <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
                      {editing && draft ? (
                        <>
                          <EditableField
                            label="Target company type"
                            value={draft.target_company_type}
                            onChange={(v) => setDraft({ ...draft, target_company_type: v })}
                          />
                          <EditableField
                            label="Buyer persona"
                            value={draft.buyer_persona}
                            onChange={(v) => setDraft({ ...draft, buyer_persona: v })}
                          />
                          <EditableField
                            label="Headcount range"
                            value={draft.headcount_range}
                            onChange={(v) => setDraft({ ...draft, headcount_range: v })}
                          />
                          <EditableField
                            label="Business problem"
                            value={draft.business_problem}
                            onChange={(v) => setDraft({ ...draft, business_problem: v })}
                            fullWidth
                          />
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-muted-text">Industries</p>
                            <div className="mt-1.5">
                              <EditableTagList
                                items={draft.industries}
                                onChange={(v) => setDraft({ ...draft, industries: v })}
                              />
                            </div>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-wide text-muted-text">Geography</p>
                            <div className="mt-1.5">
                              <EditableTagList
                                items={draft.geography}
                                onChange={(v) => setDraft({ ...draft, geography: v })}
                              />
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <Fact label="Target company type" value={icp.target_company_type} />
                          <Fact label="Buyer persona" value={icp.buyer_persona} />
                          <Fact label="Headcount range" value={icp.headcount_range} />
                          <div className="sm:col-span-2">
                            <Fact label="Business problem" value={icp.business_problem} />
                          </div>
                          <ChipRow label="Industries" items={icp.industries} />
                          <ChipRow label="Geography" items={icp.geography} />
                        </>
                      )}
                    </div>
                  </CardSection>

                  <div className="glow-card grid grid-cols-1 divide-y divide-surface-border rounded-2xl border border-surface-border bg-surface-card sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                    <div className="p-6">
                      <h2 className="text-sm font-semibold text-emerald-700">Required</h2>
                      <p className="mt-0.5 text-xs text-muted-text">Must all be true</p>
                      <div className="mt-3">
                        {editing && draft ? (
                          <EditableCriteriaList
                            items={draft.hard_filters}
                            tone="positive"
                            onChange={(v) => setDraft({ ...draft, hard_filters: v })}
                            addLabel="Add requirement"
                          />
                        ) : (
                          <CriteriaList items={icp.hard_filters} tone="positive" />
                        )}
                      </div>
                    </div>
                    <div className="p-6">
                      <h2 className="text-sm font-semibold text-sky-700">Preferred</h2>
                      <p className="mt-0.5 text-xs text-muted-text">Improves fit, not a dealbreaker</p>
                      <div className="mt-3">
                        {editing && draft ? (
                          <EditableCriteriaList
                            items={draft.soft_preferences}
                            tone="neutral"
                            onChange={(v) => setDraft({ ...draft, soft_preferences: v })}
                            addLabel="Add preference"
                          />
                        ) : (
                          <CriteriaList items={icp.soft_preferences} tone="neutral" />
                        )}
                      </div>
                    </div>
                    <div className="p-6">
                      <h2 className="text-sm font-semibold text-rose-700">Excluded</h2>
                      <p className="mt-0.5 text-xs text-muted-text">Disqualifies a candidate</p>
                      <div className="mt-3">
                        {editing && draft ? (
                          <EditableCriteriaList
                            items={draft.disqualifiers}
                            tone="negative"
                            onChange={(v) => setDraft({ ...draft, disqualifiers: v })}
                            addLabel="Add exclusion"
                          />
                        ) : (
                          <CriteriaList items={icp.disqualifiers} tone="negative" emptyLabel="None specified." />
                        )}
                      </div>
                    </div>
                  </div>

                  {viewedIcp.assumptions_made.length > 0 && (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
                      <h2 className="text-sm font-semibold text-amber-900">Assumptions I made</h2>
                      <p className="mt-1 text-xs text-amber-800">Check these are right before confirming.</p>
                      <div className="mt-3">
                        <CriteriaList items={viewedIcp.assumptions_made} tone="neutral" maxVisible={3} />
                      </div>
                    </div>
                  )}

                  {viewedIcp.needs_confirmation.length > 0 && (
                    <div className="rounded-2xl border border-sky-200 bg-sky-50 p-6">
                      <h2 className="text-sm font-semibold text-sky-900">Best-effort only</h2>
                      <p className="mt-1 text-xs text-sky-800">Can&apos;t be reliably verified from web research.</p>
                      <div className="mt-3">
                        <CriteriaList items={viewedIcp.needs_confirmation} tone="neutral" maxVisible={3} />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeStageId === "discovery" && <DiscoveryPanel run={run} />}

              {activeStageId === "scraping" && <ScrapingPanel run={run} />}

              {activeStageId === "qualification" && <QualificationPanel run={run} />}

              {activeStageId === "drafting" && <DraftingPanel run={run} />}
            </PhaseCarousel>
          </div>
        </div>

        <div className="sticky bottom-0 border-t border-surface-border bg-surface-card px-4 py-4 sm:px-8">
          <div className="mx-auto max-w-3xl space-y-3">
            <div className="flex items-center justify-between gap-3">
              <RunStageSummary run={run} />
              <button
                type="button"
                onClick={toggleAutoContinue}
                title="When on, each stage automatically starts the next one as soon as it has work ready -- spends budget without a click in between."
                className="flex shrink-0 items-center gap-2 text-xs font-medium text-muted-text"
              >
                Auto-continue
                <span
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    autoContinue ? "bg-primary-accent" : "bg-surface-border"
                  }`}
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                      autoContinue ? "translate-x-[18px]" : "translate-x-[3px]"
                    }`}
                  />
                </span>
              </button>
            </div>

            {run.status === "running" && !busy && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="text-xs text-amber-900">
                  This run shows as running, but nothing here is waiting on it -- it may be stuck, or still running
                  from another tab or an earlier action.
                </p>
                <button
                  type="button"
                  onClick={handleResetRun}
                  className="shrink-0 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 transition-colors hover:bg-amber-100"
                >
                  Force reset
                </button>
              </div>
            )}

            {activeStageId === "icp" && (
              <div className="flex flex-wrap items-center justify-between gap-4">
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

                <button
                  onClick={handleConfirm}
                  disabled={busy || icpConfirmed || editing || !isViewingCurrent}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy && <Spinner className="text-white" />}
                  {icpConfirmed ? "Confirmed" : busy ? "Confirming..." : "Confirm and continue"}
                </button>
              </div>
            )}

            {activeStageId === "discovery" && run.status === "queued" && (
              <div className="flex items-center justify-end">
                <button
                  onClick={handleStartDiscovery}
                  disabled={busy}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy && <Spinner className="text-white" />}
                  {busy ? "Searching..." : "Start discovery"}
                </button>
              </div>
            )}

            {activeStageId === "discovery" && canTopUpDiscovery && (
              <div className="space-y-3">
                <p className="text-xs text-muted-text">
                  {validLeadCount} of {run.lead_count_limit} valid so far.{" "}
                  <button
                    type="button"
                    onClick={() => setTopUpCount(leadShortfall)}
                    className="underline decoration-dotted underline-offset-2 hover:text-foreground"
                  >
                    Suggested: {leadShortfall} more
                  </button>
                </p>

                {spareBufferCount > 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
                    <p className="text-xs text-emerald-900">
                      {spareBufferCount} spare candidate{spareBufferCount === 1 ? "" : "s"} already discovered
                      (no extra Apify spend) -- try these first.
                    </p>
                    <button
                      onClick={() => handleUseBuffer(Math.min(leadShortfall, spareBufferCount))}
                      disabled={busy}
                      className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {busy && <Spinner className="text-white" />}
                      Use {Math.min(leadShortfall, spareBufferCount)} spare candidate
                      {Math.min(leadShortfall, spareBufferCount) === 1 ? "" : "s"}
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-4">
                  <p className="text-xs text-muted-text">
                    Still short? Search for genuinely new candidates instead (uses more Apify budget).
                  </p>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min={1}
                      value={topUpCount}
                      onChange={(e) => setTopUpCount(Math.max(1, Number(e.target.value)))}
                      className="w-16 rounded-lg border border-surface-border bg-background px-2 py-1.5 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
                    />
                    <button
                      onClick={handleTopUpDiscovery}
                      disabled={busy}
                      className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {busy && <Spinner className="text-white" />}
                      {busy ? "Searching..." : `Get ${topUpCount} more candidate${topUpCount === 1 ? "" : "s"}`}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeStageId === "scraping" && canStartScrape && (
              <div className="flex items-center justify-end">
                <button
                  onClick={handleStartScrape}
                  disabled={busy}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy
                    ? "Scraping..."
                    : `Scrape ${discoveredLeadCount} candidate site${discoveredLeadCount === 1 ? "" : "s"}`}
                </button>
              </div>
            )}

            {activeStageId === "qualification" && canStartQualify && (
              <div className="flex items-center justify-end">
                <button
                  onClick={handleStartQualify}
                  disabled={busy}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy && <Spinner className="text-white" />}
                  {busy
                    ? "Qualifying..."
                    : `Qualify ${scrapedLeadCount} candidate${scrapedLeadCount === 1 ? "" : "s"}`}
                </button>
              </div>
            )}

            {activeStageId === "drafting" && canStartDraft && (
              <div className="flex items-center justify-end">
                <button
                  onClick={handleStartDraft}
                  disabled={busy}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy && <Spinner className="text-white" />}
                  {busy
                    ? "Drafting..."
                    : `Draft outreach for ${undraftedQualifiedCount} lead${undraftedQualifiedCount === 1 ? "" : "s"}`}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

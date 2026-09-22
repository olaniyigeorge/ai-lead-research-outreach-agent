"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert } from "@/components/Alert";
import { AppShell } from "@/components/AppShell";
import { CriteriaList } from "@/components/CriteriaList";
import { DiscoveryPanel } from "@/components/DiscoveryPanel";
import { EditableCriteriaList } from "@/components/EditableCriteriaList";
import { EditableTagList } from "@/components/EditableTagList";
import { ICPVersionHistory } from "@/components/ICPVersionHistory";
import { PhaseCarousel } from "@/components/PhaseCarousel";
import { LoadingLine, Spinner } from "@/components/Spinner";
import { Stage, StageStepper } from "@/components/StageStepper";
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

function ComingSoonPhase({ title, note }: { title: string; note: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
      <div className="rounded-2xl border border-dashed border-surface-border bg-surface-card p-8 text-center">
        <p className="text-sm text-muted-text">{note}</p>
      </div>
    </div>
  );
}

const COMING_SOON: Record<string, { title: string; note: string }> = {
  scraping: {
    title: "Scraping",
    note: "Not started yet -- website scraping runs after discovery finds candidate companies.",
  },
  qualification: {
    title: "Qualification",
    note: "Not started yet -- qualification runs after each candidate is scraped.",
  },
  drafting: {
    title: "Drafting",
    note: "Not started yet -- outreach drafts are generated for qualified leads.",
  },
};

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<RunOut | null>(null);
  const [leadCount, setLeadCount] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [viewingVersion, setViewingVersion] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DraftICP | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);

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
    setError(null);
    try {
      const updated = await api.startRun(runId);
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

  const stages: Stage[] = [
    { id: "icp", label: "ICP", status: icpConfirmed ? "completed" : "current" },
    { id: "discovery", label: "Discovery", status: "upcoming" },
    { id: "scraping", label: "Scraping", status: "upcoming" },
    { id: "qualification", label: "Qualification", status: "upcoming" },
    { id: "drafting", label: "Drafting", status: "upcoming" },
  ];
  const activeStageId = stages[activeIndex].id;

  return (
    <AppShell>
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

              {activeStageId !== "icp" && activeStageId !== "discovery" && (
                <ComingSoonPhase {...COMING_SOON[activeStageId]} />
              )}
            </PhaseCarousel>
          </div>
        </div>

        {activeStageId === "icp" && (
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
                  disabled={busy || icpConfirmed || editing || !isViewingCurrent}
                  className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy && <Spinner className="text-white" />}
                  {icpConfirmed ? "Confirmed" : busy ? "Confirming..." : "Confirm and continue"}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeStageId === "discovery" && run.status === "queued" && (
          <div className="sticky bottom-0 border-t border-surface-border bg-surface-card px-4 py-4 sm:px-8">
            <div className="mx-auto flex max-w-3xl items-center justify-end">
              <button
                onClick={handleStartDiscovery}
                disabled={busy}
                className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy && <Spinner className="text-white" />}
                {busy ? "Searching..." : "Start discovery"}
              </button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

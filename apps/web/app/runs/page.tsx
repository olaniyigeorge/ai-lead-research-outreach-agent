"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RunStatusBadge } from "@/components/RunStatusBadge";
import { LoadingLine } from "@/components/Spinner";
import { ApiError, RunSummary, api, getSession } from "@/lib/api-client";

const QUICK_FILTERS = [
  { id: "ALL", label: "All runs" },
  { id: "awaiting_icp_confirmation", label: "Awaiting confirmation" },
  { id: "queued", label: "Queued" },
  { id: "running", label: "Running" },
  { id: "completed", label: "Completed" },
  { id: "failed", label: "Failed" },
];

export default function RunsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    if (!getSession()) {
      router.push("/sign-in");
      return;
    }
    api
      .listRuns()
      .then(setRuns)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong"));
  }, [router]);

  const filteredRuns = useMemo(() => {
    if (!runs) return [];
    return runs.filter((r) => {
      const matchesSearch = search === "" || r.objective.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "ALL" || r.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [runs, search, statusFilter]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: runs?.length ?? 0 };
    (runs ?? []).forEach((r) => {
      counts[r.status] = (counts[r.status] ?? 0) + 1;
    });
    return counts;
  }, [runs]);

  if (error) {
    return (
      <AppShell>
        <div className="mx-auto max-w-4xl px-4 py-16">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      </AppShell>
    );
  }

  if (!runs) {
    return <LoadingLine />;
  }

  return (
    <AppShell>
      <div className="animate-fade-in-up mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-2xl font-semibold text-foreground">My runs</h1>

        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by objective..."
            className="w-full max-w-xs rounded-lg border border-surface-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
          />
          <div className="flex flex-wrap items-center gap-1">
            {QUICK_FILTERS.map((f) => {
              const count = statusCounts[f.id] ?? 0;
              const selected = statusFilter === f.id;
              return (
                <button
                  key={f.id}
                  onClick={() => setStatusFilter(f.id)}
                  className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    selected
                      ? "border border-primary-accent/30 bg-primary-accent/10 text-primary-accent"
                      : "border border-transparent text-muted-text hover:bg-surface-card-hover hover:text-foreground"
                  }`}
                >
                  {f.label}
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] ${
                      selected ? "bg-primary-accent/15" : "bg-surface-base text-muted-text"
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {filteredRuns.length === 0 ? (
          <div className="glow-card mt-6 rounded-2xl border border-surface-border bg-surface-card p-12 text-center">
            <h3 className="text-base font-semibold text-foreground">No runs found</h3>
            <p className="mt-1 text-sm text-muted-text">
              {search || statusFilter !== "ALL"
                ? "No runs matched your search or filter."
                : "Start a run from the New run page to see it here."}
            </p>
            <Link
              href="/"
              className="mt-4 inline-block rounded-lg border border-surface-border bg-surface-base px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-card-hover"
            >
              New run
            </Link>
          </div>
        ) : (
          <div className="glow-card mt-6 overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border bg-surface-base text-xs font-semibold uppercase tracking-wide text-muted-text">
                  <th className="px-6 py-3">Objective</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Lead count</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {filteredRuns.map((run) => (
                  <tr key={run.id} className="transition-colors hover:bg-surface-card-hover">
                    <td className="max-w-sm truncate px-6 py-4">
                      <Link href={`/runs/${run.id}`} className="hover:text-primary-accent">
                        {run.objective}
                      </Link>
                    </td>
                    <td className="px-4 py-4">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-4 text-muted-text">{run.lead_count_limit ?? "—"}</td>
                    <td className="whitespace-nowrap px-4 py-4 text-muted-text">
                      {new Date(run.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}

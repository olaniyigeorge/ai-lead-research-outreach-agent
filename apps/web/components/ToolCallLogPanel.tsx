"use client";

import { useEffect, useState } from "react";
import { ApiError, ToolCallLog, api } from "@/lib/api-client";
import { Spinner } from "@/components/Spinner";

const STAGE_LABELS: Record<string, string> = {
  icp: "ICP",
  discovery: "Discovery",
  scraping: "Scraping",
  qualification: "Qualification",
  drafting: "Drafting",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function LogRow({ log }: { log: ToolCallLog }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = log.input_summary || log.result_summary || log.error_message;

  return (
    <div className="border-b border-surface-border last:border-b-0">
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((v) => !v)}
        className={`flex w-full items-start justify-between gap-3 px-4 py-3 text-left ${
          hasDetail ? "cursor-pointer hover:bg-surface-base" : "cursor-default"
        }`}
      >
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{log.tool_name}</p>
          <p className="mt-0.5 text-xs text-muted-text">
            {formatTime(log.created_at)} &middot; {STAGE_LABELS[log.stage] ?? log.stage}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
            log.status === "error" ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
          }`}
        >
          {log.status}
        </span>
      </button>
      {expanded && hasDetail && (
        <div className="space-y-2 border-t border-surface-border bg-surface-base px-4 py-3">
          {log.error_message && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-rose-700">Error</p>
              <p className="mt-1 whitespace-pre-wrap text-xs text-foreground">{log.error_message}</p>
            </div>
          )}
          {log.input_summary && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-text">Input</p>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-xs text-foreground">
                {JSON.stringify(log.input_summary, null, 2)}
              </pre>
            </div>
          )}
          {log.result_summary && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-text">Result</p>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-xs text-foreground">
                {JSON.stringify(log.result_summary, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallLogPanel({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [logs, setLogs] = useState<ToolCallLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<string>("all");

  function fetchLogs() {
    api
      .listToolCalls(runId)
      .then((rows) => setLogs(rows))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load tool call logs"));
  }

  function refresh() {
    setError(null);
    fetchLogs();
  }

  useEffect(() => {
    if (!open || logs !== null) return;
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, runId]);

  const loading = open && logs === null && !error;

  const stages = logs ? Array.from(new Set(logs.map((l) => l.stage))) : [];
  const visibleLogs = logs
    ? [...logs].reverse().filter((l) => stageFilter === "all" || l.stage === stageFilter)
    : [];
  const errorCount = logs?.filter((l) => l.status === "error").length ?? 0;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="View tool call logs"
        className="glow-primary fixed right-5 top-3 z-40 flex items-center gap-2 rounded-full bg-primary-accent px-4 py-2 text-xs font-medium text-white shadow-lg transition-opacity hover:opacity-90"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
          <path
            fillRule="evenodd"
            d="M10 2a.75.75 0 0 1 .75.75v.51a7.5 7.5 0 0 1 6.99 6.99h.51a.75.75 0 0 1 0 1.5h-.51a7.5 7.5 0 0 1-6.99 6.99v.51a.75.75 0 0 1-1.5 0v-.51a7.5 7.5 0 0 1-6.99-6.99H1.75a.75.75 0 0 1 0-1.5h.51a7.5 7.5 0 0 1 6.99-6.99V2.75A.75.75 0 0 1 10 2Zm0 3.5a6 6 0 1 0 0 12 6 6 0 0 0 0-12Z"
            clipRule="evenodd"
          />
        </svg>
        Logs
      </button>

      {open && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/30 transition-opacity"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="animate-drawer-in absolute right-0 top-0 flex h-full w-full max-w-sm flex-col border-l border-surface-border bg-surface-card shadow-2xl">
            <div className="flex items-center justify-between gap-3 border-b border-surface-border px-4 py-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Tool call logs</h2>
                <p className="text-xs text-muted-text">
                  {logs ? `${logs.length} call${logs.length === 1 ? "" : "s"}` : "Loading..."}
                  {errorCount > 0 && <span className="text-rose-600"> &middot; {errorCount} error{errorCount === 1 ? "" : "s"}</span>}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={refresh}
                  aria-label="Refresh logs"
                  className="rounded-lg p-1.5 text-muted-text hover:bg-surface-base hover:text-foreground"
                >
                  <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                    <path
                      fillRule="evenodd"
                      d="M15.312 5.312a5.5 5.5 0 0 0-9.201 2.466.75.75 0 0 1-1.44-.416A7 7 0 0 1 16.5 4.032V2.75a.75.75 0 0 1 1.5 0v3.5a.75.75 0 0 1-.75.75h-3.5a.75.75 0 0 1 0-1.5h1.562Zm-10.624 9.376a5.5 5.5 0 0 0 9.201-2.466.75.75 0 1 1 1.44.416A7 7 0 0 1 3.5 15.968v1.282a.75.75 0 0 1-1.5 0v-3.5a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5H4.688Z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                  className="rounded-lg p-1.5 text-muted-text hover:bg-surface-base hover:text-foreground"
                >
                  <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                    <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                  </svg>
                </button>
              </div>
            </div>

            {stages.length > 1 && (
              <div className="flex flex-wrap gap-1.5 border-b border-surface-border px-4 py-3">
                <button
                  type="button"
                  onClick={() => setStageFilter("all")}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    stageFilter === "all" ? "bg-primary-accent text-white" : "bg-surface-base text-muted-text"
                  }`}
                >
                  All
                </button>
                {stages.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStageFilter(s)}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      stageFilter === s ? "bg-primary-accent text-white" : "bg-surface-base text-muted-text"
                    }`}
                  >
                    {STAGE_LABELS[s] ?? s}
                  </button>
                ))}
              </div>
            )}

            <div className="flex-1 overflow-y-auto">
              {loading && (
                <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-text">
                  <Spinner /> Loading logs...
                </div>
              )}
              {error && <p className="px-4 py-6 text-sm text-red-600">{error}</p>}
              {!loading && !error && visibleLogs.length === 0 && (
                <p className="px-4 py-6 text-sm text-muted-text">No tool calls logged yet for this run.</p>
              )}
              {!loading &&
                !error &&
                visibleLogs.length > 0 && (
                  <div>
                    {visibleLogs.map((log) => (
                      <LogRow key={log.id} log={log} />
                    ))}
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

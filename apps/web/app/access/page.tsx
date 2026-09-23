"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/Alert";
import { AppShell } from "@/components/AppShell";
import { Spinner } from "@/components/Spinner";
import { AccessRequestOut, AllowedActorOut, ApiError, api, getSession } from "@/lib/api-client";
import { useRouter } from "next/navigation";

type GrantMode = "email" | "domain";
type ExpiryChoice = "never" | "7d" | "30d" | "custom";

function computeExpiresAt(choice: ExpiryChoice, customValue: string): string | undefined {
  if (choice === "never") return undefined;
  if (choice === "7d") return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  if (choice === "30d") return new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
  return customValue ? new Date(customValue).toISOString() : undefined;
}

export default function AccessPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<AllowedActorOut[] | null>(null);
  const [requests, setRequests] = useState<AccessRequestOut[] | null>(null);
  const [notAuthorized, setNotAuthorized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const [mode, setMode] = useState<GrantMode>("email");
  const [value, setValue] = useState("");
  const [label, setLabel] = useState("");
  const [expiryChoice, setExpiryChoice] = useState<ExpiryChoice>("never");
  const [customExpiry, setCustomExpiry] = useState("");
  const [busy, setBusy] = useState(false);

  function loadEntries() {
    api
      .listAllowlist()
      .then(setEntries)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setNotAuthorized(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Something went wrong");
        }
      });
  }

  function loadRequests() {
    api
      .listAccessRequests()
      .then(setRequests)
      .catch(() => {}); // not authorized already surfaces via loadEntries; nothing extra to show here
  }

  useEffect(() => {
    if (!getSession()) {
      router.push("/sign-in");
      return;
    }
    loadEntries();
    loadRequests();
  }, [router]);

  async function handleDecideRequest(requestId: string, decision: "granted" | "rejected") {
    setError(null);
    setDecidingId(requestId);
    try {
      await api.decideAccessRequest(requestId, decision);
      loadRequests();
      if (decision === "granted") loadEntries();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setDecidingId(null);
    }
  }

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createAllowlistEntry({
        email: mode === "email" ? value.trim() : undefined,
        email_domain: mode === "domain" ? value.trim() : undefined,
        label: label.trim() || undefined,
        expires_at: computeExpiresAt(expiryChoice, customExpiry),
      });
      setValue("");
      setLabel("");
      setExpiryChoice("never");
      setCustomExpiry("");
      loadEntries();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(id: string) {
    setError(null);
    try {
      await api.deleteAllowlistEntry(id);
      loadEntries();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    }
  }

  if (notAuthorized) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center px-4">
          <p className="text-sm text-muted-text">You don&apos;t have access to this page.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-8">
        <h1 className="text-2xl font-semibold text-foreground">Access</h1>
        <p className="mt-2 text-sm text-muted-text">
          Grant an email address or an entire domain access to sign in, with an optional expiry.
        </p>

        <form
          onSubmit={handleGrant}
          className="glow-card mt-6 space-y-4 rounded-2xl border border-surface-border bg-surface-card p-6"
        >
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode("email")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                mode === "email" ? "bg-primary-accent/10 text-primary-accent" : "text-muted-text hover:bg-surface-base"
              }`}
            >
              Email
            </button>
            <button
              type="button"
              onClick={() => setMode("domain")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                mode === "domain" ? "bg-primary-accent/10 text-primary-accent" : "text-muted-text hover:bg-surface-base"
              }`}
            >
              Domain
            </button>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              {mode === "email" ? "Email address" : "Domain"}
            </label>
            <input
              required
              type={mode === "email" ? "email" : "text"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={mode === "email" ? "someone@example.com" : "example.com"}
              className="w-full rounded-lg border border-surface-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Label (optional)</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. cohort teammate"
              className="w-full rounded-lg border border-surface-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Expires</label>
            <div className="flex flex-wrap gap-2">
              {(["never", "7d", "30d", "custom"] as ExpiryChoice[]).map((choice) => (
                <button
                  key={choice}
                  type="button"
                  onClick={() => setExpiryChoice(choice)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    expiryChoice === choice
                      ? "bg-primary-accent/10 text-primary-accent"
                      : "text-muted-text hover:bg-surface-base"
                  }`}
                >
                  {choice === "never" ? "Never" : choice === "7d" ? "7 days" : choice === "30d" ? "30 days" : "Custom"}
                </button>
              ))}
            </div>
            {expiryChoice === "custom" && (
              <input
                type="datetime-local"
                value={customExpiry}
                onChange={(e) => setCustomExpiry(e.target.value)}
                className="mt-2 rounded-lg border border-surface-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
              />
            )}
          </div>

          <button
            type="submit"
            disabled={busy}
            className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy && <Spinner className="text-white" />}
            {busy ? "Granting..." : "Grant access"}
          </button>

          {error && <Alert message={error} />}
        </form>

        {requests && requests.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-foreground">
              Pending requests <span className="text-muted-text">({requests.length})</span>
            </h2>
            <div className="glow-card mt-3 divide-y divide-surface-border overflow-hidden rounded-2xl border border-surface-border bg-surface-card">
              {requests.map((req) => (
                <div key={req.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{req.email}</p>
                    <p className="text-xs text-muted-text">
                      {req.reason || "No reason given"} &middot;{" "}
                      {new Date(req.created_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => handleDecideRequest(req.id, "rejected")}
                      disabled={decidingId === req.id}
                      className="rounded-lg border border-surface-border px-3 py-1.5 text-xs font-medium text-muted-text transition-colors hover:bg-surface-base disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleDecideRequest(req.id, "granted")}
                      disabled={decidingId === req.id}
                      className="flex items-center gap-1.5 rounded-lg bg-primary-accent px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {decidingId === req.id && <Spinner className="text-white" />}
                      Grant
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8">
          <h2 className="text-sm font-semibold text-foreground">Currently granted</h2>
          {!entries ? (
            <p className="mt-2 text-sm text-muted-text">Loading...</p>
          ) : entries.length === 0 ? (
            <p className="mt-2 text-sm text-muted-text">No one has been granted access yet.</p>
          ) : (
            <div className="glow-card mt-3 overflow-x-auto rounded-2xl border border-surface-border bg-surface-card">
              <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-surface-border bg-surface-base text-xs font-semibold uppercase tracking-wide text-muted-text">
                    <th className="px-4 py-3">Who</th>
                    <th className="px-4 py-3">Label</th>
                    <th className="px-4 py-3">Last login</th>
                    <th className="px-4 py-3">Expires</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {entries.map((entry) => {
                    const expired = entry.expires_at ? new Date(entry.expires_at) < new Date() : false;
                    return (
                      <tr key={entry.id} className="hover:bg-surface-card-hover">
                        <td className="px-4 py-3">
                          <span className="font-medium text-foreground">
                            {entry.email ?? `*@${entry.email_domain}`}
                          </span>
                          {entry.is_admin && (
                            <span className="ml-2 rounded-full bg-primary-accent/10 px-2 py-0.5 text-[10px] font-medium text-primary-accent">
                              admin
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-muted-text">{entry.label ?? "—"}</td>
                        <td className="px-4 py-3 text-muted-text text-xs">
                          {entry.last_login_at
                            ? new Date(entry.last_login_at).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "Never"}
                        </td>
                        <td className="px-4 py-3">
                          {entry.expires_at ? (
                            <span className={expired ? "text-red-600" : "text-muted-text"}>
                              {new Date(entry.expires_at).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                              {expired ? " (expired)" : ""}
                            </span>
                          ) : (
                            <span className="text-muted-text">Never</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!entry.is_admin && (
                            <button
                              onClick={() => handleRevoke(entry.id)}
                              className="text-xs font-medium text-red-600 hover:underline"
                            >
                              Revoke
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

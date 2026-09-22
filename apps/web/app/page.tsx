"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/Alert";
import { AppShell } from "@/components/AppShell";
import { LoadingLine, Spinner } from "@/components/Spinner";
import { ApiError, api, getSession } from "@/lib/api-client";
import { looksLikeGibberish } from "@/lib/objective-validation";

const EXAMPLES = [
  "Find 10 US B2B SaaS companies with 10 to 100 employees that may need AI automation support.",
  "Find operations-heavy agencies in Canada with 20-50 employees.",
  "Find early-stage fintech startups hiring for operations roles.",
];

type Phase = "idle" | "validating" | "refining";

// The backend runs a free regex check, then a cheap Haiku sanity check,
// then (only if both pass) the expensive ICP-refinement call -- all within
// one HTTP request. There's no real signal from the server about which
// phase is active mid-flight, so this is a best-effort estimate of how long
// the free+cheap checks typically take, purely so the label doesn't lie by
// claiming "Refining" before refinement has actually started.
const ESTIMATED_VALIDATION_MS = 2000;

export default function Home() {
  const router = useRouter();
  const [objective, setObjective] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [checkedAuth, setCheckedAuth] = useState(false);
  const phaseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!getSession()) {
      router.push("/sign-in");
      return;
    }
    setCheckedAuth(true);
  }, [router]);

  useEffect(() => {
    return () => {
      if (phaseTimeoutRef.current) clearTimeout(phaseTimeoutRef.current);
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPhase("validating");
    phaseTimeoutRef.current = setTimeout(() => setPhase("refining"), ESTIMATED_VALIDATION_MS);
    try {
      const run = await api.createRun(objective);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      if (phaseTimeoutRef.current) clearTimeout(phaseTimeoutRef.current);
      setPhase("idle");
    }
  }

  if (!checkedAuth) {
    return <LoadingLine />;
  }

  const busy = phase !== "idle";
  const passesClientCheck = !looksLikeGibberish(objective);
  const showGibberishWarning = objective.trim().length >= 10 && !passesClientCheck;
  const buttonLabel = phase === "validating" ? "Checking..." : phase === "refining" ? "Refining..." : "Refine ICP";

  return (
    <AppShell>
      <div className="flex justify-center px-4 py-20">
      <div className="animate-fade-in-up w-full max-w-2xl">
        <h1 className="text-2xl font-semibold text-foreground">What kind of companies are you looking for?</h1>

        <form onSubmit={handleSubmit} className="glow-card mt-6 rounded-2xl border border-surface-border bg-surface-card p-6">
          <textarea
            required
            minLength={10}
            maxLength={2000}
            rows={4}
            disabled={busy}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="Find 10 US B2B SaaS companies with 10 to 100 employees..."
            className={`w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent disabled:opacity-60 ${
              showGibberishWarning ? "border-amber-300" : "border-surface-border"
            }`}
          />
          {showGibberishWarning && (
            <p className="mt-2 text-xs text-amber-700">
              That doesn&apos;t look like a real objective yet -- try describing the kind of companies you want researched.
            </p>
          )}
          <div className="mt-4 flex items-center gap-3">
            <button
              type="submit"
              disabled={busy || !passesClientCheck}
              className="glow-primary flex items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Spinner className="text-white" />}
              {buttonLabel}
            </button>
            {busy && <p className="text-sm text-muted-text">This can take a few seconds...</p>}
          </div>
        </form>

        <div className="mt-8">
          <p className="text-sm font-medium text-muted-text">Or try an example</p>
          <ul className="mt-2 space-y-2">
            {EXAMPLES.map((example) => (
              <li key={example}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setObjective(example)}
                  className="w-full rounded-lg border border-surface-border bg-surface-card px-4 py-3 text-left text-sm text-foreground transition-colors hover:border-surface-border-hover hover:bg-surface-card-hover disabled:opacity-60"
                >
                  {example}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {error && <Alert message={error} />}
      </div>
      </div>
    </AppShell>
  );
}

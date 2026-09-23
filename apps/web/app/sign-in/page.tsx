"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/Alert";
import { Spinner } from "@/components/Spinner";
import { ApiError, api, saveSession } from "@/lib/api-client";

const OTP_LENGTH = 8;

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<"email" | "otp">("email");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const otpInputRef = useRef<HTMLInputElement>(null);

  const [notAllowed, setNotAllowed] = useState(false);
  const [requestReason, setRequestReason] = useState("");
  const [requestSent, setRequestSent] = useState(false);
  const [requestBusy, setRequestBusy] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    if (step === "otp") otpInputRef.current?.focus();
  }, [step]);

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotAllowed(false);
    setBusy(true);
    try {
      await api.requestOtp(email);
      setStep("otp");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setNotAllowed(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestAccess() {
    setRequestError(null);
    setRequestBusy(true);
    try {
      await api.requestAccess(email, requestReason);
      setRequestSent(true);
    } catch (err) {
      setRequestError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setRequestBusy(false);
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      let session;
      try {
        session = await api.verifyOtp(email, otp);
      } catch (err) {
        // The backend already retries a transient JWKS-fetch blip a few
        // times internally (see apps/api/auth/jwt.py) before giving up with
        // a 503 -- if it still failed, the OTP code itself is still valid
        // (Supabase already accepted it), so one more client-side retry
        // after a short pause covers a slightly longer blip without making
        // the user re-type an 8-digit code for something that wasn't their
        // fault.
        if (!(err instanceof ApiError) || err.status !== 503) throw err;
        await new Promise((resolve) => setTimeout(resolve, 1500));
        session = await api.verifyOtp(email, otp);
      }
      saveSession(session, email);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-base px-4">
      <div className="animate-fade-in-up glow-card w-full max-w-sm rounded-2xl border border-surface-border bg-surface-card p-8">
        <h1 className="text-xl font-semibold text-foreground">Sign in</h1>
        <p className="mt-1 text-sm text-muted-text">
          {step === "email" ? "Enter your email to get a one-time code." : `We sent a code to ${email}.`}
        </p>

        {step === "email" ? (
          <form onSubmit={handleRequestOtp} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setNotAllowed(false);
                  setRequestSent(false);
                  setRequestError(null);
                }}
                className="w-full rounded-lg border border-surface-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
                placeholder="you@company.com"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="glow-primary flex w-full items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Spinner className="text-white" />}
              {busy ? "Sending..." : "Send code"}
            </button>

            {notAllowed && !requestSent && (
              <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3.5">
                <p className="text-xs text-amber-900">
                  <strong>{email}</strong> doesn&apos;t have access yet. Ask for it below -- an admin will review
                  your request.
                </p>
                <textarea
                  value={requestReason}
                  onChange={(e) => setRequestReason(e.target.value)}
                  placeholder="Why do you need access? (optional)"
                  rows={2}
                  className="w-full resize-none rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary-accent"
                />
                <button
                  type="button"
                  onClick={handleRequestAccess}
                  disabled={requestBusy}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-900 transition-colors hover:bg-amber-100 disabled:opacity-50"
                >
                  {requestBusy && <Spinner />}
                  {requestBusy ? "Requesting..." : "Request access"}
                </button>
                {requestError && <p className="text-xs text-red-600">{requestError}</p>}
              </div>
            )}
            {requestSent && (
              <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs text-emerald-900">
                Request sent -- you&apos;ll be able to sign in once an admin grants access.
              </p>
            )}
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} className="mt-6 space-y-4">
            <div>
              <div className="mb-1 flex items-baseline justify-between">
                <label htmlFor="otp" className="block text-sm font-medium text-foreground">
                  Code
                </label>
                <span className="text-xs text-muted-text">
                  {otp.length}/{OTP_LENGTH}
                </span>
              </div>
              <input
                ref={otpInputRef}
                id="otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="\d*"
                maxLength={OTP_LENGTH}
                minLength={OTP_LENGTH}
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, OTP_LENGTH))}
                className="w-full rounded-lg border border-surface-border bg-background px-3 py-3 text-center font-mono text-2xl tracking-[0.5em] text-foreground outline-none transition-colors focus:border-primary-accent"
                placeholder="00000000"
              />
            </div>
            <button
              type="submit"
              disabled={busy || otp.length !== OTP_LENGTH}
              className="glow-primary flex w-full items-center justify-center gap-2 rounded-lg bg-primary-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Spinner className="text-white" />}
              {busy ? "Verifying..." : "Verify"}
            </button>
          </form>
        )}

        {error && <Alert message={error} />}
      </div>
    </main>
  );
}

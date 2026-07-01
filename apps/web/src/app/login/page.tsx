"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiFetch, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

type Mode = "login" | "register";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "register" && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, fullName || undefined, orgName || undefined);
      }
      // Resolve the user's first org (the existing /auth/me → orgs[0] pattern) and
      // land them inside the CaptureOS app. New users start the onboarding wizard;
      // returning users go straight to Find. No org → fall back to the dashboard.
      const me = await apiFetch<Me>("/auth/me").catch(() => null);
      const firstOrgId = me?.orgs[0]?.orgId;
      if (firstOrgId) {
        router.replace(
          mode === "register"
            ? `/orgs/${firstOrgId}/onboarding`
            : `/orgs/${firstOrgId}/workspace/find`,
        );
      } else {
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <div className="w-full max-w-sm rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold tracking-tight">CaptureOS</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {mode === "login" ? "Sign in to your account" : "Create your account"}
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          {mode === "register" && (
            <Field
              label="Full name"
              value={fullName}
              onChange={setFullName}
              placeholder="Jane Doe"
            />
          )}
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@company.com"
            required
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            required
            minLength={mode === "register" ? 8 : undefined}
            hint={mode === "register" ? "At least 8 characters." : undefined}
          />
          {mode === "register" && (
            <Field
              label="Organization (optional)"
              value={orgName}
              onChange={setOrgName}
              placeholder="Acme LLC"
            />
          )}

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50"
          >
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-center text-sm text-neutral-500 hover:text-neutral-900"
        >
          {mode === "login"
            ? "Need an account? Sign up"
            : "Already have an account? Sign in"}
        </button>

        <p className="mt-6 border-t border-neutral-100 pt-4 text-center text-xs text-neutral-400">
          New to CaptureOS?{" "}
          <Link href="/how-it-works" className="text-neutral-600 underline hover:text-neutral-900">
            See how it works
          </Link>
        </p>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
  minLength,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
  hint?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-neutral-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
        className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900"
      />
      {hint && <span className="mt-1 block text-xs text-neutral-400">{hint}</span>}
    </label>
  );
}

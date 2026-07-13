"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button, Card, CaptureOSLogo, Eyebrow, Input } from "@/components/captureos";
import { captureosFontVars } from "@/lib/captureos-fonts";
import { apiFetch, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

type Mode = "login" | "register";

// Sign in / register — the CaptureOS front door. Themed identically to the
// onboarding wizard (same `.captureos` tokens, weave background, Card/Input/
// Button primitives) so there's no jarring light-theme flash between the
// landing page and the app behind it.
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
    <div
      className={`captureos ${captureosFontVars} gr-weave`}
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <Link href="/" style={{ textDecoration: "none", marginBottom: 30 }}>
        <CaptureOSLogo markSize={30} wordmarkSize={20} />
      </Link>

      <div style={{ width: "100%", maxWidth: 400 }}>
        <Card padding={32}>
          <Eyebrow style={{ marginBottom: 8 }}>{mode === "login" ? "Welcome back" : "Get started"}</Eyebrow>
          <h1
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 28,
              fontWeight: 400,
              color: "var(--gr-heading)",
              margin: "0 0 24px",
            }}
          >
            {mode === "login" ? "Sign in to your account" : "Create your account"}
          </h1>

          <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {mode === "register" && (
              <Field label="Full name" value={fullName} onChange={setFullName} placeholder="Jane Doe" />
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
                label="Organization · optional"
                value={orgName}
                onChange={setOrgName}
                placeholder="Acme LLC"
              />
            )}

            {error && (
              <p
                role="alert"
                style={{
                  margin: 0,
                  padding: "11px 14px",
                  borderRadius: 9,
                  background: "rgba(240,138,120,.12)",
                  border: "1px solid rgba(240,138,120,.32)",
                  color: "#F0A593",
                  fontSize: 13.5,
                  lineHeight: 1.5,
                }}
              >
                {error}
              </p>
            )}

            <Button type="submit" variant="primary" disabled={busy} style={{ width: "100%", justifyContent: "center", marginTop: 4 }}>
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            style={{
              marginTop: 18,
              width: "100%",
              textAlign: "center",
              fontSize: 13.5,
              color: "var(--gr-muted-2)",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontFamily: "var(--gr-font-sans)",
            }}
          >
            {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </Card>

        <p style={{ marginTop: 22, textAlign: "center", fontSize: 12.5, color: "var(--gr-muted-3)" }}>
          New to CaptureOS?{" "}
          <Link href="/#how" style={{ color: "var(--gr-muted-2)", textDecoration: "underline" }}>
            See how it works
          </Link>
        </p>
      </div>
    </div>
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
    <label style={{ display: "block" }}>
      <span
        style={{
          display: "block",
          fontFamily: "var(--gr-font-mono)",
          fontSize: 10.5,
          fontWeight: 600,
          letterSpacing: ".1em",
          textTransform: "uppercase",
          color: "var(--gr-muted-2)",
          marginBottom: 8,
        }}
      >
        {label}
      </span>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
      />
      {hint && (
        <span style={{ display: "block", marginTop: 6, fontSize: 12, color: "var(--gr-muted-3)" }}>
          {hint}
        </span>
      )}
    </label>
  );
}

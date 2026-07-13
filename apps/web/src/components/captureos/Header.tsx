"use client";

import { useState, type CSSProperties } from "react";
import Link from "next/link";

import { CaptureOSLogo } from "./Logo";

// The four primary workspace tabs. Slugs map 1:1 to routes under
// /orgs/[orgId]/workspace/<slug>.
export type WorkspaceTab = "find" | "copilot" | "pursue" | "stay";

const TABS: { slug: WorkspaceTab; label: string }[] = [
  { slug: "find", label: "Find" },
  { slug: "copilot", label: "Copilot" },
  { slug: "pursue", label: "Pursue" },
  { slug: "stay", label: "Stay eligible" },
];

// Secondary header link (Audit, Billing) — lower visual weight than the
// primary workspace tabs since neither is part of the Find/Copilot/Pursue/
// Stay job-based IA; both live one level down, reachable from every surface.
function SecondaryLink({ href, label }: { href: string; label: string }) {
  const [hover, setHover] = useState(false);
  return (
    <Link
      href={href}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontSize: 13,
        fontWeight: 600,
        color: hover ? "var(--gr-heading)" : "var(--gr-muted-3)",
        textDecoration: "none",
        transition: "color .12s ease",
      }}
    >
      {label}
    </Link>
  );
}

function NavTab({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <Link
      href={href}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: "100%",
        fontSize: 14,
        fontWeight: active ? 700 : 600,
        color: active || hover ? "var(--gr-heading)" : "var(--gr-muted-2)",
        textDecoration: "none",
        borderBottom: `2px solid ${active ? "var(--gr-green-bright)" : "transparent"}`,
        transition: "color .12s ease",
      }}
    >
      {label}
    </Link>
  );
}

// Profile-completeness ring button. The SVG ring fills proportionally to `pct`;
// links to the onboarding wizard ("Add more → find more").
function ProfileRingButton({ href, pct }: { href: string; pct: number }) {
  const [hover, setHover] = useState(false);
  const r = 15;
  const circumference = 2 * Math.PI * r;
  const filled = (Math.max(0, Math.min(100, pct)) / 100) * circumference;

  return (
    <Link
      href={href}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 11,
        padding: "6px 13px 6px 9px",
        borderRadius: 9,
        border: `1px solid ${hover ? "var(--gr-border-strong)" : "var(--gr-border)"}`,
        background: "var(--gr-surface)",
        textDecoration: "none",
      }}
    >
      <div style={{ position: "relative", width: 28, height: 28 }}>
        <svg width="28" height="28" viewBox="0 0 36 36" style={{ transform: "rotate(-90deg)" }}>
          <circle cx="18" cy="18" r={r} fill="none" stroke="var(--gr-border)" strokeWidth="4" />
          <circle
            cx="18"
            cy="18"
            r={r}
            fill="none"
            stroke="var(--gr-green-bright)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
          />
        </svg>
        <span
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--gr-font-mono)",
            fontSize: 9,
            fontWeight: 700,
            color: "var(--gr-green-bright)",
          }}
        >
          {pct}
        </span>
      </div>
      <div style={{ textAlign: "left", lineHeight: 1.25 }}>
        <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--gr-text)" }}>
          Profile {pct}% complete
        </div>
        <div
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 9.5,
            color: "var(--gr-green-bright)",
            fontWeight: 600,
            letterSpacing: ".04em",
            textTransform: "uppercase",
          }}
        >
          Add more → find more
        </div>
      </div>
    </Link>
  );
}

const HEADER: CSSProperties = {
  position: "sticky",
  top: 0,
  zIndex: 30,
  background: "rgba(22,19,14,.88)",
  backdropFilter: "blur(10px)",
  WebkitBackdropFilter: "blur(10px)",
  borderBottom: "1px solid var(--gr-border-soft)",
};

export function CaptureOSHeader({
  orgId,
  activeTab,
  profilePct = 60,
  initials = "GR",
}: {
  orgId: string;
  activeTab: WorkspaceTab | null;
  profilePct?: number;
  initials?: string;
}) {
  const base = `/orgs/${orgId}/workspace`;
  return (
    <header style={HEADER}>
      <div
        style={{
          maxWidth: 1160,
          margin: "0 auto",
          padding: "0 28px",
          height: 64,
          display: "flex",
          alignItems: "center",
          gap: 24,
        }}
      >
        <Link href={`${base}/find`} style={{ textDecoration: "none" }}>
          <CaptureOSLogo pro />
        </Link>

        <nav style={{ display: "flex", gap: 20, alignSelf: "stretch", alignItems: "center" }}>
          {TABS.map((t) => (
            <NavTab
              key={t.slug}
              href={`${base}/${t.slug}`}
              label={t.label}
              active={activeTab === t.slug}
            />
          ))}
        </nav>

        <div style={{ flex: 1 }} />

        <div style={{ display: "flex", gap: 18 }}>
          <SecondaryLink href={`/orgs/${orgId}/workspace/audit`} label="Audit" />
          <SecondaryLink href={`/orgs/${orgId}/workspace/billing`} label="Billing" />
        </div>

        <ProfileRingButton href={`/orgs/${orgId}/onboarding`} pct={profilePct} />

        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            background: "var(--gr-green)",
            color: "var(--gr-on-green)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 13,
          }}
        >
          {initials}
        </div>
      </div>
    </header>
  );
}

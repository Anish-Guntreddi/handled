"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Eyebrow } from "@/components/granted";
import { apiFetch, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Obligation } from "@/lib/types";

// Stay eligible — the retention surface. Dated renewal/report obligations the
// org must keep current (SAM.gov renewal, WOSB recert, SBIR progress reports,
// tax filings). Each card shows how long until it's due (or how overdue), a
// reminder toggle, and a "Mark done" action, grouped by urgency.
//
// Backend (read-only here):
//   GET   /orgs/{orgId}/obligations          → Obligation[]
//   PATCH /orgs/{orgId}/obligations/{id}      { status, dueDate, notifyLeadDays }
// "Mark done"      → PATCH { status: "completed" }  (undo → "upcoming")
// "Reminder" toggle→ PATCH { notifyLeadDays: 30 | 0 } (persisted server-side)
//
// GAP: ObligationResponse omits notifyLeadDays, so the server's current
// reminder state can't be read back on load. We seed reminders ON for active
// obligations and persist each toggle; see REMINDER_ON / reminderState below.

const REMINDER_ON = 30; // lead-days written when a reminder is switched on
const REMINDER_OFF = 0; // lead-days written when switched off

// ---------------------------------------------------------------------------
// Urgency derives from days-until-due (independent of the server status string
// so the surface stays correct even between sync passes). Matches the design's
// amber/red bands: overdue / due soon (≤14) / coming up (≤30) / on track.
type Urgency = "overdue" | "due_soon" | "coming_up" | "on_track" | "done";

type UrgencyTheme = {
  /** stub bg/text + card border accent */
  accent: string;
  stubBg: string;
  stubBorder: string;
  cardBorder: string;
  tagLabel: string;
  tagBg: string;
  tagColor: string;
};

const THEMES: Record<Urgency, UrgencyTheme> = {
  overdue: {
    accent: "#f0a593",
    stubBg: "rgba(240,138,120,.16)",
    stubBorder: "rgba(240,138,120,.32)",
    cardBorder: "rgba(240,138,120,.32)",
    tagLabel: "Overdue",
    tagBg: "rgba(240,138,120,.16)",
    tagColor: "#f0a593",
  },
  due_soon: {
    accent: "#f0a593",
    stubBg: "rgba(240,138,120,.16)",
    stubBorder: "rgba(240,138,120,.32)",
    cardBorder: "rgba(240,138,120,.32)",
    tagLabel: "Due soon",
    tagBg: "rgba(240,138,120,.16)",
    tagColor: "#f0a593",
  },
  coming_up: {
    accent: "var(--gr-amber)",
    stubBg: "rgba(242,182,92,.15)",
    stubBorder: "rgba(242,182,92,.32)",
    cardBorder: "rgba(242,182,92,.32)",
    tagLabel: "Coming up",
    tagBg: "rgba(242,182,92,.15)",
    tagColor: "var(--gr-amber)",
  },
  on_track: {
    accent: "#74d89b",
    stubBg: "rgba(46,158,102,.15)",
    stubBorder: "rgba(116,216,155,.3)",
    cardBorder: "rgba(116,216,155,.3)",
    tagLabel: "On track",
    tagBg: "rgba(46,158,102,.16)",
    tagColor: "#74d89b",
  },
  done: {
    accent: "var(--gr-muted-3)",
    stubBg: "var(--gr-surface-raised)",
    stubBorder: "var(--gr-border)",
    cardBorder: "var(--gr-border)",
    tagLabel: "Done",
    tagBg: "rgba(46,158,102,.16)",
    tagColor: "#74d89b",
  },
};

// Whole-day difference between today (local midnight) and an ISO date. Positive
// = days remaining, negative = days overdue, 0 = due today.
function daysUntil(iso: string): number {
  const due = new Date(`${iso}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const ms = due.getTime() - today.getTime();
  return Math.round(ms / 86_400_000);
}

function isDone(o: Obligation): boolean {
  return o.status === "completed" || o.status === "dismissed";
}

function urgencyOf(o: Obligation, days: number): Urgency {
  if (isDone(o)) return "done";
  if (days < 0) return "overdue";
  if (days <= 14) return "due_soon";
  if (days <= 30) return "coming_up";
  return "on_track";
}

// "due in 5 days" / "due today" / "overdue by 3 days" / "Marked done".
function dueText(o: Obligation, days: number): string {
  if (isDone(o)) return "Marked done";
  if (days < 0) {
    const n = Math.abs(days);
    return `Overdue by ${n} ${n === 1 ? "day" : "days"}`;
  }
  if (days === 0) return "Due today";
  return `Due in ${days} ${days === 1 ? "day" : "days"}`;
}

// Stub's big number: ✓ when done, "!" when overdue, otherwise the day count.
function stubNumber(o: Obligation, days: number): string {
  if (isDone(o)) return "✓";
  if (days < 0) return "!";
  return String(days);
}

// Humanize the obligation kind for the meta line (sba_recert → "SBA recert").
function prettyKind(kind: string): string {
  const t = kind.replace(/[_-]+/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "Renewal";
}

// ---------------------------------------------------------------------------
export default function StayPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Reminder on/off is local: the GET response omits notifyLeadDays, so we
  // can't read the server's current state. Active obligations default ON.
  const [reminderState, setReminderState] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const obligationsQuery = useQuery({
    queryKey: ["obligations", orgId],
    queryFn: () => apiFetch<Obligation[]>(`/orgs/${orgId}/obligations`),
    enabled: isAuthenticated,
  });

  const patch = useMutation({
    mutationFn: (vars: { id: string; body: Record<string, unknown> }) =>
      apiFetch<Obligation>(`/orgs/${orgId}/obligations/${vars.id}`, {
        method: "PATCH",
        body: vars.body,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["obligations", orgId] }),
  });

  const items = useMemo(() => obligationsQuery.data ?? [], [obligationsQuery.data]);

  // Sort by due date (soonest first); done items always sink to the bottom.
  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      const ad = isDone(a) ? 1 : 0;
      const bd = isDone(b) ? 1 : 0;
      if (ad !== bd) return ad - bd;
      return a.dueDate.localeCompare(b.dueDate);
    });
  }, [items]);

  // Group by urgency band so the page reads "overdue · due soon · upcoming".
  const groups = useMemo(() => {
    const buckets: { key: Urgency; label: string; rows: Obligation[] }[] = [
      { key: "overdue", label: "Overdue", rows: [] },
      { key: "due_soon", label: "Due soon", rows: [] },
      { key: "coming_up", label: "Upcoming", rows: [] },
      { key: "on_track", label: "Upcoming", rows: [] },
      { key: "done", label: "Completed", rows: [] },
    ];
    for (const o of sorted) {
      const u = urgencyOf(o, daysUntil(o.dueDate));
      buckets.find((b) => b.key === u)?.rows.push(o);
    }
    // Merge "coming_up" + "on_track" under one "Upcoming" header.
    const merged: { label: string; rows: Obligation[] }[] = [];
    for (const b of buckets) {
      if (b.rows.length === 0) continue;
      const last = merged[merged.length - 1];
      if (last && last.label === b.label) last.rows.push(...b.rows);
      else merged.push({ label: b.label, rows: [...b.rows] });
    }
    return merged;
  }, [sorted]);

  function reminderOn(o: Obligation): boolean {
    if (o.id in reminderState) return reminderState[o.id];
    return !isDone(o); // default ON for active obligations
  }

  function toggleReminder(o: Obligation) {
    const next = !reminderOn(o);
    setReminderState((s) => ({ ...s, [o.id]: next }));
    patch.mutate({
      id: o.id,
      body: { notifyLeadDays: next ? REMINDER_ON : REMINDER_OFF },
    });
  }

  function toggleDone(o: Obligation) {
    patch.mutate({
      id: o.id,
      body: { status: isDone(o) ? "upcoming" : "completed" },
    });
  }

  if (loading || !isAuthenticated) {
    return (
      <div
        style={{ display: "grid", minHeight: "60vh", placeItems: "center", color: "var(--gr-muted-3)" }}
      >
        Loading…
      </div>
    );
  }

  return (
    <div style={{ paddingTop: 44 }}>
      <Eyebrow style={{ marginBottom: 8 }}>Keep what you&rsquo;ve won</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 46,
          fontWeight: 400,
          lineHeight: 1,
          letterSpacing: "-.01em",
          margin: "0 0 10px",
          color: "var(--gr-heading)",
        }}
      >
        Stay eligible
      </h1>
      <p style={{ margin: "0 0 30px", color: "var(--gr-muted)", fontSize: 16, maxWidth: 660 }}>
        The renewals and reports that keep your money flowing. Miss one and you can lose a
        certification — so we track them all and remind you early.
      </p>

      {obligationsQuery.isLoading ? (
        <ObligationSkeleton />
      ) : obligationsQuery.isError ? (
        <ErrorState
          message={errorMessage(obligationsQuery.error, "Couldn't load your renewals.")}
          onRetry={() => obligationsQuery.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          {groups.map((group) => (
            <section key={group.label}>
              <Eyebrow style={{ marginBottom: 12 }}>
                {group.label} · {group.rows.length}
              </Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {group.rows.map((o) => (
                  <ObligationCard
                    key={o.id}
                    obligation={o}
                    reminderOn={reminderOn(o)}
                    pending={patch.isPending}
                    onToggleReminder={() => toggleReminder(o)}
                    onToggleDone={() => toggleDone(o)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
function ObligationCard({
  obligation,
  reminderOn,
  pending,
  onToggleReminder,
  onToggleDone,
}: {
  obligation: Obligation;
  reminderOn: boolean;
  pending: boolean;
  onToggleReminder: () => void;
  onToggleDone: () => void;
}) {
  const days = daysUntil(obligation.dueDate);
  const urgency = urgencyOf(obligation, days);
  const theme = THEMES[urgency];
  const done = isDone(obligation);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        background: "var(--gr-surface)",
        border: `1px solid ${theme.cardBorder}`,
        borderRadius: "var(--gr-radius-card)",
        overflow: "hidden",
        opacity: done ? 0.55 : 1,
      }}
    >
      {/* ---- Left "days" stub ---- */}
      <div
        style={{
          flexShrink: 0,
          width: 78,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: theme.stubBg,
          color: theme.accent,
          borderRight: `1px dashed ${theme.stubBorder}`,
        }}
      >
        <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 30, fontWeight: 400, lineHeight: 1 }}>
          {stubNumber(obligation, days)}
        </div>
        <div
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 9,
            fontWeight: 600,
            letterSpacing: ".1em",
            marginTop: 3,
          }}
        >
          {done ? "DONE" : "DAYS"}
        </div>
      </div>

      {/* ---- Body ---- */}
      <div
        style={{
          flex: 1,
          minWidth: 200,
          padding: "18px 20px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
            <span style={{ display: "flex", color: theme.accent }}>
              <ObligationIcon kind={obligation.kind} />
            </span>
            <h3
              style={{
                fontSize: 17,
                fontWeight: 700,
                margin: 0,
                letterSpacing: "-.01em",
                color: done ? "var(--gr-muted-3)" : "var(--gr-text-strong)",
                textDecoration: done ? "line-through" : "none",
              }}
            >
              {obligation.title}
            </h3>
            <span
              style={{
                borderRadius: 5,
                padding: "2px 8px",
                fontFamily: "var(--gr-font-mono)",
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: ".04em",
                textTransform: "uppercase",
                background: theme.tagBg,
                color: theme.tagColor,
              }}
            >
              {theme.tagLabel}
            </span>
          </div>
          <div
            style={{
              fontFamily: "var(--gr-font-mono)",
              fontSize: 12,
              color: "var(--gr-muted-3)",
              marginTop: 4,
            }}
          >
            {prettyKind(obligation.kind)} · {obligation.recurrence} · {dueText(obligation, days)}
          </div>
        </div>

        {/* ---- Actions ---- */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button
            type="button"
            onClick={onToggleReminder}
            disabled={pending}
            aria-pressed={reminderOn}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              background: "none",
              border: "none",
              cursor: pending ? "default" : "pointer",
              fontSize: 12.5,
              fontWeight: 700,
              color: reminderOn ? "#74d89b" : "var(--gr-muted-3)",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: reminderOn ? "var(--gr-green-bright-2)" : "var(--gr-border-strong)",
              }}
            />
            {reminderOn ? "Reminder on" : "Reminder off"}
          </button>

          <DoneButton done={done} pending={pending} onClick={onToggleDone} />
        </div>
      </div>
    </div>
  );
}

function DoneButton({
  done,
  pending,
  onClick,
}: {
  done: boolean;
  pending: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const style: CSSProperties = done
    ? {
        padding: "8px 15px",
        borderRadius: 8,
        border: "1px solid var(--gr-border-input)",
        background: hover ? "var(--gr-hover)" : "var(--gr-input)",
        color: "#c9bea4",
        fontSize: 13,
        fontWeight: 700,
        cursor: pending ? "default" : "pointer",
      }
    : {
        padding: "8px 15px",
        borderRadius: 8,
        border: "none",
        background: hover ? "var(--gr-green-hover)" : "var(--gr-green)",
        color: "var(--gr-on-green)",
        fontSize: 13,
        fontWeight: 700,
        cursor: pending ? "default" : "pointer",
      };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={style}
    >
      {done ? "Undo" : "Mark done"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Per-kind glyph (15px, currentColor) so the icon tints with the urgency band.
function ObligationIcon({ kind }: { kind: string }) {
  const common = {
    width: 15,
    height: 15,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    style: { flexShrink: 0 },
  };
  const k = kind.toLowerCase();
  if (k.includes("sam") || k.includes("registration")) {
    return (
      <svg {...common}>
        <path d="M12 3l7 3v5c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z" />
        <path d="M9 11.5l2 2 4-4" />
      </svg>
    );
  }
  if (k.includes("tax")) {
    return (
      <svg {...common}>
        <path d="M6 3h12v18l-2-1.3-2 1.3-2-1.3-2 1.3-2-1.3L6 21z" />
        <path d="M9 8h6M9 12h4" />
      </svg>
    );
  }
  if (k.includes("recert") || k.includes("cert") || k.includes("wosb") || k.includes("set")) {
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="5" />
        <path d="M8.5 12.4 7 21l5-2.6L17 21l-1.5-8.6" />
      </svg>
    );
  }
  if (k.includes("report") || k.includes("sbir") || k.includes("grant")) {
    return (
      <svg {...common}>
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
        <path d="M14 3v5h5" />
        <path d="M9 13h6M9 17h4" />
      </svg>
    );
  }
  // Default: a calendar.
  return (
    <svg {...common}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 9h18M8 3v4M16 3v4" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
function EmptyState() {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "70px 20px",
        background: "var(--gr-surface)",
        border: "1px dashed var(--gr-border-input)",
        borderRadius: "var(--gr-radius-card)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 24,
          marginBottom: 6,
          color: "var(--gr-heading)",
        }}
      >
        You&rsquo;re all caught up
      </div>
      <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: 0 }}>
        No renewals due — we&rsquo;ll surface them here the moment one comes up.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "70px 20px",
        background: "var(--gr-surface)",
        border: "1px dashed var(--gr-border-input)",
        borderRadius: "var(--gr-radius-card)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 24,
          marginBottom: 6,
          color: "var(--gr-heading)",
        }}
      >
        Couldn&rsquo;t load your renewals
      </div>
      <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: "0 0 18px" }}>{message}</p>
      <button
        type="button"
        onClick={onRetry}
        style={{
          padding: "11px 18px",
          borderRadius: 9,
          background: "var(--gr-green)",
          color: "var(--gr-on-green)",
          border: "none",
          fontWeight: 700,
          fontSize: 14,
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </div>
  );
}

function ObligationSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "stretch",
            background: "var(--gr-surface)",
            border: "1px solid var(--gr-border)",
            borderRadius: "var(--gr-radius-card)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              flexShrink: 0,
              width: 78,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              background: "var(--gr-input)",
              borderRight: "1px dashed var(--gr-border)",
            }}
          >
            <SkeletonBar width={28} height={26} />
            <SkeletonBar width={26} height={8} />
          </div>
          <div
            style={{
              flex: 1,
              padding: "18px 20px",
              display: "flex",
              alignItems: "center",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: 9 }}>
              <SkeletonBar width={220} height={16} />
              <SkeletonBar width={260} height={12} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <SkeletonBar width={92} height={14} />
              <SkeletonBar width={92} height={30} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SkeletonBar({ width, height }: { width: number; height: number }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 6,
        background:
          "linear-gradient(90deg, var(--gr-hover) 25%, var(--gr-surface-raised) 50%, var(--gr-hover) 75%)",
        backgroundSize: "200% 100%",
        animation: "gr-shimmer 1.4s ease-in-out infinite",
      }}
    />
  );
}

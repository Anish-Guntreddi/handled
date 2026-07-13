"use client";

import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type FormEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, EligibilityBadge, Eyebrow, Input } from "@/components/captureos";
import { ApiError, apiFetch, pollWorkflowRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Discovery, DiscoveryItem, Me, WorkflowRunCreated } from "@/lib/types";

// Find — the hero/payoff surface. A live "money on the table" estimate over the
// org's discovery feed (programs + open contracts), each row carrying eligibility,
// why-you-qualify, a citation, and a CTA into Pursue. The scan button kicks the
// async program scan (202 → poll → refetch); the prompt routes to Copilot.

// ---------------------------------------------------------------------------
// Filter taxonomy. Items are filtered client-side by a derived category slug so
// the chips line up with the design's [All · Loans · Grants · R&D · Tax credit ·
// Contracts · Set-aside]. The data contract gives a precise `typeLabel`; we map
// it to a slug, falling back to `kind` when the label is unfamiliar.
type FilterKey = "all" | "loan" | "grant" | "sbir" | "credit" | "contract" | "setaside";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "loan", label: "Loans" },
  { key: "grant", label: "Grants" },
  { key: "sbir", label: "R&D" },
  { key: "credit", label: "Tax credit" },
  { key: "contract", label: "Contracts" },
  { key: "setaside", label: "Set-aside" },
];

function categoryOf(item: DiscoveryItem): Exclude<FilterKey, "all"> {
  const t = (item.typeLabel ?? "").toLowerCase();
  if (t.includes("set-aside") || t.includes("set aside") || t.includes("setaside")) return "setaside";
  if (t.includes("sbir") || t.includes("sttr") || t.includes("r&d") || t.includes("r & d")) return "sbir";
  if (t.includes("tax") || t.includes("credit")) return "credit";
  if (t.includes("loan")) return "loan";
  if (t.includes("contract")) return "contract";
  if (t.includes("grant")) return "grant";
  if (item.kind === "gov_contract") return "contract";
  if (item.kind === "grant") return "grant";
  return "grant";
}

// Compact USD formatting for the hero estimate and per-row benefit ($2.3M, $45K).
function formatMoney(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "$0";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${trim(value / 1_000_000)}M`;
  if (abs >= 1_000) return `$${trim(value / 1_000)}K`;
  return `$${Math.round(value).toLocaleString()}`;
}

function trim(n: number): string {
  // One decimal place, but drop a trailing ".0".
  const s = n.toFixed(1);
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

// ---------------------------------------------------------------------------
// Type icons (15px, currentColor stroke) — mirror the design's per-type glyphs.
function TypeIcon({ category }: { category: Exclude<FilterKey, "all"> }) {
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
  switch (category) {
    case "loan":
      return (
        <svg {...common}>
          <rect x="2.5" y="6" width="19" height="12" rx="2" />
          <circle cx="12" cy="12" r="2.4" />
          <path d="M6 9.5h.01M18 14.5h.01" />
        </svg>
      );
    case "grant":
      return (
        <svg {...common}>
          <circle cx="12" cy="8" r="5" />
          <path d="M8.5 12.4 7 21l5-2.6L17 21l-1.5-8.6" />
        </svg>
      );
    case "sbir":
      return (
        <svg {...common}>
          <path d="M9 3h6M10 3v5.5L5.2 17.4A2 2 0 0 0 7 20.4h10a2 2 0 0 0 1.8-3L14 8.5V3" />
          <path d="M8 14.5h8" />
        </svg>
      );
    case "credit":
      return (
        <svg {...common}>
          <path d="M6 3h12v18l-2-1.3-2 1.3-2-1.3-2 1.3-2-1.3L6 21z" />
          <path d="M9 8h6M9 12h4" />
        </svg>
      );
    case "contract":
      return (
        <svg {...common}>
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          <path d="M14 3v5h5" />
          <path d="M9 13h6M9 17h4" />
        </svg>
      );
    case "setaside":
      return (
        <svg {...common}>
          <path d="M12 3l7 3v5c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z" />
          <path d="M9 11.5l2 2 4-4" />
        </svg>
      );
  }
}

function AllIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <circle cx="6" cy="6" r="2.2" />
      <circle cx="18" cy="6" r="2.2" />
      <circle cx="6" cy="18" r="2.2" />
      <circle cx="18" cy="18" r="2.2" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#5C5444"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.5 1.5" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.5-1.5" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#0C1A11"
      strokeWidth={2.4}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
export default function FindPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  // Org name powers the hero headline; pulled from the membership list on /auth/me.
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/auth/me"),
    enabled: isAuthenticated,
  });
  const orgName = meQuery.data?.orgs.find((o) => o.orgId === orgId)?.name ?? "Your company";

  const discoveryQuery = useQuery({
    queryKey: ["discovery", orgId],
    queryFn: () => apiFetch<Discovery>(`/orgs/${orgId}/discovery`),
    enabled: isAuthenticated,
  });

  // Scan: POST /programs/scan (202 → workflowRunId), poll to terminal, then
  // refetch the discovery feed. The button shows a scanning spinner meanwhile.
  const scan = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/programs/scan`,
        { method: "POST", body: {} },
      );
      const run = await pollWorkflowRun(orgId, workflowRunId, { maxAttempts: 60 });
      if (run.status !== "succeeded") {
        throw new ApiError(500, "scan_failed", run.error ?? "Scan failed");
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["discovery", orgId] }),
  });

  const data = discoveryQuery.data;
  const items = useMemo(() => data?.items ?? [], [data]);
  const filtered = useMemo(
    () => (filter === "all" ? items : items.filter((it) => categoryOf(it) === filter)),
    [items, filter],
  );

  function submitPrompt(e: FormEvent) {
    e.preventDefault();
    const q = prompt.trim();
    const base = `/orgs/${orgId}/workspace/copilot`;
    router.push(q ? `${base}?q=${encodeURIComponent(q)}` : base);
  }

  if (loading || !isAuthenticated) {
    return (
      <div style={{ display: "grid", minHeight: "60vh", placeItems: "center", color: "var(--gr-muted-3)" }}>
        Loading…
      </div>
    );
  }

  return (
    <div>
      {/* ===== Hero ===== */}
      <section
        className="gr-weave"
        style={{
          position: "relative",
          overflow: "hidden",
          margin: "0 -28px",
          padding: "50px 28px 44px",
          borderBottom: "1px solid var(--gr-border-soft)",
        }}
      >
        <Eyebrow
          color="var(--gr-green-bright)"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            letterSpacing: ".14em",
            marginBottom: 20,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--gr-green-bright-2)",
              boxShadow: "0 0 8px var(--gr-green-bright-2)",
            }}
          />
          Live · {(data?.scanCount ?? 0).toLocaleString()} programs scanned · refreshes daily
        </Eyebrow>

        <div style={{ fontSize: 19, fontWeight: 600, color: "var(--gr-muted)", marginBottom: 4 }}>
          {orgName}, you may qualify for
        </div>

        <h1
          className="gr-animate-rise"
          style={{
            fontFamily: "var(--gr-font-serif)",
            fontSize: 96,
            fontWeight: 400,
            lineHeight: 0.9,
            letterSpacing: "-.02em",
            color: "var(--gr-green-bright)",
            margin: "0 0 14px",
          }}
        >
          ≈ {formatMoney(data?.totalEstimate ?? 0)}
        </h1>

        <p
          style={{
            margin: "0 0 26px",
            color: "var(--gr-muted)",
            fontSize: 17,
            lineHeight: 1.5,
            maxWidth: 600,
          }}
        >
          on the table you haven&rsquo;t claimed — across {data?.programsCount ?? 0} programs and{" "}
          {data?.contractsCount ?? 0} open contracts. Here&rsquo;s exactly what, and{" "}
          <span
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontStyle: "italic",
              fontSize: 19,
              color: "#9FD8B5",
            }}
          >
            why you qualify.
          </span>
        </p>

        <form
          onSubmit={submitPrompt}
          style={{ display: "flex", gap: 10, flexWrap: "wrap", maxWidth: 760 }}
        >
          <Input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe what you're looking for…"
            aria-label="Describe what you're looking for"
            style={{ flex: 1, minWidth: 240 }}
          />
          <Button
            type="button"
            onClick={() => scan.mutate()}
            disabled={scan.isPending}
            style={scan.isPending ? { opacity: 0.85, cursor: "default" } : undefined}
          >
            {scan.isPending ? (
              <>
                <span
                  className="gr-animate-spin"
                  style={{
                    width: 15,
                    height: 15,
                    borderRadius: "50%",
                    border: "2px solid rgba(12,26,17,.35)",
                    borderTopColor: "var(--gr-on-green)",
                    display: "inline-block",
                  }}
                />
                Scanning programs…
              </>
            ) : (
              <>
                <SearchIcon />
                Find everything I qualify for
              </>
            )}
          </Button>
        </form>

        {scan.isError && (
          <p style={{ marginTop: 14, fontSize: 13.5, color: "#e89a8a" }}>
            {scan.error instanceof ApiError ? scan.error.message : "Scan failed — try again."}
          </p>
        )}
      </section>

      {/* ===== Daily brief ===== */}
      <Card
        tone="money"
        padding="20px 24px"
        style={{
          marginTop: 32,
          display: "flex",
          alignItems: "center",
          gap: 20,
          flexWrap: "wrap",
          backgroundImage:
            "repeating-linear-gradient(24deg, rgba(255,255,255,.035) 0 1px, transparent 1px 9px)",
        }}
      >
        <div style={{ flex: 1, minWidth: 240 }}>
          <div
            style={{
              fontFamily: "var(--gr-font-mono)",
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: ".14em",
              textTransform: "uppercase",
              color: "var(--gr-money-text)",
              marginBottom: 6,
            }}
          >
            Your daily brief
          </div>
          <div
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 23,
              fontWeight: 400,
              color: "#ffffff",
              lineHeight: 1.15,
            }}
          >
            {data && data.newCount > 0
              ? `${data.newCount} new ${data.newCount === 1 ? "match" : "matches"} — and ${formatMoney(
                  data.totalEstimate,
                )} in money found.`
              : "Your matches are up to date."}
          </div>
        </div>
      </Card>

      {/* ===== Statement of opportunities ===== */}
      <section style={{ marginTop: 30 }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 14,
            marginBottom: 18,
          }}
        >
          <div>
            <Eyebrow style={{ marginBottom: 5 }}>Statement of opportunities</Eyebrow>
            <div
              style={{
                fontFamily: "var(--gr-font-mono)",
                fontSize: 12.5,
                color: "var(--gr-muted)",
              }}
            >
              {data?.matchCount ?? 0} matches — {data?.qualifyCount ?? 0} confirmed,{" "}
              {data?.likelyCount ?? 0} to review
            </div>
          </div>

          <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
            {FILTERS.map((f) => (
              <FilterChip
                key={f.key}
                label={f.label}
                active={filter === f.key}
                onClick={() => setFilter(f.key)}
                icon={f.key === "all" ? <AllIcon /> : <TypeIcon category={f.key} />}
              />
            ))}
          </div>
        </div>

        {discoveryQuery.isLoading ? (
          <FeedSkeleton />
        ) : discoveryQuery.isError ? (
          <div
            style={{
              textAlign: "center",
              padding: "70px 20px",
              background: "var(--gr-surface)",
              border: "1px dashed var(--gr-border-input)",
              borderRadius: "var(--gr-radius-card)",
              color: "var(--gr-muted-3)",
              fontSize: 14,
            }}
          >
            Couldn&rsquo;t load your matches. Try refreshing.
          </div>
        ) : items.length === 0 ? (
          <EmptyState orgId={orgId} />
        ) : filtered.length === 0 ? (
          <FilterEmptyState onClear={() => setFilter("all")} />
        ) : (
          <div
            style={{
              background: "var(--gr-surface)",
              border: "1px solid var(--gr-border)",
              borderRadius: "var(--gr-radius-card)",
              overflow: "hidden",
            }}
          >
            {filtered.map((item, i) => (
              <FeedRow key={item.id} item={item} index={i} orgId={orgId} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
function FilterChip({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 13px",
    borderRadius: "var(--gr-radius-chip)",
    fontSize: 12.5,
    cursor: "pointer",
  };
  const style: CSSProperties = active
    ? { ...base, border: "1px solid #ede4d2", background: "#ede4d2", color: "var(--gr-bg)", fontWeight: 700 }
    : {
        ...base,
        border: `1px solid ${hover ? "var(--gr-border-strong)" : "var(--gr-border-input)"}`,
        background: "var(--gr-input)",
        color: "var(--gr-muted)",
        fontWeight: 600,
      };
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={style}
    >
      <span style={{ display: "flex" }}>{icon}</span>
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
function FeedRow({ item, index, orgId }: { item: DiscoveryItem; index: number; orgId: string }) {
  const router = useRouter();
  const [hover, setHover] = useState(false);
  const category = categoryOf(item);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        gap: 18,
        alignItems: "flex-start",
        padding: "22px 24px",
        borderTop: index === 0 ? "none" : "1px solid var(--gr-border-soft)",
        background: hover ? "var(--gr-hover)" : "transparent",
        transition: "background .12s ease",
      }}
    >
      <div
        style={{
          fontFamily: "var(--gr-font-mono)",
          fontSize: 12,
          color: "#6a6150",
          fontWeight: 500,
          paddingTop: 3,
          minWidth: 22,
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            marginBottom: 7,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontFamily: "var(--gr-font-mono)",
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: "#9c907a",
            }}
          >
            <TypeIcon category={category} />
            {item.typeLabel}
          </span>

          <EligibilityBadge status={item.eligibility} label={item.eligibilityLabel} />

          {item.isNew && (
            <span
              style={{
                fontFamily: "var(--gr-font-mono)",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: ".06em",
                background: "rgba(242,182,92,.16)",
                color: "var(--gr-amber)",
                borderRadius: 5,
                padding: "2px 7px",
              }}
            >
              NEW
            </span>
          )}
        </div>

        <h3
          style={{
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: "-.01em",
            margin: "0 0 2px",
            color: "var(--gr-text-strong)",
          }}
        >
          {item.name}
        </h3>
        <div style={{ fontSize: 13, color: "var(--gr-muted-3)", marginBottom: item.benefit ? 8 : item.why ? 12 : 11 }}>
          {item.funder ?? "Funder unknown"}
        </div>

        {item.benefit && (
          <p style={{ margin: "0 0 12px", fontSize: 13.5, color: "var(--gr-muted)", lineHeight: 1.5 }}>
            {item.benefit}
          </p>
        )}

        {item.why && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: "rgba(46,158,102,.1)",
              border: "1px solid rgba(116,216,155,.22)",
              borderRadius: "var(--gr-radius-chip)",
              padding: "5px 11px",
              fontSize: 12.5,
              color: "#86d9a8",
              fontWeight: 500,
              marginBottom: 12,
            }}
          >
            <span style={{ fontFamily: "var(--gr-font-serif)", fontSize: 15 }}>✦</span> Matched because
            you said <span style={{ fontWeight: 700, color: "#a6e5c0" }}>{item.why}</span>
          </div>
        )}

        {item.citation && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontFamily: "var(--gr-font-mono)",
              fontSize: 11.5,
              color: "var(--gr-muted-4)",
            }}
          >
            <LinkIcon />
            {item.citation}
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 14,
          minWidth: 160,
          textAlign: "right",
        }}
      >
        <div
          style={{
            fontFamily: "var(--gr-font-serif)",
            fontSize: 30,
            fontWeight: 400,
            color: "var(--gr-green-bright)",
            lineHeight: 1,
            letterSpacing: "-.01em",
          }}
        >
          {formatMoney(item.estValue)}
        </div>
        <CtaButton
          label={item.cta}
          eligibility={item.eligibility}
          onClick={() => router.push(`/orgs/${orgId}/workspace/pursue`)}
        />
      </div>
    </div>
  );
}

function CtaButton({
  label,
  eligibility,
  onClick,
}: {
  label: string;
  eligibility: "qualify" | "likely";
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const qualify = eligibility === "qualify";
  const style: CSSProperties = {
    padding: "9px 17px",
    borderRadius: 8,
    fontSize: 13.5,
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
    ...(qualify
      ? {
          background: hover ? "var(--gr-green-hover)" : "var(--gr-green)",
          color: "var(--gr-on-green)",
          border: "1px solid var(--gr-green)",
        }
      : {
          background: "var(--gr-surface)",
          color: "#74d89b",
          border: `1px solid ${hover ? "#4f6256" : "#3f5246"}`,
        }),
  };
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={style}
    >
      {label} →
    </button>
  );
}

// ---------------------------------------------------------------------------
function EmptyState({ orgId }: { orgId: string }) {
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
        Nothing here yet
      </div>
      <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: "0 0 18px" }}>
        Complete your profile to surface more.
      </p>
      <Link href={`/orgs/${orgId}/onboarding`} style={{ textDecoration: "none" }}>
        <span
          style={{
            display: "inline-block",
            padding: "11px 18px",
            borderRadius: 9,
            background: "var(--gr-green)",
            color: "var(--gr-on-green)",
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          Complete your profile →
        </span>
      </Link>
    </div>
  );
}

function FilterEmptyState({ onClear }: { onClear: () => void }) {
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
        Nothing in this category
      </div>
      <button
        type="button"
        onClick={onClear}
        style={{
          marginTop: 12,
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
        Show all
      </button>
    </div>
  );
}

function FeedSkeleton() {
  return (
    <div
      style={{
        background: "var(--gr-surface)",
        border: "1px solid var(--gr-border)",
        borderRadius: "var(--gr-radius-card)",
        overflow: "hidden",
      }}
    >
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          style={{
            display: "flex",
            gap: 18,
            alignItems: "flex-start",
            padding: "22px 24px",
            borderTop: i === 0 ? "none" : "1px solid var(--gr-border-soft)",
          }}
        >
          <div style={{ minWidth: 22, paddingTop: 3 }}>
            <SkeletonBar width={18} height={12} />
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 9 }}>
            <SkeletonBar width={150} height={12} />
            <SkeletonBar width={260} height={18} />
            <SkeletonBar width={180} height={12} />
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: 14,
              minWidth: 160,
            }}
          >
            <SkeletonBar width={110} height={28} />
            <SkeletonBar width={120} height={32} />
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
        background: "linear-gradient(90deg, var(--gr-hover) 25%, var(--gr-surface-raised) 50%, var(--gr-hover) 75%)",
        backgroundSize: "200% 100%",
        animation: "gr-shimmer 1.4s ease-in-out infinite",
      }}
    />
  );
}

"use client";

import { Suspense, useMemo, useState, type CSSProperties } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Eyebrow } from "@/components/granted";
import { ApiError, apiDownload, apiFetch, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ComplianceRow,
  FilingAggregate,
  FilingResponse,
  FilledForm,
  OpportunitySummary,
  RecommendationDetail,
} from "@/lib/types";

// Pursue — the pipeline of filings being worked, restyled into the Granted theme.
// LIST: GET /orgs/{orgId}/filings joined with GET /orgs/{orgId}/opportunities for
//   each card's name + funder. Status drives a 6-step progress bar and a stage
//   badge (draft → requirements → evidence → recommend → package → ready).
// DETAIL (?filing={id}): the filing aggregate (GET /filings/{id}) powers the
//   recommendation money-panel + compliance matrix; GET /orgs/{orgId}/forms powers
//   the auto-filled forms list. The Approve checkbox posts an approval; Export
//   package downloads the approved package (nothing is auto-submitted — CON-1).

// ---------------------------------------------------------------------------
// Stage model. The backend FilingStatus enum collapses onto the design's
// 6-step pipeline (0 Draft → 5 Ready). The badge color tiers mirror the design:
// neutral (<recommend), gold (recommend / package), green (ready).
const STAGES = ["Draft", "Requirements", "Evidence", "Recommend", "Package", "Ready"] as const;

function stageOf(status: string): number {
  switch (status) {
    case "draft":
      return 0;
    case "researching":
      return 1;
    case "evidence_review":
      return 2;
    case "recommended":
      return 3;
    case "approved":
    case "packaging":
    case "package_review":
      return 4;
    case "ready":
      return 5;
    default:
      return 0; // archived / rejected / unknown → render at the start of the pipeline
  }
}

type Tier = { bg: string; color: string; border: string };

function stageTier(stage: number): Tier {
  if (stage >= 5) {
    return { bg: "rgba(46,158,102,.16)", color: "#74d89b", border: "rgba(116,216,155,.3)" };
  }
  if (stage >= 3) {
    return { bg: "rgba(242,182,92,.15)", color: "var(--gr-amber)", border: "rgba(242,182,92,.3)" };
  }
  return { bg: "var(--gr-hover)", color: "var(--gr-muted)", border: "var(--gr-border-input)" };
}

// ---------------------------------------------------------------------------
// Compliance status → the design's three matrix buckets. The backend emits
// matched / user_provided / partial / missing; we fold those into met / partial /
// todo, each with its own glyph + color treatment.
type MatrixKind = "met" | "partial" | "todo";

function matrixKind(status: string): MatrixKind {
  if (status === "matched" || status === "user_provided") return "met";
  if (status === "partial") return "partial";
  return "todo"; // missing / unknown
}

const MATRIX_META: Record<MatrixKind, { glyph: string; label: string; color: string; iconBg: string; iconBorder?: string }> = {
  met: { glyph: "✓", label: "Met", color: "#74d89b", iconBg: "rgba(46,158,102,.16)" },
  partial: { glyph: "!", label: "In progress", color: "var(--gr-amber)", iconBg: "rgba(242,182,92,.15)" },
  todo: {
    glyph: "–",
    label: "To do",
    color: "var(--gr-muted-3)",
    iconBg: "var(--gr-hover)",
    iconBorder: "var(--gr-border-input)",
  },
};

// ---------------------------------------------------------------------------
function FundIcon() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h4" />
    </svg>
  );
}

function RecommendIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-money-text)"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l2.5 2.5M16.5 16.5 19 19M19 5l-2.5 2.5M7.5 16.5 5 19" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}

function FormFileIcon() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-muted-4)"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-on-green)"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}

// ===========================================================================
// LIST
// ===========================================================================
function PursueList({ orgId, onOpen }: { orgId: string; onOpen: (filingId: string) => void }) {
  const { isAuthenticated } = useAuth();

  const filingsQuery = useQuery({
    queryKey: ["filings", orgId],
    queryFn: () => apiFetch<FilingResponse[]>(`/orgs/${orgId}/filings`),
    enabled: isAuthenticated,
  });

  // The filings list carries only opportunity IDs; the opportunity list gives us
  // each filing's display name + funder. We join the two by opportunityId.
  const opportunitiesQuery = useQuery({
    queryKey: ["opportunities", orgId],
    queryFn: () => apiFetch<OpportunitySummary[]>(`/orgs/${orgId}/opportunities`),
    enabled: isAuthenticated,
  });

  const oppById = useMemo(() => {
    const map = new Map<string, OpportunitySummary>();
    for (const o of opportunitiesQuery.data ?? []) map.set(o.id, o);
    return map;
  }, [opportunitiesQuery.data]);

  const filings = filingsQuery.data ?? [];

  return (
    <div style={{ paddingTop: 44 }}>
      <Eyebrow style={{ marginBottom: 8 }}>Your pipeline</Eyebrow>
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
        What you&rsquo;re pursuing
      </h1>
      <p style={{ margin: "0 0 30px", color: "var(--gr-muted)", fontSize: 16, maxWidth: 640 }}>
        Every filing you&rsquo;ve started. Forms, evidence and the package live inside each one — and
        nothing is submitted without your sign-off.
      </p>

      {filingsQuery.isLoading ? (
        <ListSkeleton />
      ) : filingsQuery.isError ? (
        <ErrorPanel message="Couldn't load your pipeline. Try refreshing." />
      ) : filings.length === 0 ? (
        <EmptyPipeline orgId={orgId} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {filings.map((f) => (
            <PipelineCard
              key={f.id}
              filing={f}
              opportunity={oppById.get(f.opportunityId)}
              onOpen={() => onOpen(f.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineCard({
  filing,
  opportunity,
  onOpen,
}: {
  filing: FilingResponse;
  opportunity: OpportunitySummary | undefined;
  onOpen: () => void;
}) {
  const [hover, setHover] = useState(false);
  const stage = stageOf(filing.status);
  const tier = stageTier(stage);

  const name = opportunity?.title ?? (filing.kind === "grant" ? "Grant filing" : "Contract filing");
  // GAP: no dollar value exists on the filing or opportunity payloads, so the
  // design's "funder · value" reduces to the funder + the kind (grant/contract).
  const funder = opportunity?.sponsor ?? "Funder unknown";
  const kindLabel = filing.kind === "grant" ? "Grant" : "Contract";
  const note =
    stage >= 5
      ? "Ready to export"
      : stage === 4
        ? "Building the package"
        : stage === 3
          ? "Recommendation ready"
          : stage === 2
            ? "Matching evidence"
            : stage === 1
              ? "Gathering requirements"
              : "Just started";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? "var(--gr-surface-raised)" : "var(--gr-surface)",
        border: `1px solid ${hover ? "var(--gr-green)" : "var(--gr-border)"}`,
        borderRadius: "var(--gr-radius-card)",
        padding: "22px 24px",
        cursor: "pointer",
        transition: "background .12s ease, border-color .12s ease",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          alignItems: "flex-start",
        }}
      >
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 5 }}>
            <span style={{ display: "flex", color: "#9c907a" }}>
              <FundIcon />
            </span>
            <h3
              style={{
                fontSize: 18,
                fontWeight: 700,
                margin: 0,
                letterSpacing: "-.01em",
                color: "var(--gr-text-strong)",
              }}
            >
              {name}
            </h3>
          </div>
          <div style={{ fontFamily: "var(--gr-font-mono)", fontSize: 12, color: "var(--gr-muted-3)" }}>
            {funder} · {kindLabel}
          </div>
        </div>
        <span
          style={{
            borderRadius: 6,
            padding: "4px 11px",
            fontSize: 11.5,
            fontWeight: 700,
            background: tier.bg,
            color: tier.color,
            border: `1px solid ${tier.border}`,
          }}
        >
          {STAGES[stage]}
        </span>
      </div>

      {/* 6-step progress bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 18 }}>
        {STAGES.map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background:
                i < stage ? "var(--gr-green)" : i === stage ? "#3e8c63" : "var(--gr-border)",
            }}
          />
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 9 }}>
        <span
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 11,
            color: "#9c907a",
            fontWeight: 500,
            letterSpacing: ".03em",
          }}
        >
          STAGE {stage + 1} / 6 · {STAGES[stage].toUpperCase()}
        </span>
        <span style={{ fontFamily: "var(--gr-font-mono)", fontSize: 11, color: "var(--gr-muted-4)" }}>
          {note}
        </span>
      </div>
    </div>
  );
}

// ===========================================================================
// DETAIL
// ===========================================================================
function PursueDetail({
  orgId,
  filingId,
  onClose,
}: {
  orgId: string;
  filingId: string;
  onClose: () => void;
}) {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [exportError, setExportError] = useState<string | null>(null);

  const filingQuery = useQuery({
    queryKey: ["filing", orgId, filingId],
    queryFn: () => apiFetch<FilingAggregate>(`/orgs/${orgId}/filings/${filingId}`),
    enabled: isAuthenticated,
  });

  const formsQuery = useQuery({
    queryKey: ["forms", orgId],
    queryFn: () => apiFetch<FilledForm[]>(`/orgs/${orgId}/forms`),
    enabled: isAuthenticated,
  });

  // Approve the recommendation. The backend exposes no numeric confidence, so the
  // checkbox simply records human sign-off (POST /approvals) — the gate before a
  // package can be built. Refetch the aggregate so `recommendation.approved` flips.
  const approve = useMutation({
    mutationFn: () =>
      apiFetch(`/orgs/${orgId}/filings/${filingId}/approvals`, {
        method: "POST",
        body: { target: "recommendation", decision: "approved" },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filing", orgId, filingId] }),
  });

  // Export the filing package (md). The API only ever returns a download; it is
  // gated server-side behind a ready (approved) package and never auto-submits.
  const exportPackage = useMutation({
    mutationFn: () => apiDownload(`/orgs/${orgId}/filings/${filingId}/export?format=md`),
    onMutate: () => setExportError(null),
    onError: (err) => setExportError(errorMessage(err, "Couldn't export the package.")),
  });

  return (
    <div style={{ paddingTop: 36 }}>
      <button
        type="button"
        onClick={onClose}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          background: "none",
          border: "none",
          color: "var(--gr-muted-2)",
          fontFamily: "var(--gr-font-mono)",
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: ".04em",
          textTransform: "uppercase",
          cursor: "pointer",
          padding: 0,
          marginBottom: 18,
        }}
      >
        ← All filings
      </button>

      {filingQuery.isLoading ? (
        <DetailSkeleton />
      ) : filingQuery.isError ? (
        <ErrorPanel
          message={
            filingQuery.error instanceof ApiError && filingQuery.error.status === 404
              ? "That filing no longer exists."
              : "Couldn't load this filing. Try refreshing."
          }
        />
      ) : filingQuery.data ? (
        <DetailBody
          data={filingQuery.data}
          forms={formsQuery.data ?? []}
          formsLoading={formsQuery.isLoading}
          approved={!!filingQuery.data.recommendation?.approved}
          onApprove={() => approve.mutate()}
          approvePending={approve.isPending}
          onExport={() => exportPackage.mutate()}
          exportPending={exportPackage.isPending}
          exportError={exportError}
        />
      ) : null}
    </div>
  );
}

function DetailBody({
  data,
  forms,
  formsLoading,
  approved,
  onApprove,
  approvePending,
  onExport,
  exportPending,
  exportError,
}: {
  data: FilingAggregate;
  forms: FilledForm[];
  formsLoading: boolean;
  approved: boolean;
  onApprove: () => void;
  approvePending: boolean;
  onExport: () => void;
  exportPending: boolean;
  exportError: string | null;
}) {
  const stage = stageOf(data.status);
  const name =
    data.opportunity?.title ?? (data.filing.kind === "grant" ? "Grant filing" : "Contract filing");
  const funder = data.opportunity?.sponsor ?? "Funder unknown";
  const kindLabel = data.filing.kind === "grant" ? "Grant" : "Contract";

  return (
    <>
      {/* ===== Header ===== */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 18,
          flexWrap: "wrap",
          alignItems: "flex-start",
          marginBottom: 26,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ display: "flex", color: "#9c907a" }}>
              <FundIcon />
            </span>
            <h1
              style={{
                fontFamily: "var(--gr-font-serif)",
                fontSize: 36,
                fontWeight: 400,
                letterSpacing: "-.01em",
                margin: 0,
                lineHeight: 1,
                color: "var(--gr-heading)",
              }}
            >
              {name}
            </h1>
          </div>
          <div style={{ fontFamily: "var(--gr-font-mono)", fontSize: 13, color: "var(--gr-muted-3)" }}>
            {funder} · {kindLabel}
          </div>
        </div>
        <span
          style={{
            borderRadius: 6,
            padding: "7px 14px",
            fontSize: 12.5,
            fontWeight: 700,
            background: "rgba(46,158,102,.16)",
            color: "#74d89b",
            border: "1px solid rgba(116,216,155,.3)",
          }}
        >
          {STAGES[stage]}
        </span>
      </div>

      {/* ===== Recommendation money-panel ===== */}
      <RecommendationPanel
        recommendation={data.recommendation}
        matchSummary={data.matchSummary}
        requirementCount={data.complianceMatrix.length}
        approved={approved}
        onApprove={onApprove}
        approvePending={approvePending}
      />

      {/* ===== Compliance matrix ===== */}
      <div
        style={{
          background: "var(--gr-surface)",
          border: "1px solid var(--gr-border)",
          borderRadius: "var(--gr-radius-card)",
          padding: 24,
          marginBottom: 18,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 10,
            marginBottom: 14,
          }}
        >
          <h2
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 24,
              fontWeight: 400,
              margin: 0,
              color: "var(--gr-heading)",
            }}
          >
            Compliance matrix
          </h2>
          <span style={{ fontFamily: "var(--gr-font-mono)", fontSize: 11.5, color: "var(--gr-muted-3)" }}>
            Every requirement, mapped to its source
          </span>
        </div>

        {data.complianceMatrix.length === 0 ? (
          <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: "8px 0 0" }}>
            No requirements yet — they appear once requirements are extracted and matched.
          </p>
        ) : (
          data.complianceMatrix.map((row, i) => <MatrixRow key={row.requirementId} row={row} first={i === 0} />)
        )}
      </div>

      {/* ===== Auto-filled forms ===== */}
      <div
        style={{
          background: "var(--gr-surface)",
          border: "1px solid var(--gr-border)",
          borderRadius: "var(--gr-radius-card)",
          padding: 24,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 10,
            marginBottom: 15,
          }}
        >
          <h2
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 24,
              fontWeight: 400,
              margin: 0,
              color: "var(--gr-heading)",
            }}
          >
            Auto-filled forms
          </h2>
          <button
            type="button"
            onClick={onExport}
            disabled={exportPending || !data.packageReady}
            title={
              data.packageReady
                ? "Download the approved package"
                : "Approve the package before exporting"
            }
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "9px 16px",
              borderRadius: 8,
              background: "var(--gr-green)",
              color: "var(--gr-on-green)",
              border: "none",
              fontSize: 13.5,
              fontWeight: 700,
              cursor: exportPending || !data.packageReady ? "not-allowed" : "pointer",
              opacity: exportPending || !data.packageReady ? 0.5 : 1,
            }}
          >
            <DownloadIcon />
            {exportPending ? "Exporting…" : "Export package"}
          </button>
        </div>

        {exportError && (
          <p style={{ margin: "0 0 12px", fontSize: 13, color: "#e89a8a" }}>{exportError}</p>
        )}

        {formsLoading ? (
          <FormsSkeleton />
        ) : forms.length === 0 ? (
          <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: "4px 0 0" }}>
            No forms to fill yet — build your Company Brain so we can auto-fill these.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {forms.map((form) => (
              <FormRow key={form.formId} form={form} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function RecommendationPanel({
  recommendation,
  matchSummary,
  requirementCount,
  approved,
  onApprove,
  approvePending,
}: {
  recommendation: RecommendationDetail | null;
  matchSummary: Record<string, number>;
  requirementCount: number;
  approved: boolean;
  onApprove: () => void;
  approvePending: boolean;
}) {
  // Verdict + the "N / M requirements met" line. The backend reports a 0–100
  // `score` (not a labelled confidence), so we render the verdict from `decision`
  // and a coarse confidence band derived from the score. GAP: no first-class
  // numeric confidence exists; the band is derived from score.
  const decision = recommendation?.decision ?? null;
  const verdict =
    decision === "pursue"
      ? "Pursue — strong fit"
      : decision === "no_pursue" || decision === "do_not_pursue"
        ? "Hold — gaps remain"
        : "Recommendation pending";
  const score = recommendation?.score ?? null;
  const confidence =
    score === null ? null : score >= 75 ? "High confidence" : score >= 45 ? "Moderate confidence" : "Low confidence";

  const met = (matchSummary.matched ?? 0) + (matchSummary.user_provided ?? 0);
  const rationale = recommendation?.rationale ?? null;
  const forItems = rationale?.for ?? [];
  const gaps = rationale?.key_gaps ?? [];

  return (
    <div
      className="gr-weave"
      style={{
        background: "var(--gr-money-bg)",
        color: "#eaf7ee",
        borderRadius: "var(--gr-radius-card)",
        padding: 26,
        marginBottom: 18,
        position: "relative",
        overflow: "hidden",
        border: "1px solid var(--gr-money-border)",
        backgroundImage: "repeating-linear-gradient(24deg, rgba(255,255,255,.04) 0 1px, transparent 1px 9px)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
          fontFamily: "var(--gr-font-mono)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: ".12em",
          textTransform: "uppercase",
          color: "var(--gr-money-text)",
        }}
      >
        <RecommendIcon />
        Handled&rsquo;s recommendation
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 14,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <span style={{ fontFamily: "var(--gr-font-serif)", fontSize: 32, fontWeight: 400, color: "#fff", lineHeight: 1 }}>
          {verdict}
        </span>
        <span style={{ fontFamily: "var(--gr-font-mono)", fontSize: 12, color: "var(--gr-money-text)" }}>
          {confidence ? `${confidence} · ` : ""}
          {met} / {requirementCount} requirements met
        </span>
      </div>

      {/* Cited rationale */}
      {forItems.length > 0 ? (
        <p style={{ margin: "0 0 18px", color: "#c8e3cf", fontSize: 15, lineHeight: 1.6, maxWidth: 780 }}>
          {forItems.join(" ")}
          {gaps.length > 0 && (
            <>
              {" "}
              <span style={{ color: "#fff", fontWeight: 600 }}>Still to resolve:</span> {gaps.join("; ")}.
            </>
          )}
        </p>
      ) : (
        <p style={{ margin: "0 0 18px", color: "#c8e3cf", fontSize: 15, lineHeight: 1.6, maxWidth: 780 }}>
          Run the recommendation step to see Handled&rsquo;s cited verdict on whether this filing is worth
          pursuing.
        </p>
      )}

      {/* Approve checkbox */}
      <div
        role="checkbox"
        aria-checked={approved}
        aria-label="Approve this recommendation"
        tabIndex={approved || approvePending ? -1 : 0}
        onClick={() => !approved && !approvePending && onApprove()}
        onKeyDown={(e) => {
          if (!approved && !approvePending && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            onApprove();
          }
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 13,
          flexWrap: "wrap",
          background: "rgba(255,255,255,.07)",
          border: "1px solid rgba(255,255,255,.16)",
          borderRadius: 10,
          padding: "14px 16px",
          cursor: approved || approvePending ? "default" : "pointer",
        }}
      >
        <span
          style={{
            flexShrink: 0,
            width: 22,
            height: 22,
            borderRadius: 6,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: approved ? "var(--gr-money-text)" : "transparent",
            border: `1.5px solid ${approved ? "var(--gr-money-text)" : "rgba(255,255,255,.4)"}`,
          }}
        >
          {approved && (
            <svg
              width={13}
              height={13}
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--gr-money-bg)"
              strokeWidth={3.4}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20 6 L9 17 L4 12" />
            </svg>
          )}
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#fff" }}>
            {approved
              ? "Approved — you've signed off on this recommendation"
              : approvePending
                ? "Recording your approval…"
                : "Approve this recommendation"}
          </div>
          <div style={{ fontSize: 12.5, color: "var(--gr-money-text)", marginTop: 1 }}>
            Handled never submits anything to the government without your approval.
          </div>
        </div>
      </div>
    </div>
  );
}

function MatrixRow({ row, first }: { row: ComplianceRow; first: boolean }) {
  const kind = matrixKind(row.status);
  const meta = MATRIX_META[kind];
  // Source line: the requirement's locator (e.g. "13 CFR §121.201"); evidence, if
  // matched, is shown as the right-hand note.
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 13,
        padding: "13px 2px",
        borderTop: first ? "none" : "1px solid var(--gr-border-soft)",
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: 22,
          height: 22,
          borderRadius: "50%",
          background: meta.iconBg,
          color: meta.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          fontWeight: 800,
          border: meta.iconBorder ? `1px solid ${meta.iconBorder}` : undefined,
        }}
      >
        {meta.glyph}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#e6dcc8" }}>
          {row.mandatory && (
            <span style={{ marginRight: 6, fontSize: 10, fontWeight: 700, color: "#74d89b" }}>MUST</span>
          )}
          {row.requirement}
        </div>
        {row.locator && (
          <div
            style={{
              fontFamily: "var(--gr-font-mono)",
              fontSize: 11,
              color: "var(--gr-muted-4)",
              marginTop: 2,
            }}
          >
            {row.locator}
          </div>
        )}
      </div>
      <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
        <div
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: ".04em",
            textTransform: "uppercase",
            color: meta.color,
          }}
        >
          {meta.label}
        </div>
        {row.evidence && (
          <div style={{ fontSize: 12, color: "var(--gr-muted-3)", marginTop: 2, maxWidth: 200, whiteSpace: "normal" }}>
            {row.evidence}
          </div>
        )}
      </div>
    </div>
  );
}

function FormRow({ form }: { form: FilledForm }) {
  const total = form.fields.length;
  // The design's state badge: green "Auto-filled" when nothing is outstanding,
  // gold "In progress" when the human still owes fields.
  const complete = form.missingRequired === 0;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 13,
        padding: "13px 15px",
        border: "1px solid var(--gr-border-soft)",
        borderRadius: 10,
        background: "var(--gr-input)",
      }}
    >
      <FormFileIcon />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#e6dcc8" }}>{form.name}</div>
        <div
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 11.5,
            color: "var(--gr-muted-3)",
            marginTop: 1,
          }}
        >
          {form.filledCount} of {total} fields filled
        </div>
      </div>
      <span
        style={{
          borderRadius: 6,
          padding: "3px 10px",
          fontFamily: "var(--gr-font-mono)",
          fontSize: 10.5,
          fontWeight: 600,
          letterSpacing: ".04em",
          textTransform: "uppercase",
          background: complete ? "rgba(46,158,102,.16)" : "rgba(242,182,92,.15)",
          color: complete ? "#74d89b" : "var(--gr-amber)",
        }}
      >
        {complete ? "Auto-filled" : "In progress"}
      </span>
      <span
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "var(--gr-green-bright)",
          whiteSpace: "nowrap",
        }}
        title="Field-level review of this form (coming soon)"
      >
        Review →
      </span>
    </div>
  );
}

// ===========================================================================
// Shared states
// ===========================================================================
function EmptyPipeline({ orgId }: { orgId: string }) {
  const router = useRouter();
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
      <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 24, marginBottom: 6, color: "var(--gr-heading)" }}>
        Nothing in your pipeline yet
      </div>
      <p style={{ color: "var(--gr-muted-3)", fontSize: 14, margin: "0 0 18px" }}>
        Start one from Find — pick an opportunity you qualify for and Handled opens a filing here.
      </p>
      <button
        type="button"
        onClick={() => router.push(`/orgs/${orgId}/workspace/find`)}
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
        Go to Find →
      </button>
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
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
      {message}
    </div>
  );
}

function SkeletonBar({ width, height, style }: { width: number | string; height: number; style?: CSSProperties }) {
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
        ...style,
      }}
    />
  );
}

function ListSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            background: "var(--gr-surface)",
            border: "1px solid var(--gr-border)",
            borderRadius: "var(--gr-radius-card)",
            padding: "22px 24px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
              <SkeletonBar width={240} height={18} />
              <SkeletonBar width={160} height={12} />
            </div>
            <SkeletonBar width={84} height={24} />
          </div>
          <SkeletonBar width="100%" height={4} style={{ marginTop: 18 }} />
        </div>
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <SkeletonBar width={320} height={36} />
      <SkeletonBar width="100%" height={180} style={{ borderRadius: 14 }} />
      <SkeletonBar width="100%" height={220} style={{ borderRadius: 14 }} />
    </div>
  );
}

function FormsSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {[0, 1, 2].map((i) => (
        <SkeletonBar key={i} width="100%" height={48} style={{ borderRadius: 10 }} />
      ))}
    </div>
  );
}

// ===========================================================================
// Page — list vs. detail is driven by a ?filing={id} search param so the back
// link is a real navigation (shareable + browser-back friendly), mirroring the
// Copilot surface's use of useSearchParams under a Suspense boundary.
// ===========================================================================
function PursueInner() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const selected = searchParams.get("filing");
  const base = `/orgs/${orgId}/workspace/pursue`;

  if (selected) {
    return (
      <PursueDetail
        orgId={orgId}
        filingId={selected}
        onClose={() => router.push(base)}
      />
    );
  }
  return (
    <PursueList
      orgId={orgId}
      onOpen={(filingId) => router.push(`${base}?filing=${encodeURIComponent(filingId)}`)}
    />
  );
}

export default function PursuePage() {
  return (
    <Suspense fallback={null}>
      <PursueInner />
    </Suspense>
  );
}

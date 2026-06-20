"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch, pollWorkflowRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ComplianceRow, FilingAggregate, WorkflowRunCreated } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  matched: "bg-emerald-100 text-emerald-800",
  user_provided: "bg-blue-100 text-blue-800",
  partial: "bg-amber-100 text-amber-800",
  missing: "bg-red-100 text-red-700",
};

// POST an async action sub-path and poll its workflow run to completion.
async function runAction(orgId: string, filingId: string, path: string) {
  const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
    `/orgs/${orgId}/filings/${filingId}/${path}`,
    { method: "POST" },
  );
  const run = await pollWorkflowRun(orgId, workflowRunId, { maxAttempts: 60 });
  if (run.status === "failed") throw new ApiError(500, "action_failed", run.error ?? "Failed");
  return run;
}

export default function FilingPage() {
  const { orgId, filingId } = useParams<{ orgId: string; filingId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const query = useQuery({
    queryKey: ["filing", orgId, filingId],
    queryFn: () => apiFetch<FilingAggregate>(`/orgs/${orgId}/filings/${filingId}`),
    enabled: isAuthenticated,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["filing", orgId, filingId] });

  const extract = useMutation({
    mutationFn: () => runAction(orgId, filingId, "extract-requirements"),
    onSuccess: refresh,
  });
  const match = useMutation({
    mutationFn: () => runAction(orgId, filingId, "match-evidence"),
    onSuccess: refresh,
  });
  const recommend = useMutation({
    mutationFn: () => runAction(orgId, filingId, "recommend"),
    onSuccess: refresh,
  });

  const approve = useMutation({
    mutationFn: (decision: "approved" | "rejected") =>
      apiFetch(`/orgs/${orgId}/filings/${filingId}/approvals`, {
        method: "POST",
        body: { target: "recommendation", decision },
      }),
    onSuccess: refresh,
  });

  if (loading || !isAuthenticated || query.isLoading) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }
  const d = query.data;
  if (!d) return <main className="grid min-h-screen place-items-center">Filing not found.</main>;

  const rec = d.recommendation;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-6">
        <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Workspace
        </Link>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {d.opportunity?.title ?? "Filing"}
            </h1>
            <p className="text-sm text-neutral-500">
              {d.opportunity?.sponsor} · {d.filing.kind === "grant" ? "Grant" : "Contract"}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700">
            {d.status.replace(/_/g, " ")}
          </span>
        </div>
      </header>

      {/* Step bar */}
      <div className="mb-6 flex flex-wrap gap-2">
        <ActionButton label="1. Extract requirements" mut={extract} done={d.requirementCount > 0} />
        <ActionButton
          label="2. Match evidence"
          mut={match}
          disabled={d.requirementCount === 0}
          done={d.complianceMatrix.length > 0 && (d.matchSummary.matched ?? 0) >= 0 && d.complianceMatrix.some((r) => r.status !== "missing")}
        />
        <ActionButton
          label="3. Recommend"
          mut={recommend}
          disabled={d.complianceMatrix.length === 0}
          done={!!rec}
        />
      </div>

      {/* Recommendation */}
      {rec && rec.decision && (
        <section className="mb-6 rounded-2xl border border-neutral-200 bg-white p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
              Recommendation
            </h2>
            <span
              className={`rounded-full px-3 py-1 text-sm font-semibold ${
                rec.decision === "pursue" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-700"
              }`}
            >
              {rec.decision === "pursue" ? "Pursue" : "Do not pursue"} · {Math.round(rec.score ?? 0)}
            </span>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <RationaleList title="For" items={rec.rationale?.for} color="text-emerald-700" />
            <RationaleList title="Against" items={rec.rationale?.against} color="text-red-700" />
          </div>
          {(rec.rationale?.key_gaps ?? []).length > 0 && (
            <p className="mt-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-800">
              <span className="font-medium">Key gaps: </span>
              {(rec.rationale?.key_gaps ?? []).join("; ")}
            </p>
          )}
          <div className="mt-4 flex items-center gap-2">
            {rec.approved ? (
              <span className="text-sm font-medium text-emerald-700">✓ Approved</span>
            ) : (
              <>
                <button
                  onClick={() => approve.mutate("approved")}
                  disabled={approve.isPending}
                  className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
                >
                  Approve recommendation
                </button>
                <button
                  onClick={() => approve.mutate("rejected")}
                  disabled={approve.isPending}
                  className="rounded-lg border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100 disabled:opacity-50"
                >
                  Reject
                </button>
              </>
            )}
            <span className="text-xs text-neutral-400">A human approves before pursuit (CON-1).</span>
          </div>
        </section>
      )}

      {/* Gaps */}
      {d.gapList.length > 0 && (
        <section className="mb-6 rounded-2xl border border-amber-200 bg-amber-50/40 p-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-amber-700">
            Gaps to resolve ({d.gapList.length})
          </h2>
          <ul className="mt-3 space-y-3">
            {d.gapList.map((row) => (
              <GapRow key={row.requirementId} orgId={orgId} filingId={filingId} row={row} onResolved={refresh} />
            ))}
          </ul>
        </section>
      )}

      {/* Compliance matrix */}
      <section className="rounded-2xl border border-neutral-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
            Compliance matrix ({d.complianceMatrix.length})
          </h2>
          <div className="flex gap-1 text-xs">
            {(["matched", "user_provided", "partial", "missing"] as const).map((s) =>
              d.matchSummary[s] ? (
                <span key={s} className={`rounded-full px-2 py-0.5 ${STATUS_STYLE[s]}`}>
                  {d.matchSummary[s]} {s.replace("_", " ")}
                </span>
              ) : null,
            )}
          </div>
        </div>
        {d.complianceMatrix.length === 0 ? (
          <p className="mt-4 text-sm text-neutral-500">
            Extract requirements and run evidence matching to build the matrix.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-neutral-100">
            {d.complianceMatrix.map((row) => (
              <li key={row.requirementId} className="flex items-start gap-3 py-2 text-sm">
                <StatusBadge status={row.status} />
                <div className="min-w-0">
                  <p className="text-neutral-800">
                    {row.requirement}
                    {row.locator && <span className="text-neutral-400"> — {row.locator}</span>}
                  </p>
                  {row.evidence && (
                    <p className="mt-0.5 text-xs text-neutral-500">Evidence: {row.evidence}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function ActionButton({
  label,
  mut,
  disabled,
  done,
}: {
  label: string;
  mut: { mutate: () => void; isPending: boolean; isError: boolean };
  disabled?: boolean;
  done?: boolean;
}) {
  return (
    <button
      onClick={() => mut.mutate()}
      disabled={mut.isPending || disabled}
      className={`rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50 ${
        done
          ? "border border-emerald-300 bg-emerald-50 text-emerald-800"
          : "bg-neutral-900 text-white hover:bg-neutral-700"
      }`}
    >
      {mut.isPending ? "Running…" : done ? `✓ ${label}` : label}
    </button>
  );
}

function GapRow({
  orgId,
  filingId,
  row,
  onResolved,
}: {
  orgId: string;
  filingId: string;
  row: ComplianceRow;
  onResolved: () => void;
}) {
  const [value, setValue] = useState("");
  const resolve = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/filings/${filingId}/gaps/${row.requirementId}/resolve`,
        { method: "POST", body: { value } },
      );
      await pollWorkflowRun(orgId, workflowRunId);
    },
    onSuccess: () => {
      setValue("");
      onResolved();
    },
  });
  return (
    <li className="rounded-lg bg-white p-3">
      <p className="text-sm text-neutral-800">
        {row.mandatory && <span className="mr-1 text-xs font-semibold text-red-600">MUST</span>}
        {row.requirement}
      </p>
      <div className="mt-2 flex gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Provide evidence (e.g. 'SAM.gov registered, UEI ABC123')"
          className="flex-1 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm"
        />
        <button
          onClick={() => value.trim() && resolve.mutate()}
          disabled={resolve.isPending || !value.trim()}
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {resolve.isPending ? "…" : "Resolve"}
        </button>
      </div>
    </li>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status === "user_provided" ? "provided" : status;
  return (
    <span
      className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
        STATUS_STYLE[status] ?? "bg-neutral-100 text-neutral-600"
      }`}
    >
      {label}
    </span>
  );
}

function RationaleList({
  title,
  items,
  color,
}: {
  title: string;
  items: string[] | undefined;
  color: string;
}): ReactNode {
  return (
    <div>
      <p className={`text-xs font-medium uppercase ${color}`}>{title}</p>
      <ul className="mt-1 space-y-0.5 text-sm">
        {(items ?? []).map((it, i) => (
          <li key={i}>• {it}</li>
        ))}
        {(items ?? []).length === 0 && <li className="text-neutral-400">None</li>}
      </ul>
    </div>
  );
}

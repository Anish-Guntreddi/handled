"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch, pollWorkflowRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ProgramMatch, WorkflowRunCreated } from "@/lib/types";

// "Money you can go get" — scans funding/subsidy programs the org qualifies for
// and ranks them by fit. Scan is async (202 → workflowRunId); we poll to terminal,
// then re-fetch the ranked list. Every program is cited; nothing is invented.

export default function MoneyFinderPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const programsQuery = useQuery({
    queryKey: ["programs", orgId],
    queryFn: () => apiFetch<ProgramMatch[]>(`/orgs/${orgId}/programs`),
    enabled: isAuthenticated,
  });

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["programs", orgId] }),
  });

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }

  const programs = programsQuery.data ?? [];
  const ranked = [...programs].sort((a, b) => (b.fitScore ?? 0) - (a.fitScore ?? 0));
  const applyCount = ranked.filter((p) => p.decision === "apply").length;
  const totalSoFar = ranked.length;

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
            ← Workspace
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Money you can go get</h1>
          <p className="text-sm text-neutral-500">
            Loans, grants, tax credits, and set-aside advantages your business qualifies for —
            ranked by fit, with how to apply and a source for each.
          </p>
        </div>
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          className="shrink-0 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {scan.isPending ? "Finding funding…" : ranked.length > 0 ? "Re-scan funding" : "Find funding"}
        </button>
      </header>

      {scan.isError && (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {scan.error instanceof ApiError ? scan.error.message : "Scan failed"}
        </p>
      )}

      {scan.isPending && (
        <div className="mb-4 flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-600">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
          Scanning funding programs against your Company Brain…
        </div>
      )}

      {ranked.length > 0 && (
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Metric label="Programs found" value={totalSoFar} />
          <Metric label="Go apply" value={applyCount} accent="emerald" />
          <Metric label="Top fit" value={ranked[0]?.fitScore != null ? Math.round(ranked[0].fitScore) : "—"} />
        </section>
      )}

      {programsQuery.isLoading && (
        <p className="text-sm text-neutral-500">Loading programs…</p>
      )}

      {programsQuery.isError && !programsQuery.isLoading && (
        <p className="text-sm text-red-600">Could not load funding programs.</p>
      )}

      {!programsQuery.isLoading && ranked.length === 0 && !scan.isPending && (
        <EmptyState orgId={orgId} />
      )}

      <ul className="space-y-3">
        {ranked.map((p) => (
          <ProgramCard key={p.id} program={p} />
        ))}
      </ul>
    </main>
  );
}

function EmptyState({ orgId }: { orgId: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-neutral-300 bg-white px-6 py-10 text-center">
      <p className="text-base font-medium text-neutral-800">No funding programs yet</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-neutral-500">
        Build your{" "}
        <Link href={`/orgs/${orgId}`} className="text-neutral-700 underline hover:text-neutral-900">
          Company Brain
        </Link>{" "}
        first so we can match you accurately, then click <span className="font-medium">Find funding</span> to
        discover the money you can go get.
      </p>
    </div>
  );
}

function ProgramCard({ program }: { program: ProgramMatch }) {
  return (
    <li className="rounded-2xl border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold tracking-tight">{program.name}</h3>
          <p className="mt-0.5 text-sm text-neutral-500">
            {program.funder ?? "Funder unknown"}
            {program.programType ? ` · ${program.programType}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <DecisionBadge decision={program.decision} />
          <FitScore score={program.fitScore} />
        </div>
      </div>

      {program.benefit && (
        <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-900">
          {program.benefit}
        </p>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {program.reasonsFor.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
              Why you qualify
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {program.reasonsFor.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-neutral-800">
                  <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-700">
                    ✓
                  </span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {program.keyFactors.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-amber-700">Next steps</p>
            <ul className="mt-1.5 space-y-1.5">
              {program.keyFactors.map((k, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-neutral-800">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  {k}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {program.reasonsAgainst.length > 0 && (
        <div className="mt-3 text-sm text-neutral-500">
          <span className="font-medium text-neutral-600">Watch outs: </span>
          {program.reasonsAgainst.join("; ")}
        </div>
      )}

      {program.howToApply && (
        <div className="mt-4 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">How to apply</p>
          <p className="mt-1 text-sm leading-relaxed text-neutral-800">{program.howToApply}</p>
        </div>
      )}

      {program.citation && (
        <p className="mt-3 border-t border-neutral-100 pt-3 text-xs text-neutral-400">
          Source: {program.citation}
        </p>
      )}
    </li>
  );
}

function FitScore({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-neutral-400">—</span>;
  const color =
    score >= 60
      ? "bg-emerald-100 text-emerald-800"
      : score >= 40
        ? "bg-amber-100 text-amber-800"
        : "bg-neutral-100 text-neutral-600";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${color}`}>
      {Math.round(score)}
    </span>
  );
}

function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) return null;
  const map: Record<string, { label: string; color: string }> = {
    apply: { label: "Go apply", color: "bg-emerald-100 text-emerald-800" },
    review: { label: "Review", color: "bg-amber-100 text-amber-800" },
    no_apply: { label: "Skip", color: "bg-neutral-100 text-neutral-600" },
  };
  const cfg = map[decision] ?? { label: decision, color: "bg-neutral-100 text-neutral-600" };
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${cfg.color}`}>{cfg.label}</span>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: "emerald";
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-neutral-400">{label}</p>
      <p
        className={`mt-1 text-2xl font-semibold tracking-tight ${
          accent === "emerald" ? "text-emerald-700" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

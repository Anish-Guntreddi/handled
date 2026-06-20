"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiDownload, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditEventResponse, AuditMetrics, WorkflowRunSummary } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  succeeded: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-800",
  queued: "bg-neutral-100 text-neutral-600",
  needs_input: "bg-amber-100 text-amber-800",
};

export default function AuditPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const metrics = useQuery({
    queryKey: ["audit-metrics", orgId],
    queryFn: () => apiFetch<AuditMetrics>(`/orgs/${orgId}/audit/metrics`),
    enabled: isAuthenticated,
  });
  const runs = useQuery({
    queryKey: ["audit-runs", orgId],
    queryFn: () => apiFetch<WorkflowRunSummary[]>(`/orgs/${orgId}/audit/runs?limit=50`),
    enabled: isAuthenticated,
  });
  const events = useQuery({
    queryKey: ["audit-events", orgId],
    queryFn: () => apiFetch<AuditEventResponse[]>(`/orgs/${orgId}/audit/events?limit=20`),
    enabled: isAuthenticated,
  });
  const exportAudit = useMutation({
    mutationFn: (format: "csv" | "json") =>
      apiDownload(`/orgs/${orgId}/audit/export?format=${format}`, "GET"),
  });

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }
  const m = metrics.data;

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
            ← Workspace
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Audit & activity</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportAudit.mutate("csv")}
            className="rounded-lg border border-neutral-300 px-3 py-2 text-sm font-medium hover:bg-neutral-100"
          >
            Export CSV
          </button>
          <button
            onClick={() => exportAudit.mutate("json")}
            className="rounded-lg border border-neutral-300 px-3 py-2 text-sm font-medium hover:bg-neutral-100"
          >
            Export JSON
          </button>
        </div>
      </header>

      {/* Metrics */}
      <section className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Filings" value={m?.filings ?? "—"} />
        <Metric label="Workflow runs" value={m?.runs ?? "—"} sub={`${m?.succeededRuns ?? 0} succeeded`} />
        <Metric label="Time saved" value={m ? `${m.totalTimeSavedMinutes} min` : "—"} />
        <Metric
          label="Est. cost / filing"
          value={m ? `$${m.costPerFilingUsd.toFixed(4)}` : "—"}
          sub={m ? `$${m.estimatedCostUsd.toFixed(4)} total` : undefined}
        />
      </section>

      {/* Runs */}
      <section className="mb-8 rounded-2xl border border-neutral-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Workflow runs
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-neutral-400">
              <tr>
                <th className="py-2">Type</th>
                <th>Status</th>
                <th>Steps</th>
                <th>Time saved</th>
                <th>Tokens</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {(runs.data ?? []).map((r) => (
                <tr key={r.id}>
                  <td className="py-2 font-medium">{r.type.replace(/_/g, " ")}</td>
                  <td>
                    <span className={`rounded px-1.5 py-0.5 text-xs ${STATUS_STYLE[r.status] ?? ""}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.stepCount}</td>
                  <td>{r.timeSavedMinutes ?? 0} min</td>
                  <td className="text-neutral-500">{r.inputTokens + r.outputTokens}</td>
                </tr>
              ))}
              {(runs.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-neutral-400">
                    No runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent events */}
      <section className="rounded-2xl border border-neutral-200 bg-white p-6">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Recent audit events
        </h2>
        <ul className="space-y-1 text-sm">
          {(events.data ?? []).map((e) => (
            <li key={e.id} className="flex items-center justify-between">
              <span className="font-mono text-xs text-neutral-700">{e.action}</span>
              <span className="text-xs text-neutral-400">
                {e.actor}
                {e.model ? ` · ${e.model}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function Metric({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-neutral-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {sub && <p className="text-xs text-neutral-400">{sub}</p>}
    </div>
  );
}

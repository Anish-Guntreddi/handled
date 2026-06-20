"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch, pollWorkflowRun } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FilingAggregate, RequirementResponse, WorkflowRunCreated } from "@/lib/types";

const CATEGORY_LABEL: Record<string, string> = {
  eligibility: "Eligibility",
  technical: "Technical",
  past_performance: "Past performance",
  certification: "Certifications",
  formatting: "Formatting & submission",
  attachment: "Attachments",
  other: "Other",
};

export default function FilingPage() {
  const params = useParams<{ orgId: string; filingId: string }>();
  const { orgId, filingId } = params;
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const filingQuery = useQuery({
    queryKey: ["filing", orgId, filingId],
    queryFn: () => apiFetch<FilingAggregate>(`/orgs/${orgId}/filings/${filingId}`),
    enabled: isAuthenticated,
  });

  const extract = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/filings/${filingId}/extract-requirements`,
        { method: "POST" },
      );
      const run = await pollWorkflowRun(orgId, workflowRunId);
      if (run.status === "failed") throw new ApiError(500, "x", run.error ?? "Extraction failed");
      return run;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filing", orgId, filingId] }),
  });

  if (loading || !isAuthenticated || filingQuery.isLoading) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }
  const data = filingQuery.data;
  if (!data) return <main className="grid min-h-screen place-items-center">Filing not found.</main>;

  const grouped = data.requirements.reduce<Record<string, RequirementResponse[]>>((acc, r) => {
    (acc[r.category] ??= []).push(r);
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-6">
        <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Workspace
        </Link>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {data.opportunity?.title ?? "Filing"}
            </h1>
            <p className="text-sm text-neutral-500">
              {data.opportunity?.sponsor} · {data.filing.kind === "grant" ? "Grant" : "Contract"}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700">
            {data.status.replace("_", " ")}
          </span>
        </div>
      </header>

      <section className="rounded-2xl border border-neutral-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
            Requirements ({data.requirementCount})
          </h2>
          <button
            onClick={() => extract.mutate()}
            disabled={extract.isPending}
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {extract.isPending
              ? "Extracting…"
              : data.requirementCount > 0
                ? "Re-extract"
                : "Extract requirements"}
          </button>
        </div>
        {extract.isError && (
          <p className="mt-2 text-sm text-red-600">
            {extract.error instanceof ApiError ? extract.error.message : "Extraction failed"}
          </p>
        )}

        {data.requirementCount === 0 ? (
          <p className="mt-4 text-sm text-neutral-500">
            No requirements yet. Click “Extract requirements” to parse the solicitation.
          </p>
        ) : (
          <div className="mt-4 space-y-5">
            {Object.entries(grouped).map(([category, reqs]) => (
              <div key={category}>
                <h3 className="text-xs font-semibold uppercase text-neutral-500">
                  {CATEGORY_LABEL[category] ?? category} ({reqs.length})
                </h3>
                <ul className="mt-1 space-y-1.5">
                  {reqs.map((r) => (
                    <li key={r.id} className="flex items-start gap-2 text-sm">
                      <span
                        className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                          r.mandatory ? "bg-red-50 text-red-700" : "bg-neutral-100 text-neutral-500"
                        }`}
                      >
                        {r.mandatory ? "MUST" : "should"}
                      </span>
                      <span className="text-neutral-800">
                        {r.text}
                        {r.locator && <span className="text-neutral-400"> — {r.locator}</span>}
                        {r.needsReview && (
                          <span className="ml-1 text-amber-600">⚑ review</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

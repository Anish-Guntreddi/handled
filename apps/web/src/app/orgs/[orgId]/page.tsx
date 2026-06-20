"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch, pollWorkflowRun, uploadBlob } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CompanyProfile,
  DocumentItem,
  OpportunityDetail,
  OpportunitySummary,
  WorkflowRunCreated,
} from "@/lib/types";

export default function OrgWorkspace() {
  const params = useParams<{ orgId: string }>();
  const orgId = params.orgId;
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const profileQuery = useQuery({
    queryKey: ["profile", orgId],
    queryFn: () => apiFetch<CompanyProfile>(`/orgs/${orgId}/company-profile`),
    enabled: isAuthenticated,
    retry: false,
  });

  const documentsQuery = useQuery({
    queryKey: ["documents", orgId],
    queryFn: () => apiFetch<DocumentItem[]>(`/orgs/${orgId}/documents`),
    enabled: isAuthenticated,
  });

  const profileMissing = profileQuery.error instanceof ApiError && profileQuery.error.status === 404;

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <Link href="/dashboard" className="text-sm text-neutral-500 hover:text-neutral-900">
            ← All organizations
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Company Brain</h1>
          <p className="text-sm text-neutral-500">Build a source-backed profile, then ingest documents.</p>
        </div>
        <nav className="flex shrink-0 gap-2">
          <Link
            href={`/orgs/${orgId}/audit`}
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-100"
          >
            Audit
          </Link>
          <Link
            href={`/orgs/${orgId}/billing`}
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-100"
          >
            Billing
          </Link>
        </nav>
      </header>

      <CompanyBrainSection
        orgId={orgId}
        profile={profileQuery.data}
        missing={profileMissing}
        loading={profileQuery.isLoading}
        onChanged={() => queryClient.invalidateQueries({ queryKey: ["profile", orgId] })}
      />

      <DocumentsSection
        orgId={orgId}
        documents={documentsQuery.data ?? []}
        onChanged={() => {
          queryClient.invalidateQueries({ queryKey: ["documents", orgId] });
          queryClient.invalidateQueries({ queryKey: ["profile", orgId] });
        }}
      />

      <OpportunitiesSection orgId={orgId} />
    </main>
  );
}

function OpportunitiesSection({ orgId }: { orgId: string }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);

  const opportunitiesQuery = useQuery({
    queryKey: ["opportunities", orgId],
    queryFn: () => apiFetch<OpportunitySummary[]>(`/orgs/${orgId}/opportunities`),
  });

  const scan = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/opportunity-scans`,
        { method: "POST", body: { kind: "gov_contract", limit: 12 } },
      );
      const run = await pollWorkflowRun(orgId, workflowRunId, { maxAttempts: 60 });
      if (run.status !== "succeeded") throw new ApiError(500, "scan_failed", run.error ?? "Scan failed");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["opportunities", orgId] }),
  });

  const items = opportunitiesQuery.data ?? [];

  return (
    <section className="mt-10 rounded-2xl border border-neutral-200 bg-white p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Government contract opportunities
        </h2>
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {scan.isPending ? "Scanning…" : "Run GovCon scan"}
        </button>
      </div>
      {scan.isError && (
        <p className="mt-2 text-sm text-red-600">
          {scan.error instanceof ApiError ? scan.error.message : "Scan failed"}
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {items.map((opp) => (
          <li key={opp.id} className="rounded-xl border border-neutral-200">
            <button
              onClick={() => setExpanded(expanded === opp.id ? null : opp.id)}
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{opp.title}</p>
                <p className="truncate text-xs text-neutral-500">{opp.sponsor}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <DecisionBadge hint={opp.decisionHint} />
                <FitScore score={opp.fitScore} />
              </div>
            </button>
            {expanded === opp.id && <OpportunityExpand orgId={orgId} opportunityId={opp.id} />}
          </li>
        ))}
        {items.length === 0 && !scan.isPending && (
          <li className="rounded-xl border border-dashed border-neutral-300 px-4 py-6 text-center text-sm text-neutral-500">
            Build the Company Brain above, then run a scan to discover and rank contracts.
          </li>
        )}
      </ul>
    </section>
  );
}

function OpportunityExpand({ orgId, opportunityId }: { orgId: string; opportunityId: string }) {
  const router = useRouter();
  const detail = useQuery({
    queryKey: ["opportunity", orgId, opportunityId],
    queryFn: () => apiFetch<OpportunityDetail>(`/orgs/${orgId}/opportunities/${opportunityId}`),
  });
  const startFiling = useMutation({
    mutationFn: () =>
      apiFetch<{ id: string }>(`/orgs/${orgId}/filings`, {
        method: "POST",
        body: { opportunityId },
      }),
    onSuccess: (filing) => router.push(`/orgs/${orgId}/filings/${filing.id}`),
  });
  if (detail.isLoading) return <p className="px-4 pb-3 text-sm text-neutral-500">Loading…</p>;
  const d = detail.data;
  if (!d) return null;
  return (
    <div className="space-y-3 border-t border-neutral-100 px-4 py-3 text-sm">
      {d.details.research && (
        <p className="text-neutral-700">{d.details.research.agency_summary}</p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase text-emerald-700">Reasons to bid</p>
          <ul className="mt-1 space-y-0.5">
            {(d.fitRationale?.for ?? []).map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-red-700">Reasons against</p>
          <ul className="mt-1 space-y-0.5">
            {(d.fitRationale?.against ?? []).map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
            {(d.fitRationale?.against ?? []).length === 0 && <li className="text-neutral-400">None</li>}
          </ul>
        </div>
      </div>
      {(d.fitRationale?.key_factors ?? []).length > 0 && (
        <div className="rounded-lg bg-amber-50 p-2 text-amber-800">
          <span className="font-medium">Key factors: </span>
          {(d.fitRationale?.key_factors ?? []).join("; ")}
        </div>
      )}
      <div className="flex items-center justify-between gap-3 pt-1">
        {d.sourceUrl ? (
          <a
            href={d.sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="text-neutral-500 underline"
          >
            View source ({d.externalId})
          </a>
        ) : (
          <span />
        )}
        <button
          onClick={() => startFiling.mutate()}
          disabled={startFiling.isPending}
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {startFiling.isPending ? "Starting…" : "Start filing →"}
        </button>
      </div>
    </div>
  );
}

function FitScore({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-neutral-400">—</span>;
  const color = score >= 60 ? "bg-emerald-100 text-emerald-800" : score >= 40 ? "bg-amber-100 text-amber-800" : "bg-neutral-100 text-neutral-600";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${color}`}>{Math.round(score)}</span>;
}

function DecisionBadge({ hint }: { hint: string | null }) {
  if (!hint) return null;
  const label = hint === "no_bid" ? "no-bid" : hint;
  const color = hint === "bid" ? "text-emerald-700" : hint === "review" ? "text-amber-700" : "text-neutral-500";
  return <span className={`text-xs font-medium ${color}`}>{label}</span>;
}

function CompanyBrainSection({
  orgId,
  profile,
  missing,
  loading,
  onChanged,
}: {
  orgId: string;
  profile: CompanyProfile | undefined;
  missing: boolean;
  loading: boolean;
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [description, setDescription] = useState("");

  const build = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/company-profile/build`,
        { method: "POST", body: { name, websiteUrl: websiteUrl || undefined, description: description || undefined } },
      );
      const run = await pollWorkflowRun(orgId, workflowRunId);
      if (run.status !== "succeeded") throw new ApiError(500, "build_failed", run.error ?? "Build failed");
      return run;
    },
    onSuccess: onChanged,
  });

  function onBuild(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) build.mutate();
  }

  return (
    <section className="mb-10 rounded-2xl border border-neutral-200 bg-white p-6">
      <form onSubmit={onBuild} className="grid gap-3 sm:grid-cols-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Company name *"
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm sm:col-span-1"
        />
        <input
          value={websiteUrl}
          onChange={(e) => setWebsiteUrl(e.target.value)}
          placeholder="https://website.com"
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm sm:col-span-2"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does the company do? (optional)"
          rows={2}
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm sm:col-span-3"
        />
        <button
          type="submit"
          disabled={build.isPending || !name.trim()}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 sm:col-span-1"
        >
          {build.isPending ? "Building…" : profile ? "Rebuild profile" : "Build profile"}
        </button>
      </form>
      {build.isError && (
        <p className="mt-2 text-sm text-red-600">
          {build.error instanceof ApiError ? build.error.message : "Build failed"}
        </p>
      )}

      {loading && <p className="mt-4 text-sm text-neutral-500">Loading profile…</p>}
      {missing && !build.isPending && (
        <p className="mt-4 text-sm text-neutral-500">No profile yet — fill the form above and build one.</p>
      )}

      {profile && <ProfileView orgId={orgId} profile={profile} onChanged={onChanged} />}
    </section>
  );
}

function ProfileView({
  orgId,
  profile,
  onChanged,
}: {
  orgId: string;
  profile: CompanyProfile;
  onChanged: () => void;
}) {
  const [industry, setIndustry] = useState(profile.industry ?? "");

  const patch = useMutation({
    mutationFn: () =>
      apiFetch<CompanyProfile>(`/orgs/${orgId}/company-profile`, {
        method: "PATCH",
        body: { industry },
      }),
    onSuccess: onChanged,
  });

  return (
    <div className="mt-6 space-y-5">
      {profile.capabilityStatement && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">Capability statement</h3>
          <p className="mt-1 text-sm leading-relaxed text-neutral-800">{profile.capabilityStatement}</p>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <Block title="Services">
          <ul className="space-y-1 text-sm">
            {profile.services.map((s, i) => (
              <li key={i}>• {s.name}</li>
            ))}
          </ul>
        </Block>
        <Block title="NAICS guesses">
          <ul className="space-y-1 text-sm">
            {profile.naicsGuesses.map((n, i) => (
              <li key={i}>
                <span className="font-mono">{n.code}</span> — {n.label}{" "}
                <span className="text-neutral-400">({Math.round(n.confidence * 100)}%)</span>
              </li>
            ))}
          </ul>
        </Block>
        <Block title="Certifications">
          <ul className="space-y-1 text-sm">
            {profile.certifications.map((c, i) => (
              <li key={i}>
                {c.name} <span className="text-neutral-400">[{c.status}]</span>
              </li>
            ))}
          </ul>
        </Block>
        <Block title={`Missing info (${profile.missingFields.length})`}>
          <ul className="space-y-1 text-sm text-amber-700">
            {profile.missingFields.map((m, i) => (
              <li key={i}>• {m}</li>
            ))}
          </ul>
        </Block>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-neutral-50 p-3">
        <label className="text-sm text-neutral-600">Override industry:</label>
        <input
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="flex-1 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm"
        />
        <button
          onClick={() => patch.mutate()}
          disabled={patch.isPending}
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 disabled:opacity-50"
        >
          {patch.isPending ? "Saving…" : "Save override"}
        </button>
        <span className="text-xs text-neutral-400">{profile.evidenceCount} sourced evidence items</span>
      </div>
    </div>
  );
}

function DocumentsSection({
  orgId,
  documents,
  onChanged,
}: {
  orgId: string;
  documents: DocumentItem[];
  onChanged: () => void;
}) {
  const [text, setText] = useState("");

  const ingestText = useMutation({
    mutationFn: async () => {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(`/orgs/${orgId}/documents/paste`, {
        method: "POST",
        body: { filename: "pasted.txt", rawText: text },
      });
      await pollWorkflowRun(orgId, workflowRunId);
    },
    onSuccess: () => {
      setText("");
      onChanged();
    },
  });

  const uploadFile = useMutation({
    mutationFn: async (file: File) => {
      const init = await apiFetch<{ documentId: string; uploadUrl: string }>(
        `/orgs/${orgId}/documents/initiate-upload`,
        { method: "POST", body: { filename: file.name, mimeType: file.type || "application/octet-stream" } },
      );
      await uploadBlob(init.uploadUrl, file);
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/documents/${init.documentId}/ingest`,
        { method: "POST", body: {} },
      );
      await pollWorkflowRun(orgId, workflowRunId);
    },
    onSuccess: onChanged,
  });

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6">
      <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">Documents & evidence</h2>

      <div className="mt-3 grid gap-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste solicitation or capability text to ingest…"
          rows={3}
          className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => text.trim() && ingestText.mutate()}
            disabled={ingestText.isPending || !text.trim()}
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {ingestText.isPending ? "Ingesting…" : "Ingest text"}
          </button>
          <label className="cursor-pointer rounded-lg border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100">
            {uploadFile.isPending ? "Uploading…" : "Upload file"}
            <input
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadFile.mutate(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>

      <ul className="mt-4 divide-y divide-neutral-100">
        {documents.map((doc) => (
          <li key={doc.id} className="flex items-center justify-between py-2 text-sm">
            <span>{doc.filename}</span>
            <span className="text-xs text-neutral-500">
              {doc.parseStatus} · {doc.chunkCount} chunks
            </span>
          </li>
        ))}
        {documents.length === 0 && <li className="py-2 text-sm text-neutral-400">No documents ingested yet.</li>}
      </ul>
    </section>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-500">{title}</h3>
      <div className="mt-1 text-neutral-800">{children}</div>
    </div>
  );
}

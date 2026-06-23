"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FilledField, FilledForm } from "@/lib/types";

// Filled Forms — the documents a small business submits (SF-424, SAM Reps & Certs).
// We auto-fill every field we can from the Company Brain (green, sourced) and flag the
// rest for the human to complete (amber "you provide"). We never invent answers.

export default function FormsPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const formsQuery = useQuery({
    queryKey: ["forms", orgId],
    queryFn: () => apiFetch<FilledForm[]>(`/orgs/${orgId}/forms`),
    enabled: isAuthenticated,
  });

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }

  const forms = formsQuery.data ?? [];
  const noProfile =
    !formsQuery.isLoading &&
    forms.length > 0 &&
    forms.every((f) => f.filledCount === 0);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-6">
        <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Workspace
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Filled forms</h1>
        <p className="text-sm text-neutral-500">
          We filled what we know from your Company Brain — here&apos;s what you complete. Every
          auto-filled value is sourced; we never invent answers.
        </p>
      </header>

      {noProfile && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Nothing is auto-filled yet. Build your{" "}
          <Link href={`/orgs/${orgId}`} className="font-medium underline">
            Company Brain
          </Link>{" "}
          first so we can fill these forms from your profile.
        </div>
      )}

      {formsQuery.isLoading && <p className="text-sm text-neutral-500">Loading forms…</p>}
      {formsQuery.isError && !formsQuery.isLoading && (
        <p className="text-sm text-red-600">Could not load forms.</p>
      )}

      {!formsQuery.isLoading && forms.length === 0 && (
        <div className="rounded-2xl border border-dashed border-neutral-300 bg-white px-6 py-10 text-center text-sm text-neutral-500">
          No forms available yet.
        </div>
      )}

      <div className="space-y-6">
        {forms.map((form) => (
          <FormCard key={form.formId} form={form} />
        ))}
      </div>
    </main>
  );
}

function FormCard({ form }: { form: FilledForm }) {
  const total = form.fields.length;
  const pct = total > 0 ? Math.round((form.filledCount / total) * 100) : 0;

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-tight">{form.name}</h2>
          <p className="mt-0.5 text-sm text-neutral-500">{form.description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs">
          <span className="rounded-full bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-800">
            {form.filledCount} filled
          </span>
          {form.missingRequired > 0 && (
            <span className="rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-800">
              {form.missingRequired} you provide
            </span>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-neutral-400">
          <span>{pct}% auto-filled</span>
          <span>
            {form.filledCount}/{total} fields
          </span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Fields */}
      <ul className="mt-5 divide-y divide-neutral-100">
        {form.fields.map((field) => (
          <FieldRow key={field.fieldId} field={field} />
        ))}
      </ul>

      <p className="mt-4 border-t border-neutral-100 pt-3 text-xs text-neutral-400">
        Source: {form.citation}
      </p>
    </section>
  );
}

function FieldRow({ field }: { field: FilledField }) {
  const filled = field.status === "filled";
  return (
    <li className="flex items-start justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-neutral-800">{field.label}</p>
        {filled ? (
          <p className="mt-0.5 break-words text-sm text-emerald-700">{field.value}</p>
        ) : (
          <p className="mt-0.5 text-sm text-amber-700">
            {field.note || "You provide this."}
          </p>
        )}
      </div>
      <span
        className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
          filled
            ? "bg-emerald-100 text-emerald-700"
            : "bg-amber-100 text-amber-700"
        }`}
      >
        {filled ? (field.source === "auto" ? "Auto-filled" : "Filled") : "You provide"}
      </span>
    </li>
  );
}

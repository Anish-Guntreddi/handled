"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me, Org } from "@/lib/types";

export default function DashboardPage() {
  const { isAuthenticated, loading, logout } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [orgName, setOrgName] = useState("");

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/auth/me"),
    enabled: isAuthenticated,
  });

  const createOrg = useMutation({
    mutationFn: (name: string) => apiFetch<Org>("/orgs", { method: "POST", body: { name } }),
    onSuccess: () => {
      setOrgName("");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  function onCreateOrg(e: FormEvent) {
    e.preventDefault();
    if (orgName.trim()) createOrg.mutate(orgName.trim());
  }

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }

  const me = meQuery.data;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">CaptureOS</h1>
          <p className="text-sm text-neutral-500">
            {me ? `Signed in as ${me.user.email}` : "Loading your account…"}
          </p>
        </div>
        <button
          onClick={() => {
            logout();
            router.replace("/login");
          }}
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100"
        >
          Sign out
        </button>
      </header>

      <section className="mt-8">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Your organizations
        </h2>

        {meQuery.isLoading && <p className="mt-3 text-sm text-neutral-500">Loading…</p>}
        {meQuery.isError && (
          <p className="mt-3 text-sm text-red-600">Could not load organizations.</p>
        )}

        <ul className="mt-3 space-y-2">
          {me?.orgs.map((org) => (
            <li key={org.orgId}>
              <Link
                href={`/orgs/${org.orgId}`}
                className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-4 py-3 transition hover:border-neutral-400 hover:bg-neutral-50"
              >
                <div>
                  <p className="font-medium">{org.name}</p>
                  <p className="text-xs text-neutral-500">
                    Role: {org.role} · Plan: {org.plan}
                  </p>
                </div>
                <span className="text-sm text-neutral-400">Open →</span>
              </Link>
            </li>
          ))}
          {me && me.orgs.length === 0 && (
            <li className="rounded-xl border border-dashed border-neutral-300 px-4 py-6 text-center text-sm text-neutral-500">
              No organizations yet. Create one below to get started.
            </li>
          )}
        </ul>

        <form onSubmit={onCreateOrg} className="mt-4 flex gap-2">
          <input
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="New organization name"
            className="flex-1 rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900"
          />
          <button
            type="submit"
            disabled={createOrg.isPending || !orgName.trim()}
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {createOrg.isPending ? "Creating…" : "Create"}
          </button>
        </form>
        {createOrg.isError && (
          <p className="mt-2 text-sm text-red-600">Could not create organization.</p>
        )}
      </section>

      <footer className="mt-12 rounded-xl border border-neutral-200 bg-white p-4 text-sm text-neutral-500">
        Open an organization to access the Company Brain, opportunity scanning, filings, audit,
        and billing.{" "}
        <Link href="/how-it-works" className="text-neutral-600 underline hover:text-neutral-900">
          How CaptureOS works
        </Link>
        .
      </footer>
    </main>
  );
}

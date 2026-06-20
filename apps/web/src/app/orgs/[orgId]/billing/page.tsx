"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BillingStatus, CheckoutResponse } from "@/lib/types";

const PLAN_BLURB: Record<string, string> = {
  free: "Scan, match, and get recommendations.",
  audit: "Everything in Free, plus the audit dashboard.",
  sprint: "Build and export filing packages.",
  autopilot: "Sprint plus priority processing.",
};

export default function BillingPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const billing = useQuery({
    queryKey: ["billing", orgId],
    queryFn: () => apiFetch<BillingStatus>(`/orgs/${orgId}/billing`),
    enabled: isAuthenticated,
  });

  const upgrade = useMutation({
    mutationFn: async (product: string) => {
      // Checkout is authenticated + org-scoped. In mock mode it fulfills the upgrade inline
      // (completed=true); with Stripe it returns a URL and the signed webhook fulfills it.
      const cs = await apiFetch<CheckoutResponse>(`/orgs/${orgId}/billing/checkout`, {
        method: "POST",
        body: { product },
      });
      if (!cs.completed && cs.url) window.open(cs.url, "_blank");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["billing", orgId] }),
  });

  if (loading || !isAuthenticated || billing.isLoading) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }
  const b = billing.data;
  if (!b) return <main className="grid min-h-screen place-items-center">No billing data.</main>;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-6">
        <Link href={`/orgs/${orgId}`} className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Workspace
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Plan & billing</h1>
      </header>

      <section className="mb-6 rounded-2xl border border-neutral-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-400">Current plan</p>
            <p className="text-xl font-semibold capitalize">{b.plan}</p>
          </div>
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-600">
            {b.subscriptionStatus ?? "no subscription"}
          </span>
        </div>
        <p className="mt-2 text-sm text-neutral-500">
          Premium features:{" "}
          {b.premiumFeatures.map((f) => (
            <span
              key={f}
              className={`mr-1 rounded px-1.5 py-0.5 text-xs ${
                b.entitlements.includes(f)
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-neutral-100 text-neutral-500"
              }`}
            >
              {f} {b.entitlements.includes(f) ? "✓" : "🔒"}
            </span>
          ))}
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {Object.entries(b.products).map(([product, cents]) => {
          const current = b.plan === product;
          return (
            <div
              key={product}
              className={`rounded-2xl border p-5 ${current ? "border-neutral-900" : "border-neutral-200"}`}
            >
              <p className="text-lg font-semibold capitalize">{product}</p>
              <p className="mt-1 text-2xl font-bold">
                ${(cents / 100).toFixed(0)}
                <span className="text-sm font-normal text-neutral-400">/mo</span>
              </p>
              <p className="mt-1 min-h-10 text-xs text-neutral-500">{PLAN_BLURB[product]}</p>
              <button
                onClick={() => upgrade.mutate(product)}
                disabled={current || upgrade.isPending}
                className="mt-3 w-full rounded-lg bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-40"
              >
                {current ? "Current plan" : upgrade.isPending ? "Upgrading…" : "Upgrade"}
              </button>
            </div>
          );
        })}
      </section>
    </main>
  );
}

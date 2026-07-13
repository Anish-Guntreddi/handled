"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, Eyebrow } from "@/components/captureos";
import { apiFetch } from "@/lib/api";
import type { BillingStatus, CheckoutResponse } from "@/lib/types";

// Plan & billing — current plan, entitlements, and upgrade. Lives under
// workspace/ to inherit the shared shell from workspace/layout.tsx; not one
// of the four primary tabs, reachable via the header's "Billing" link.

const PLAN_BLURB: Record<string, string> = {
  free: "Scan, match, and get recommendations.",
  audit: "Everything in Free, plus the audit dashboard.",
  sprint: "Build and export filing packages.",
  autopilot: "Sprint plus priority processing.",
};

export default function BillingPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const queryClient = useQueryClient();

  const billing = useQuery({
    queryKey: ["billing", orgId],
    queryFn: () => apiFetch<BillingStatus>(`/orgs/${orgId}/billing`),
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

  if (billing.isLoading) {
    return <div style={{ paddingTop: 44, color: "var(--gr-muted)" }}>Loading…</div>;
  }
  const b = billing.data;
  if (!b) {
    return <div style={{ paddingTop: 44, color: "var(--gr-muted)" }}>No billing data.</div>;
  }

  return (
    <div style={{ paddingTop: 44, paddingBottom: 60, maxWidth: 780 }}>
      <Eyebrow style={{ marginBottom: 8 }}>Plan &amp; billing</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 40,
          fontWeight: 400,
          lineHeight: 1.02,
          letterSpacing: "-.01em",
          margin: "0 0 28px",
          color: "var(--gr-heading)",
        }}
      >
        Your plan, entitlements, and upgrades.
      </h1>

      <Card tone="money" padding={24} style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <div>
            <Eyebrow color="var(--gr-money-text)" style={{ marginBottom: 6 }}>
              Current plan
            </Eyebrow>
            <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 30, fontWeight: 400, color: "#ffffff", textTransform: "capitalize" }}>
              {b.plan}
            </div>
          </div>
          <span
            style={{
              borderRadius: 999,
              padding: "5px 13px",
              fontSize: 12,
              fontWeight: 600,
              background: "rgba(255,255,255,.1)",
              color: "#eaf7ee",
            }}
          >
            {b.subscriptionStatus ?? "no subscription"}
          </span>
        </div>
        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 7 }}>
          {b.premiumFeatures.map((f) => {
            const unlocked = b.entitlements.includes(f);
            return (
              <span
                key={f}
                style={{
                  borderRadius: 6,
                  padding: "3px 9px",
                  fontSize: 12,
                  fontWeight: 600,
                  background: unlocked ? "rgba(255,255,255,.14)" : "rgba(255,255,255,.06)",
                  color: unlocked ? "#eaf7ee" : "rgba(234,247,238,.5)",
                }}
              >
                {f} {unlocked ? "✓" : "🔒"}
              </span>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
        {Object.entries(b.products).map(([product, cents]) => {
          const current = b.plan === product;
          return (
            <Card
              key={product}
              padding={22}
              style={{ border: `1px solid ${current ? "var(--gr-green)" : "var(--gr-border)"}` }}
            >
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--gr-text-strong)", textTransform: "capitalize" }}>
                {product}
              </div>
              <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 30, fontWeight: 400, color: "var(--gr-heading)", marginTop: 6 }}>
                ${(cents / 100).toFixed(0)}
                <span style={{ fontFamily: "var(--gr-font-sans)", fontSize: 13, fontWeight: 500, color: "var(--gr-muted-3)" }}>
                  /mo
                </span>
              </div>
              <p style={{ margin: "8px 0 16px", fontSize: 12.5, color: "var(--gr-muted)", lineHeight: 1.5, minHeight: 38 }}>
                {PLAN_BLURB[product]}
              </p>
              <Button
                variant={current ? "secondary" : "primary"}
                onClick={() => upgrade.mutate(product)}
                disabled={current || upgrade.isPending}
                style={{ width: "100%", justifyContent: "center" }}
              >
                {current ? "Current plan" : upgrade.isPending ? "Upgrading…" : "Upgrade"}
              </Button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

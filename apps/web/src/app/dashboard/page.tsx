"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, CaptureOSLogo, Eyebrow, Input } from "@/components/captureos";
import { captureosFontVars } from "@/lib/captureos-fonts";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me, Org } from "@/lib/types";

// Org picker — shown to authenticated users who land at "/" (already-authed
// visitors get bounced here from the landing page) or have no org yet.
// Everyone else skips straight from /login to their org's workspace, so this
// page mostly matters for multi-org accounts and the empty "no orgs yet" case.
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
    return (
      <div
        className={`captureos ${captureosFontVars}`}
        style={{ display: "grid", placeItems: "center", minHeight: "100vh", color: "var(--gr-muted)" }}
      >
        Loading…
      </div>
    );
  }

  const me = meQuery.data;

  return (
    <div className={`captureos ${captureosFontVars}`} style={{ minHeight: "100vh" }}>
      <style>{`
        .gr-dashboard-org-card:hover { border-color: var(--gr-border-strong) !important; background: var(--gr-hover) !important; }
      `}</style>
      <div style={{ maxWidth: 640, margin: "0 auto", padding: "56px 24px 80px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 40 }}>
          <div>
            <CaptureOSLogo markSize={28} wordmarkSize={18} />
            <p style={{ margin: "10px 0 0", fontSize: 13.5, color: "var(--gr-muted-3)" }}>
              {me ? `Signed in as ${me.user.email}` : "Loading your account…"}
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
          >
            Sign out
          </Button>
        </div>

        <Eyebrow style={{ marginBottom: 10 }}>Your organizations</Eyebrow>

        {meQuery.isLoading && <p style={{ fontSize: 13.5, color: "var(--gr-muted)" }}>Loading…</p>}
        {meQuery.isError && (
          <p style={{ fontSize: 13.5, color: "#F0A593" }}>Could not load organizations.</p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
          {me?.orgs.map((org) => (
            <Link key={org.orgId} href={`/orgs/${org.orgId}/workspace/find`} style={{ textDecoration: "none" }}>
              <Card
                padding={18}
                style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
                className="gr-dashboard-org-card"
              >
                <div>
                  <p style={{ margin: 0, fontWeight: 700, fontSize: 14.5, color: "var(--gr-text-strong)" }}>
                    {org.name}
                  </p>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--gr-muted-3)" }}>
                    Role: {org.role} · Plan: {org.plan}
                  </p>
                </div>
                <span style={{ fontSize: 13, color: "var(--gr-muted-2)" }}>Open →</span>
              </Card>
            </Link>
          ))}
          {me && me.orgs.length === 0 && (
            <Card padding="26px 20px" style={{ borderStyle: "dashed", borderColor: "var(--gr-border-input)", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: 13.5, color: "var(--gr-muted-3)" }}>
                No organizations yet. Create one below to get started.
              </p>
            </Card>
          )}
        </div>

        <form onSubmit={onCreateOrg} style={{ display: "flex", gap: 10 }}>
          <Input
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="New organization name"
            style={{ flex: 1 }}
          />
          <Button type="submit" variant="primary" disabled={createOrg.isPending || !orgName.trim()}>
            {createOrg.isPending ? "Creating…" : "Create"}
          </Button>
        </form>
        {createOrg.isError && (
          <p style={{ marginTop: 8, fontSize: 13, color: "#F0A593" }}>Could not create organization.</p>
        )}

        <p style={{ marginTop: 40, fontSize: 12.5, color: "var(--gr-muted-3)", lineHeight: 1.6 }}>
          Open an organization to access the Company Brain, opportunity scanning, filings, audit,
          and billing.{" "}
          <Link href="/#how" style={{ color: "var(--gr-muted-2)", textDecoration: "underline" }}>
            How CaptureOS works
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

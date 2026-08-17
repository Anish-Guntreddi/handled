"use client";

import { useEffect, type ReactNode } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me } from "@/lib/types";

import { CaptureOSHeader, type WorkspaceTab } from "./Header";

// Falls back to the email's first two characters when no name is set yet
// (fullName is optional at registration).
function initialsFor(user: { email: string; fullName: string | null }): string {
  const name = user.fullName?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return parts[0].slice(0, 2).toUpperCase();
  }
  return user.email.slice(0, 2).toUpperCase();
}

// Derives the active workspace tab from the current pathname so the header can
// highlight it. Audit/Billing sit outside the Find/Copilot/Pursue/Stay job-
// based IA (reachable via the header's secondary links from anywhere), so
// neither should falsely highlight a primary tab. Defaults to "find" for
// everything else (the workspace landing surface).
function activeTabFromPath(pathname: string): WorkspaceTab | null {
  if (pathname.includes("/audit") || pathname.includes("/billing")) return null;
  if (pathname.includes("/workspace/copilot")) return "copilot";
  if (pathname.includes("/workspace/pursue")) return "pursue";
  if (pathname.includes("/workspace/stay")) return "stay";
  return "find";
}

// Client shell for the CaptureOS workspace: auth-gates the surface (matching the
// existing orgs/[orgId] pattern), renders the sticky header, and lays out the
// max-width 1160px content column. The theme class + font variables are applied
// by the workspace layout that wraps this.
export function WorkspaceShell({ children }: { children: ReactNode }) {
  const params = useParams<{ orgId: string }>();
  const orgId = params.orgId;
  const pathname = usePathname();
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/auth/me"),
    enabled: isAuthenticated,
  });
  const initials = meQuery.data ? initialsFor(meQuery.data.user) : undefined;

  if (loading || !isAuthenticated) {
    return (
      <div style={{ display: "grid", minHeight: "100vh", placeItems: "center", color: "var(--gr-muted-3)" }}>
        Loading…
      </div>
    );
  }

  return (
    <>
      <CaptureOSHeader orgId={orgId} activeTab={activeTabFromPath(pathname)} initials={initials} />
      <main style={{ maxWidth: 1160, margin: "0 auto", padding: "0 28px 90px" }}>{children}</main>
    </>
  );
}

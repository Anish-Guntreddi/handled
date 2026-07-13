"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

// Superseded by the Pursue tab's own filing-detail view, which reimplements
// this exact flow (extract → match evidence → recommend → build package)
// against the same endpoints via a `?filing={id}` search param. Kept as a
// redirect — preserving the filing id — so any existing bookmarks/links
// still resolve.
export default function FilingDetailRedirect() {
  const { orgId, filingId } = useParams<{ orgId: string; filingId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/orgs/${orgId}/workspace/pursue?filing=${encodeURIComponent(filingId)}`);
  }, [orgId, filingId, router]);

  return null;
}

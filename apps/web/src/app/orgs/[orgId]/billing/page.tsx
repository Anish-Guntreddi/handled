"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

// Moved under workspace/ so it inherits the shared CaptureOS shell (theme,
// header, auth-gate) — see workspace/billing/page.tsx. Kept as a redirect so
// any existing bookmarks/links still resolve.
export default function BillingRedirect() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/orgs/${orgId}/workspace/billing`);
  }, [orgId, router]);

  return null;
}

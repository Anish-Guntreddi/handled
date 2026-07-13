"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

// The old "Company Brain" surface (profile build, document ingestion, GovCon
// scan) — fully superseded by the onboarding wizard (profile + enrichment +
// scan in one flow) and the Find tab (unified program/contract/grant
// discovery). Kept as a redirect so any existing bookmarks/links still
// resolve. Returning users land on Find; anyone without a profile yet gets
// nudged to onboarding via Find's own empty state / the header's profile ring.
export default function OrgRootRedirect() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/orgs/${orgId}/workspace/find`);
  }, [orgId, router]);

  return null;
}

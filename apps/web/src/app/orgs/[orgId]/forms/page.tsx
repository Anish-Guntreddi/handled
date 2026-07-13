"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

// Superseded by the Pursue tab — the same GET /forms data is already rendered
// inside a filing's detail view (?filing={id}). Kept as a redirect so any
// existing bookmarks/links still resolve.
export default function FormsRedirect() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/orgs/${orgId}/workspace/pursue`);
  }, [orgId, router]);

  return null;
}

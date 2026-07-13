"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

// Superseded by the Find tab — same /programs + /programs/scan endpoints,
// now inside the unified Discovery feed (programs + contracts + grants,
// ranked together). Kept as a redirect so any existing bookmarks/links still
// resolve.
export default function MoneyFinderRedirect() {
  const { orgId } = useParams<{ orgId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/orgs/${orgId}/workspace/find`);
  }, [orgId, router]);

  return null;
}

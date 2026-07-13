"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// This content now lives on the landing page (`/#how`). Kept as a redirect so
// any existing bookmarks/links to /how-it-works still resolve.
export default function HowItWorksRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/#how");
  }, [router]);

  return null;
}

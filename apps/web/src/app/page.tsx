"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function Home() {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(isAuthenticated ? "/dashboard" : "/login");
  }, [isAuthenticated, loading, router]);

  return (
    <main className="grid min-h-screen place-items-center text-neutral-500">
      <span>Loading Handled…</span>
    </main>
  );
}

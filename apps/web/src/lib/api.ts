// Typed fetch client for the CaptureOS API. Attaches the bearer token, understands
// the {error:{code,message,details}} contract, and never leaks raw responses.

import type { WorkflowRun } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// The AuthProvider registers a getter so every request auto-attaches the token.
let tokenGetter: () => string | null = () => null;
export function setTokenGetter(fn: () => string | null): void {
  tokenGetter = fn;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = opts.token ?? tokenGetter();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: unknown } })
      .error ?? { code: "error", message: res.statusText };
    throw new ApiError(res.status, err.code ?? "error", err.message ?? "Request failed", err.details);
  }
  return data as T;
}

// Raw PUT for the local upload sink (the returned uploadUrl already includes /api/v1).
export async function uploadBlob(uploadUrl: string, data: Blob): Promise<void> {
  const headers: Record<string, string> = {};
  const token = tokenGetter();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (data.type) headers["Content-Type"] = data.type;
  const res = await fetch(`${API_BASE}${uploadUrl}`, { method: "PUT", headers, body: data });
  if (!res.ok) throw new ApiError(res.status, "upload_failed", "Upload failed");
}

const TERMINAL = new Set(["succeeded", "failed", "needs_input"]);

// Poll a long-running workflow until it reaches a terminal state (PRD §9.4).
export async function pollWorkflowRun(
  orgId: string,
  runId: string,
  { maxAttempts = 40, intervalMs = 500 }: { maxAttempts?: number; intervalMs?: number } = {},
): Promise<WorkflowRun> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const run = await apiFetch<WorkflowRun>(`/orgs/${orgId}/workflow-runs/${runId}`);
    if (TERMINAL.has(run.status)) return run;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new ApiError(408, "timeout", "Workflow did not complete in time");
}

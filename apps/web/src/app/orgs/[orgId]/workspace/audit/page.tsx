"use client";

import type { CSSProperties } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button, Card, Eyebrow } from "@/components/captureos";
import { apiDownload, apiFetch } from "@/lib/api";
import type { AuditEventResponse, AuditMetrics, WorkflowRunSummary } from "@/lib/types";

// Audit & activity — every workflow run, cost, and time-saved figure, plus the
// raw event feed and a CSV/JSON export. Lives under workspace/ to inherit the
// shared shell (theme, header, auth-gate) from workspace/layout.tsx, but isn't
// one of the four primary Find/Copilot/Pursue/Stay tabs — it's cross-cutting,
// reachable from anywhere via the header's "Audit" link.

const STATUS_STYLE: Record<string, CSSProperties> = {
  succeeded: { background: "rgba(46,158,102,.16)", color: "#74d89b" },
  failed: { background: "rgba(240,138,120,.14)", color: "#F0A593" },
  running: { background: "rgba(242,182,110,.14)", color: "var(--gr-amber)" },
  queued: { background: "var(--gr-input)", color: "var(--gr-muted-2)" },
  needs_input: { background: "rgba(242,182,110,.14)", color: "var(--gr-amber)" },
};

export default function AuditPage() {
  const { orgId } = useParams<{ orgId: string }>();

  const metrics = useQuery({
    queryKey: ["audit-metrics", orgId],
    queryFn: () => apiFetch<AuditMetrics>(`/orgs/${orgId}/audit/metrics`),
  });
  const runs = useQuery({
    queryKey: ["audit-runs", orgId],
    queryFn: () => apiFetch<WorkflowRunSummary[]>(`/orgs/${orgId}/audit/runs?limit=50`),
  });
  const events = useQuery({
    queryKey: ["audit-events", orgId],
    queryFn: () => apiFetch<AuditEventResponse[]>(`/orgs/${orgId}/audit/events?limit=20`),
  });
  const exportAudit = useMutation({
    mutationFn: (format: "csv" | "json") =>
      apiDownload(`/orgs/${orgId}/audit/export?format=${format}`, "GET"),
  });

  const m = metrics.data;

  return (
    <div style={{ paddingTop: 44 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 30 }}>
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Audit &amp; activity</Eyebrow>
          <h1
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 40,
              fontWeight: 400,
              lineHeight: 1.02,
              letterSpacing: "-.01em",
              margin: 0,
              color: "var(--gr-heading)",
            }}
          >
            Every workflow run, accounted for.
          </h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="secondary" onClick={() => exportAudit.mutate("csv")}>
            Export CSV
          </Button>
          <Button variant="secondary" onClick={() => exportAudit.mutate("json")}>
            Export JSON
          </Button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", marginBottom: 28 }}>
        <MetricTile label="Filings" value={m?.filings ?? "—"} />
        <MetricTile label="Workflow runs" value={m?.runs ?? "—"} sub={m ? `${m.succeededRuns} succeeded` : undefined} />
        <MetricTile label="Time saved" value={m ? `${m.totalTimeSavedMinutes} min` : "—"} />
        <MetricTile
          label="Est. cost / filing"
          value={m ? `$${m.costPerFilingUsd.toFixed(4)}` : "—"}
          sub={m ? `$${m.estimatedCostUsd.toFixed(4)} total` : undefined}
        />
      </div>

      <Card padding={0} style={{ marginBottom: 20, overflow: "hidden" }}>
        <div style={{ padding: "18px 22px 0" }}>
          <Eyebrow>Workflow runs</Eyebrow>
        </div>
        <div style={{ overflowX: "auto", padding: "12px 22px 20px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--gr-muted-3)" }}>
                {["Type", "Status", "Steps", "Time saved", "Tokens"].map((h) => (
                  <th key={h} style={{ fontWeight: 600, padding: "8px 10px 8px 0", fontSize: 11.5, textTransform: "uppercase", letterSpacing: ".06em" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(runs.data ?? []).map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid var(--gr-border-soft)" }}>
                  <td style={{ padding: "10px 10px 10px 0", fontWeight: 600, color: "var(--gr-text)" }}>
                    {r.type.replace(/_/g, " ")}
                  </td>
                  <td style={{ padding: "10px 0" }}>
                    <span
                      style={{
                        display: "inline-block",
                        borderRadius: 6,
                        padding: "2px 9px",
                        fontSize: 11.5,
                        fontWeight: 700,
                        ...(STATUS_STYLE[r.status] ?? { background: "var(--gr-input)", color: "var(--gr-muted-2)" }),
                      }}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0", color: "var(--gr-muted)" }}>{r.stepCount}</td>
                  <td style={{ padding: "10px 0", color: "var(--gr-muted)" }}>{r.timeSavedMinutes ?? 0} min</td>
                  <td style={{ padding: "10px 0", color: "var(--gr-muted-3)" }}>
                    {r.inputTokens + r.outputTokens}
                  </td>
                </tr>
              ))}
              {(runs.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: "24px 0", textAlign: "center", color: "var(--gr-muted-3)" }}>
                    No runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padding={22} style={{ marginBottom: 60 }}>
        <Eyebrow style={{ marginBottom: 14 }}>Recent audit events</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {(events.data ?? []).map((e) => (
            <div key={e.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <span style={{ fontFamily: "var(--gr-font-mono)", fontSize: 12.5, color: "var(--gr-text)" }}>
                {e.action}
              </span>
              <span style={{ fontSize: 12, color: "var(--gr-muted-3)" }}>
                {e.actor}
                {e.model ? ` · ${e.model}` : ""}
              </span>
            </div>
          ))}
          {(events.data ?? []).length === 0 && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--gr-muted-3)" }}>No events yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function MetricTile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card padding={18}>
      <Eyebrow style={{ marginBottom: 8 }}>{label}</Eyebrow>
      <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 30, fontWeight: 400, color: "var(--gr-heading)" }}>
        {value}
      </div>
      {sub && <div style={{ marginTop: 2, fontSize: 12, color: "var(--gr-muted-3)" }}>{sub}</div>}
    </Card>
  );
}

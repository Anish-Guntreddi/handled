// Eligibility pill: green "You qualify" (confirmed) or amber "Likely — review".
// Matches the inline eligibility chips in the design's opportunity rows.

type Eligibility = "qualify" | "likely";

const STYLES: Record<
  Eligibility,
  { label: string; bg: string; color: string; dot: string }
> = {
  qualify: {
    label: "You qualify",
    bg: "rgba(46,158,102,.16)",
    color: "#74d89b",
    dot: "#57c98a",
  },
  likely: {
    label: "Likely — review",
    bg: "rgba(242,182,110,.14)",
    color: "var(--gr-amber)",
    dot: "var(--gr-amber)",
  },
};

export function EligibilityBadge({
  status,
  label,
}: {
  status: Eligibility;
  label?: string;
}) {
  const s = STYLES[status];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        padding: "2px 9px",
        fontSize: 11.5,
        fontWeight: 700,
        background: s.bg,
        color: s.color,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot }} />
      {label ?? s.label}
    </span>
  );
}

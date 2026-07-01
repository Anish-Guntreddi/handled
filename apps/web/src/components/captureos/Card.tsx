import type { CSSProperties, ReactNode } from "react";

// Surface card — the standard 14px-radius panel used across every CaptureOS
// surface. `tone="money"` swaps to the green "money" palette (bg #10402B).
export function Card({
  children,
  tone = "default",
  padding = 24,
  style,
  className,
}: {
  children: ReactNode;
  tone?: "default" | "money";
  padding?: number | string;
  style?: CSSProperties;
  className?: string;
}) {
  const money = tone === "money";
  return (
    <div
      className={className}
      style={{
        background: money ? "var(--gr-money-bg)" : "var(--gr-surface)",
        border: `1px solid ${money ? "var(--gr-money-border)" : "var(--gr-border)"}`,
        borderRadius: "var(--gr-radius-card)",
        padding,
        color: money ? "#eaf7ee" : "var(--gr-text)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

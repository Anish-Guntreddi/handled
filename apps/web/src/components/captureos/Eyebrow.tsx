import type { CSSProperties, ReactNode } from "react";

// Mono "eyebrow" label — small (10–11px), 600 weight, wide tracking, uppercase.
// Used above every surface title and as section kickers.
export function Eyebrow({
  children,
  color = "var(--gr-muted-2)",
  size = 11,
  style,
}: {
  children: ReactNode;
  color?: string;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        fontFamily: "var(--gr-font-mono)",
        fontSize: size,
        fontWeight: 600,
        letterSpacing: ".12em",
        textTransform: "uppercase",
        color,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

"use client";

import { useState, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from "react";

// CaptureOS button. `primary` = solid green with dark on-green text (hover #38B074);
// `secondary` = bordered surface chip (hover border brightens). Hover is handled
// in JS so the design's exact hover colors are preserved without extra CSS.

type Variant = "primary" | "secondary";

const BASE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 9,
  fontFamily: "var(--gr-font-sans)",
  fontWeight: 700,
  cursor: "pointer",
  whiteSpace: "nowrap",
  borderRadius: "var(--gr-radius-control)",
};

export function Button({
  children,
  variant = "primary",
  style,
  ...rest
}: {
  children: ReactNode;
  variant?: Variant;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const [hover, setHover] = useState(false);

  const variantStyle: CSSProperties =
    variant === "primary"
      ? {
          background: hover ? "var(--gr-green-hover)" : "var(--gr-green)",
          color: "var(--gr-on-green)",
          border: "1px solid var(--gr-green)",
          fontSize: 14.5,
          padding: "14px 22px",
        }
      : {
          background: "var(--gr-surface)",
          color: "var(--gr-text)",
          border: `1px solid ${hover ? "var(--gr-border-strong)" : "var(--gr-border)"}`,
          fontSize: 14,
          padding: "12px 18px",
        };

  return (
    <button
      {...rest}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ ...BASE, ...variantStyle, ...style }}
    >
      {children}
    </button>
  );
}

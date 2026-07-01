import type { ReactNode } from "react";

import { Card } from "./Card";
import { Eyebrow } from "./Eyebrow";

// Phase-1 placeholder for a workspace surface: the designed eyebrow + an
// Instrument-Serif title, an intro line, and a "coming in the next phase"
// note. Later phases replace the children of each tab page; this keeps the
// shell navigable and on-brand in the meantime.
export function SurfaceStub({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  children?: ReactNode;
}) {
  return (
    <div style={{ paddingTop: 44, maxWidth: 780 }}>
      <Eyebrow style={{ marginBottom: 8 }}>{eyebrow}</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 46,
          fontWeight: 400,
          lineHeight: 1,
          letterSpacing: "-.01em",
          margin: "0 0 10px",
          color: "var(--gr-heading)",
        }}
      >
        {title}
      </h1>
      {intro && (
        <p style={{ margin: "0 0 24px", color: "var(--gr-muted)", fontSize: 16, lineHeight: 1.5, maxWidth: 620 }}>
          {intro}
        </p>
      )}

      <Card style={{ borderStyle: "dashed", borderColor: "var(--gr-border-input)" }} padding="40px 28px">
        <Eyebrow color="var(--gr-green-bright)" style={{ marginBottom: 10 }}>
          Coming in the next phase
        </Eyebrow>
        <p style={{ margin: 0, color: "var(--gr-muted-3)", fontSize: 14.5, lineHeight: 1.6, maxWidth: 560 }}>
          This surface is part of the CaptureOS redesign and will be built on top of the shared
          foundation in a later phase. The theme, shell, navigation, and reusable primitives are
          already in place.
        </p>
        {children}
      </Card>
    </div>
  );
}

// Granted logo: a green rounded square holding the rising-chart mark, next to
// the "Granted" wordmark. The mark is reused at multiple sizes (header 28px,
// onboarding 30px, chat avatar 20px), so size is parameterized.

export function GrantedMark({ size = 28 }: { size?: number }) {
  const icon = Math.round(size * 0.57);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 7,
        background: "var(--gr-green)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <svg
        width={icon}
        height={icon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--gr-on-green)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 17 L11 10 L15 14 L21 7" />
        <path d="M15 7 H21 V13" />
      </svg>
    </div>
  );
}

export function GrantedWordmark({ size = 18 }: { size?: number }) {
  return (
    <span style={{ fontWeight: 800, fontSize: size, letterSpacing: "-.02em", color: "var(--gr-heading)" }}>
      Handled
    </span>
  );
}

// Small mono "PRO" pill that sits after the wordmark in the header.
export function ProPill() {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        marginLeft: 4,
        background: "var(--gr-green)",
        color: "var(--gr-on-green)",
        borderRadius: 5,
        padding: "2px 7px",
        fontFamily: "var(--gr-font-mono)",
        fontSize: 9.5,
        fontWeight: 700,
        letterSpacing: ".06em",
      }}
    >
      PRO
    </span>
  );
}

// Logo lockup: mark + wordmark (+ optional PRO pill).
export function GrantedLogo({
  markSize = 28,
  wordmarkSize = 18,
  pro = false,
}: {
  markSize?: number;
  wordmarkSize?: number;
  pro?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <GrantedMark size={markSize} />
      <GrantedWordmark size={wordmarkSize} />
      {pro && <ProPill />}
    </div>
  );
}

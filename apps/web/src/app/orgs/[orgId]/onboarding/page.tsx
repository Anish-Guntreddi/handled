"use client";

import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";

import { Card, Eyebrow, CaptureOSLogo, Input, Textarea } from "@/components/captureos";
import { ApiError, apiFetch, errorMessage, pollWorkflowRun } from "@/lib/api";
import { captureosFontVars } from "@/lib/captureos-fonts";
import { useAuth } from "@/lib/auth";
import type { WorkflowRunCreated } from "@/lib/types";

// Onboarding wizard — the four-step profile capture that seeds the Company Brain
// before the first money scan. Self-themed (it sits outside the `.captureos`
// workspace layout), it mirrors the design's WIZARD + LOADING screens exactly:
// business basics → team size → ownership → activities → submit → scan loader →
// /workspace/find. State lives in one object so Back never loses entered values.

// ---- Step model -----------------------------------------------------------

const STEP_TITLES = [
  "Tell us about your business",
  "How big is your team?",
  "Who owns the business?",
  "What does your business actually do?",
] as const;
const LAST_STEP = STEP_TITLES.length - 1;

const EMPLOYEE_OPTIONS = ["Just me", "2–10", "11–50", "51–500"] as const;
const REVENUE_OPTIONS = ["<$100K", "$100K–$1M", "$1M–$5M", "$5M–$25M", "$25M+"] as const;

// Ownership / activity rows: { code → [label, desc] }. The codes are the wire
// values; the label/desc are what the user sees.
const OWNERSHIP_OPTIONS: { code: string; label: string; desc: string }[] = [
  {
    code: "woman_owned",
    label: "Woman-owned",
    desc: "51%+ owned by women — unlocks WOSB set-asides",
  },
  {
    code: "service_disabled",
    label: "Service-disabled veteran-owned",
    desc: "→ SDVOSB sole-source contracts",
  },
  { code: "veteran", label: "Veteran-owned", desc: "→ veteran contracting advantages" },
  {
    code: "disadvantaged",
    label: "Socially & economically disadvantaged",
    desc: "→ the 8(a) program",
  },
  { code: "hubzone", label: "Located in a HUBZone", desc: "→ HUBZone price preference" },
];

const ACTIVITY_OPTIONS: { code: string; label: string; desc: string }[] = [
  {
    code: "rnd",
    label: "We do R&D / build new products or software",
    desc: "→ SBIR grants + R&D tax credit",
  },
  { code: "hiring", label: "We hire employees", desc: "→ Work Opportunity Tax Credit" },
  {
    code: "products",
    label: "We buy equipment or sell products",
    desc: "→ Section 179 expensing",
  },
  { code: "services", label: "We provide services", desc: "→ contracts & set-asides" },
];

// Sources we surface in the loading checklist, matching the design's scan lines.
const SCAN_LINES = [
  "SAM.gov — federal contracts",
  "Grants.gov — 17,000+ grants",
  "SBA — loans & certifications",
  "IRS — tax credits",
  "SBIR.gov — R&D funding",
] as const;

type WizardState = {
  companyName: string;
  doWhat: string;
  industry: string;
  location: string;
  employees: string; // selected label, "" = unset
  revenue: string; // selected label, "" = unset
  ownership: string[]; // selected codes
  activities: string[]; // selected codes
};

const INITIAL: WizardState = {
  companyName: "",
  doWhat: "",
  industry: "",
  location: "",
  employees: "",
  revenue: "",
  ownership: [],
  activities: [],
};

function toggle(list: string[], code: string): string[] {
  return list.includes(code) ? list.filter((c) => c !== code) : [...list, code];
}

// ---- Shared styles (lifted from the design source) ------------------------

const FIELD_LABEL: CSSProperties = {
  display: "block",
  fontFamily: "var(--gr-font-mono)",
  fontSize: 10.5,
  fontWeight: 600,
  letterSpacing: ".1em",
  textTransform: "uppercase",
  color: "var(--gr-muted-2)",
  marginBottom: 8,
};

export default function OnboardingPage() {
  const params = useParams<{ orgId: string }>();
  const orgId = params.orgId;
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState(0);
  const [data, setData] = useState<WizardState>(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const set = useCallback(
    <K extends keyof WizardState>(key: K, value: WizardState[K]) =>
      setData((prev) => ({ ...prev, [key]: value })),
    [],
  );

  const back = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);
  const next = useCallback(() => setStep((s) => Math.min(s + 1, LAST_STEP)), []);

  // POST the profile (202 → workflowRunId), poll the scan to terminal, then
  // hand off to Find. Validation is intentionally lenient — every field is
  // skippable, so we only ever block on the network, never on empty inputs.
  const finish = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/onboarding`,
        {
          method: "POST",
          body: {
            companyName: data.companyName,
            doWhat: data.doWhat,
            industry: data.industry,
            location: data.location,
            employees: data.employees,
            revenue: data.revenue,
            ownership: data.ownership,
            activities: data.activities,
          },
        },
      );
      const run = await pollWorkflowRun(orgId, workflowRunId, { maxAttempts: 60 });
      if (run.status === "failed") {
        throw new ApiError(500, "onboarding_failed", run.error ?? "We couldn't finish the scan.");
      }
      router.push(`/orgs/${orgId}/workspace/find`);
    } catch (err) {
      setError(errorMessage(err, "We couldn't finish setting up. Please try again."));
      setSubmitting(false);
    }
  }, [orgId, data, router]);

  if (loading || !isAuthenticated) {
    return (
      <div
        className={`captureos ${captureosFontVars}`}
        style={{ display: "grid", placeItems: "center", minHeight: "100vh", color: "var(--gr-muted)" }}
      >
        Loading…
      </div>
    );
  }

  if (submitting) {
    return <LoadingScreen companyName={data.companyName} />;
  }

  const isLast = step === LAST_STEP;

  return (
    <div
      className={`captureos ${captureosFontVars} gr-weave`}
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "44px 20px 72px",
      }}
    >
      <div style={{ width: "100%", maxWidth: 600 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 11,
            marginBottom: 34,
          }}
        >
          <CaptureOSLogo markSize={30} wordmarkSize={20} />
        </div>

        <Eyebrow color="var(--gr-muted-2)" style={{ letterSpacing: ".14em", marginBottom: 10 }}>
          Step {String(step + 1).padStart(2, "0")} — 04 · {STEP_TITLES[step].toUpperCase()}
        </Eyebrow>
        <div style={{ display: "flex", gap: 6, marginBottom: 26 }}>
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                height: 3,
                flex: 1,
                borderRadius: 2,
                background: i <= step ? "var(--gr-green)" : "var(--gr-border)",
              }}
            />
          ))}
        </div>

        <Card padding={36}>
          {step === 0 && <StepBusiness data={data} set={set} />}
          {step === 1 && <StepTeam data={data} set={set} />}
          {step === 2 && (
            <StepChecklist
              title="Who owns the business?"
              intro="Each of these can unlock set-aside contracts worth real money. Check all that apply — skip anything you're unsure of."
              options={OWNERSHIP_OPTIONS}
              selected={data.ownership}
              onToggle={(code) => set("ownership", toggle(data.ownership, code))}
            />
          )}
          {step === 3 && (
            <StepChecklist
              title="What does your business actually do?"
              intro="This is where a lot of hidden money lives — R&D credits, SBIR grants, and hiring credits all hinge on these."
              options={ACTIVITY_OPTIONS}
              selected={data.activities}
              onToggle={(code) => set("activities", toggle(data.activities, code))}
            />
          )}
        </Card>

        {error && (
          <p
            role="alert"
            style={{
              marginTop: 16,
              marginBottom: 0,
              padding: "11px 14px",
              borderRadius: 9,
              background: "rgba(240,138,120,.12)",
              border: "1px solid rgba(240,138,120,.32)",
              color: "#F0A593",
              fontSize: 13.5,
              lineHeight: 1.5,
            }}
          >
            {error}
          </p>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 24,
          }}
        >
          <NavButton variant="back" onClick={back} hidden={step === 0}>
            ← Back
          </NavButton>
          {isLast ? (
            <NavButton variant="primary" onClick={finish}>
              Find my money <span style={{ fontSize: 16 }}>→</span>
            </NavButton>
          ) : (
            <NavButton variant="primary" onClick={next}>
              Continue <span style={{ fontSize: 16 }}>→</span>
            </NavButton>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- Step 0: business basics ---------------------------------------------

function StepBusiness({
  data,
  set,
}: {
  data: WizardState;
  set: <K extends keyof WizardState>(key: K, value: WizardState[K]) => void;
}) {
  return (
    <div className="gr-animate-rise">
      <StepHeading>Tell us about your business</StepHeading>
      <StepIntro>
        The more you tell us, the more money we can find. Takes about two minutes — skip anything
        you&apos;re unsure of.
      </StepIntro>

      <label style={FIELD_LABEL}>Business name</label>
      <Input
        value={data.companyName}
        onChange={(e) => set("companyName", e.target.value)}
        placeholder="Acme Robotics, Inc."
        style={{ marginBottom: 20 }}
      />

      <label style={FIELD_LABEL}>What does your business do?</label>
      <Textarea
        value={data.doWhat}
        onChange={(e) => set("doWhat", e.target.value)}
        rows={3}
        placeholder="In a sentence or two — what you build, sell, or provide."
        style={{ marginBottom: 20 }}
      />

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label style={FIELD_LABEL}>Industry</label>
          <Input
            value={data.industry}
            onChange={(e) => set("industry", e.target.value)}
            placeholder="e.g. Health tech"
          />
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label style={FIELD_LABEL}>Location · optional</label>
          <Input
            value={data.location}
            onChange={(e) => set("location", e.target.value)}
            placeholder="City, State"
          />
        </div>
      </div>
    </div>
  );
}

// ---- Step 1: team size & revenue -----------------------------------------

function StepTeam({
  data,
  set,
}: {
  data: WizardState;
  set: <K extends keyof WizardState>(key: K, value: WizardState[K]) => void;
}) {
  return (
    <div className="gr-animate-rise">
      <StepHeading>How big is your team?</StepHeading>
      <StepIntro>
        Size decides which set-asides and loan programs fit. Ranges are perfectly fine.
      </StepIntro>

      <label style={{ ...FIELD_LABEL, marginBottom: 11 }}>Number of employees</label>
      <div style={{ display: "flex", gap: 9, flexWrap: "wrap", marginBottom: 26 }}>
        {EMPLOYEE_OPTIONS.map((opt) => (
          <OptionChip
            key={opt}
            label={opt}
            selected={data.employees === opt}
            onClick={() => set("employees", data.employees === opt ? "" : opt)}
          />
        ))}
      </div>

      <label style={{ ...FIELD_LABEL, marginBottom: 11 }}>Annual revenue</label>
      <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
        {REVENUE_OPTIONS.map((opt) => (
          <OptionChip
            key={opt}
            label={opt}
            selected={data.revenue === opt}
            onClick={() => set("revenue", data.revenue === opt ? "" : opt)}
          />
        ))}
      </div>
    </div>
  );
}

// ---- Steps 2 & 3: multi-select checklists --------------------------------

function StepChecklist({
  title,
  intro,
  options,
  selected,
  onToggle,
}: {
  title: string;
  intro: string;
  options: { code: string; label: string; desc: string }[];
  selected: string[];
  onToggle: (code: string) => void;
}) {
  return (
    <div className="gr-animate-rise">
      <StepHeading>{title}</StepHeading>
      <StepIntro>{intro}</StepIntro>
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        {options.map((o) => (
          <CheckRow
            key={o.code}
            label={o.label}
            desc={o.desc}
            checked={selected.includes(o.code)}
            onToggle={() => onToggle(o.code)}
          />
        ))}
      </div>
    </div>
  );
}

// ---- Loading screen -------------------------------------------------------

function LoadingScreen({ companyName }: { companyName: string }) {
  const who = companyName.trim() || "your business";
  return (
    <div
      className={`captureos ${captureosFontVars} gr-weave`}
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        className="gr-animate-spin"
        style={{
          width: 48,
          height: 48,
          borderRadius: "50%",
          border: "3px solid var(--gr-border-soft)",
          borderTopColor: "var(--gr-green-bright)",
          marginBottom: 28,
        }}
      />
      <h2
        style={{
          fontFamily: "var(--gr-font-serif)",
          fontSize: 34,
          fontWeight: 400,
          letterSpacing: "-.01em",
          margin: "0 0 8px",
          textAlign: "center",
          color: "var(--gr-heading)",
        }}
      >
        Finding the money you qualify for…
      </h2>
      <p style={{ margin: "0 0 30px", color: "var(--gr-muted)", fontSize: 15, textAlign: "center" }}>
        Matching {who} against every federal &amp; state program.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%", maxWidth: 360 }}>
        {SCAN_LINES.map((line) => (
          <div key={line} style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--gr-green-bright)"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20 6 L9 17 L4 12" />
            </svg>
            <span
              style={{
                fontFamily: "var(--gr-font-mono)",
                fontSize: 13,
                fontWeight: 500,
                color: "var(--gr-muted)",
              }}
            >
              {line}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Small building blocks ------------------------------------------------

function StepHeading({ children }: { children: ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: "var(--gr-font-serif)",
        fontSize: 38,
        fontWeight: 400,
        lineHeight: 1.05,
        letterSpacing: "-.01em",
        margin: "0 0 8px",
        color: "var(--gr-heading)",
      }}
    >
      {children}
    </h2>
  );
}

function StepIntro({ children }: { children: ReactNode }) {
  return (
    <p style={{ margin: "0 0 26px", color: "var(--gr-muted)", fontSize: 15, lineHeight: 1.55 }}>
      {children}
    </p>
  );
}

// Single-select pill for employee count / revenue. Selected = solid green.
function OptionChip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      style={{
        padding: "10px 17px",
        borderRadius: 8,
        fontSize: 14,
        fontWeight: 600,
        cursor: "pointer",
        fontFamily: "var(--gr-font-sans)",
        background: selected ? "var(--gr-green)" : "var(--gr-input)",
        border: `1px solid ${selected ? "var(--gr-green)" : "var(--gr-border-input)"}`,
        color: selected ? "var(--gr-on-green)" : "#C9BEA4",
      }}
    >
      {label}
    </button>
  );
}

// Multi-select checkbox row: green tinted + checked box when selected.
function CheckRow({
  label,
  desc,
  checked,
  onToggle,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      role="checkbox"
      aria-checked={checked}
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle();
        }
      }}
      style={{
        display: "flex",
        gap: 13,
        alignItems: "flex-start",
        padding: "15px 16px",
        borderRadius: 10,
        cursor: "pointer",
        background: checked ? "rgba(46,158,102,.12)" : "var(--gr-input)",
        border: `1px solid ${checked ? "rgba(116,216,165,.35)" : "var(--gr-border)"}`,
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: 22,
          height: 22,
          borderRadius: 6,
          marginTop: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: checked ? "var(--gr-green)" : "transparent",
          border: checked ? "1px solid var(--gr-green)" : "1.5px solid var(--gr-border-strong)",
        }}
      >
        {checked && (
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--gr-on-green)"
            strokeWidth="3.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6 L9 17 L4 12" />
          </svg>
        )}
      </div>
      <div>
        <div style={{ fontWeight: 700, fontSize: 14.5, color: "var(--gr-text)" }}>{label}</div>
        <div style={{ fontSize: 12.5, color: "var(--gr-muted-3)", marginTop: 2 }}>{desc}</div>
      </div>
    </div>
  );
}

// Back / Continue / Find-my-money nav buttons. Hover handled in JS to keep the
// design's exact hover colors. `back` is hidden (not removed) on step 0 so the
// primary button stays right-aligned.
function NavButton({
  children,
  variant,
  onClick,
  hidden = false,
}: {
  children: ReactNode;
  variant: "primary" | "back";
  onClick: () => void;
  hidden?: boolean;
}) {
  const [hover, setHover] = useState(false);
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 9,
    borderRadius: 9,
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "var(--gr-font-sans)",
  };
  const variantStyle: CSSProperties =
    variant === "primary"
      ? {
          padding: "14px 26px",
          background: hover ? "var(--gr-green-hover)" : "var(--gr-green)",
          color: "var(--gr-on-green)",
          border: "1px solid var(--gr-green)",
        }
      : {
          padding: "14px 20px",
          background: "var(--gr-surface)",
          color: "#C9BEA4",
          border: `1px solid ${hover ? "var(--gr-border-strong)" : "var(--gr-border)"}`,
          visibility: hidden ? "hidden" : "visible",
        };
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      aria-hidden={hidden}
      tabIndex={hidden ? -1 : undefined}
      style={{ ...base, ...variantStyle }}
    >
      {children}
    </button>
  );
}

"use client";

import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { useParams, useRouter } from "next/navigation";

import { Button, Card, Eyebrow, CaptureOSLogo, Input, Textarea } from "@/components/captureos";
import { ApiError, apiDownload, apiFetch, errorMessage, pollWorkflowRun } from "@/lib/api";
import { captureosFontVars } from "@/lib/captureos-fonts";
import { useAuth } from "@/lib/auth";
import type { CompanyProfile, WorkflowRunCreated } from "@/lib/types";

// Onboarding wizard — the profile capture that seeds the Company Brain before the
// first money scan. Self-themed (it sits outside the `.captureos` workspace layout),
// it mirrors the design's WIZARD + LOADING screens. Flow:
//   business basics → team size → ownership → activities → diagnostics →
//   company-profile doc → (ingest doc → enrich brain → scan) loader → BRAIN REVIEW.
// State lives in one object so Back never loses entered values. Every field is
// skippable (UX invariant): we only ever block on the network, never empty inputs.
//
// WS3 additions layered onto the original 4-step deterministic submit:
//  1. Diagnostic step → high-signal fields (NAICS / who-you-sell-to / funding goals)
//     persisted via PATCH /company-profile as user_provided evidence (wins over inferred).
//  2. `.md` company-profile intake (download template / upload / paste) — UNTRUSTED
//     DATA ingested as a `document` source; the brain reads it only as grounding text.
//  3. Post-scan Brain Review — surfaces the assembled brain (services / NAICS / certs /
//     evidence count) so the owner sees and can correct what was inferred.

// ---- Step model -----------------------------------------------------------

const STEP_TITLES = [
  "Tell us about your business",
  "How big is your team?",
  "Who owns the business?",
  "What does your business actually do?",
  "Sharpen the match",
  "Add a company profile",
] as const;
const LAST_STEP = STEP_TITLES.length - 1;
const STEP_COUNT = STEP_TITLES.length;

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

// Diagnostic step (WS3) — high-signal fields that materially sharpen eligibility
// matching. Persisted after the brain runs via PATCH /company-profile, so each
// answer becomes user_provided evidence that wins over anything the brain inferred.

// "Who do you sell to?" → target_customers. Drives set-aside / contract fit.
const CUSTOMER_OPTIONS: { code: string; label: string; desc: string }[] = [
  { code: "Federal government", label: "Federal agencies", desc: "→ federal contracts & set-asides" },
  { code: "State & local government", label: "State & local government", desc: "→ SLED contracts & grants" },
  { code: "Enterprises", label: "Large enterprises", desc: "→ commercial past-performance" },
  { code: "Small businesses", label: "Small businesses", desc: "→ B2B programs" },
  { code: "Consumers", label: "Consumers (B2C)", desc: "→ consumer-facing grants" },
];

// "What money are you after?" → funding_categories. Steers which programs surface.
const FUNDING_OPTIONS: { code: string; label: string; desc: string }[] = [
  { code: "Government contracts", label: "Government contracts", desc: "→ SAM.gov set-asides & RFPs" },
  { code: "Grants", label: "Grants", desc: "→ Grants.gov + agency grants" },
  { code: "R&D funding", label: "R&D funding", desc: "→ SBIR/STTR + R&D tax credit" },
  { code: "Tax credits", label: "Tax credits", desc: "→ WOTC, §179, energy credits" },
  { code: "Loans", label: "Loans", desc: "→ SBA 7(a) / 504, microloans" },
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
  websiteUrl: string; // optional; enriched via the SSRF-guarded fetcher server-side
  employees: string; // selected label, "" = unset
  revenue: string; // selected label, "" = unset
  ownership: string[]; // selected codes
  activities: string[]; // selected codes
  // Diagnostics → PATCH /company-profile (user_provided, wins over inferred).
  naicsCode: string; // known/suspected NAICS code
  customers: string[]; // target-customer labels
  funding: string[]; // funding-category labels
  // Company-profile doc (untrusted DATA → ingested as a `document` source).
  profileText: string; // pasted or file-loaded markdown
  profileFilename: string; // "" until a file is chosen
};

const INITIAL: WizardState = {
  companyName: "",
  doWhat: "",
  industry: "",
  location: "",
  websiteUrl: "",
  employees: "",
  revenue: "",
  ownership: [],
  activities: [],
  naicsCode: "",
  customers: [],
  funding: [],
  profileText: "",
  profileFilename: "",
};

function toggle(list: string[], code: string): string[] {
  return list.includes(code) ? list.filter((c) => c !== code) : [...list, code];
}

// Build the PATCH /company-profile body from the diagnostic answers. Only includes
// keys the owner actually answered (every field skippable) so we never overwrite an
// inferred value with an empty one. Returns null when nothing was answered.
function diagnosticPatch(data: WizardState): Record<string, unknown> | null {
  const patch: Record<string, unknown> = {};
  const naics = data.naicsCode.trim();
  if (naics) {
    patch.naicsGuesses = [{ code: naics, label: "Owner-provided", confidence: 1 }];
  }
  if (data.customers.length > 0) patch.targetCustomers = data.customers;
  if (data.funding.length > 0) patch.fundingCategories = data.funding;
  return Object.keys(patch).length > 0 ? patch : null;
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
  // Once the enrichment+scan finishes we show the Brain Review instead of jumping
  // straight to Find, so the owner can see (and correct) what was inferred.
  const [brain, setBrain] = useState<CompanyProfile | null>(null);

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

  // Assemble the brain. Every field is skippable, so we only ever block on the
  // network. Ordering matters for correctness:
  //   1. If a company-profile `.md` was provided, ingest it FIRST and wait for it
  //      to finish — so its chunks exist before the enrichment brain gathers sources.
  //   2. POST /onboarding → deterministic profile upsert + enrichment brain + scan
  //      (one polled run). `websiteUrl` routes through the SSRF-guarded fetcher.
  //   3. AFTER the brain has run, PATCH the diagnostic answers so they land as
  //      user_provided evidence that wins over anything the brain inferred.
  //   4. Fetch the assembled profile and show the Brain Review.
  const finish = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      // 1. Ingest the untrusted `.md` profile (data, never instructions) and wait.
      const profileText = data.profileText.trim();
      if (profileText) {
        const { workflowRunId: docRun } = await apiFetch<WorkflowRunCreated>(
          `/orgs/${orgId}/onboarding/profile-doc`,
          {
            method: "POST",
            body: {
              markdown: profileText,
              filename: data.profileFilename || "company-profile.md",
            },
          },
        );
        // Best-effort: if ingest stalls we still proceed to the scan.
        await pollWorkflowRun(orgId, docRun, { maxAttempts: 40 }).catch(() => undefined);
      }

      // 2. Deterministic profile + enrichment brain + program scan (one run).
      const { workflowRunId } = await apiFetch<WorkflowRunCreated>(
        `/orgs/${orgId}/onboarding`,
        {
          method: "POST",
          body: {
            companyName: data.companyName,
            doWhat: data.doWhat,
            industry: data.industry,
            location: data.location,
            websiteUrl: data.websiteUrl.trim() || undefined,
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

      // 3. Persist diagnostics as user_provided overrides (best-effort — never
      //    block the handoff on a correction that failed to save).
      const patch = diagnosticPatch(data);
      if (patch) {
        await apiFetch<CompanyProfile>(`/orgs/${orgId}/company-profile`, {
          method: "PATCH",
          body: patch,
        }).catch(() => undefined);
      }

      // 4. Surface the assembled brain for review/correction.
      const profile = await apiFetch<CompanyProfile>(
        `/orgs/${orgId}/company-profile`,
      ).catch(() => null);
      if (profile) {
        setBrain(profile);
        setSubmitting(false);
      } else {
        // No profile to show (unlikely) — fall through to Find.
        router.push(`/orgs/${orgId}/workspace/find`);
      }
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

  if (brain) {
    return (
      <BrainReview
        orgId={orgId}
        profile={brain}
        onProfile={setBrain}
        onDone={() => router.push(`/orgs/${orgId}/workspace/find`)}
      />
    );
  }

  const isLast = step === LAST_STEP;
  const stepNo = String(STEP_COUNT).padStart(2, "0");

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
          Step {String(step + 1).padStart(2, "0")} — {stepNo} · {STEP_TITLES[step].toUpperCase()}
        </Eyebrow>
        <div style={{ display: "flex", gap: 6, marginBottom: 26 }}>
          {Array.from({ length: STEP_COUNT }, (_, i) => i).map((i) => (
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
          {step === 4 && <StepDiagnostics data={data} set={set} />}
          {step === 5 && <StepProfileDoc orgId={orgId} data={data} set={set} />}
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
              Build my brain <span style={{ fontSize: 16 }}>→</span>
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

      <label style={{ ...FIELD_LABEL, marginTop: 20 }}>Website · optional</label>
      <Input
        type="url"
        inputMode="url"
        value={data.websiteUrl}
        onChange={(e) => set("websiteUrl", e.target.value)}
        placeholder="https://acmerobotics.com"
      />
      <p style={{ margin: "7px 0 0", fontSize: 12, color: "var(--gr-muted-3)", lineHeight: 1.5 }}>
        We read your public homepage to enrich the brain — nothing is posted anywhere.
      </p>
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

// ---- Step 4: diagnostics (high-signal fields → PATCH) ---------------------

// These sharpen eligibility matching. Answers are saved after the brain runs as
// user_provided evidence (confidence 1.0) that wins over inferred values. Every
// field is skippable — the whole step can be blown past.
function StepDiagnostics({
  data,
  set,
}: {
  data: WizardState;
  set: <K extends keyof WizardState>(key: K, value: WizardState[K]) => void;
}) {
  return (
    <div className="gr-animate-rise">
      <StepHeading>Sharpen the match</StepHeading>
      <StepIntro>
        A few precise answers make the difference between a rough guess and a real match. All
        optional — the brain will infer anything you leave blank.
      </StepIntro>

      <label style={FIELD_LABEL}>NAICS code · optional</label>
      <Input
        value={data.naicsCode}
        onChange={(e) => set("naicsCode", e.target.value)}
        placeholder="e.g. 541512"
        inputMode="numeric"
        style={{ marginBottom: 6 }}
      />
      <p style={{ margin: "0 0 22px", fontSize: 12, color: "var(--gr-muted-3)", lineHeight: 1.5 }}>
        Your primary NAICS drives size standards and set-aside eligibility. Don&apos;t know it? Skip
        it — we&apos;ll guess from what you do.
      </p>

      <label style={{ ...FIELD_LABEL, marginBottom: 11 }}>Who do you sell to?</label>
      <div style={{ display: "flex", flexDirection: "column", gap: 9, marginBottom: 24 }}>
        {CUSTOMER_OPTIONS.map((o) => (
          <CheckRow
            key={o.code}
            label={o.label}
            desc={o.desc}
            checked={data.customers.includes(o.code)}
            onToggle={() => set("customers", toggle(data.customers, o.code))}
          />
        ))}
      </div>

      <label style={{ ...FIELD_LABEL, marginBottom: 11 }}>What kind of money are you after?</label>
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        {FUNDING_OPTIONS.map((o) => (
          <CheckRow
            key={o.code}
            label={o.label}
            desc={o.desc}
            checked={data.funding.includes(o.code)}
            onToggle={() => set("funding", toggle(data.funding, o.code))}
          />
        ))}
      </div>
    </div>
  );
}

// ---- Step 5: company-profile `.md` intake ---------------------------------

// Download a standardized template, fill it (e.g. via ChatGPT/Claude), then upload
// or paste it back. The text is UNTRUSTED DATA: server-side it is ingested as a
// `document` source and only ever reaches the brain as grounding text, never as
// instructions. Optional — an owner can finish without touching this.
function StepProfileDoc({
  orgId,
  data,
  set,
}: {
  orgId: string;
  data: WizardState;
  set: <K extends keyof WizardState>(key: K, value: WizardState[K]) => void;
}) {
  const [downloading, setDownloading] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  const download = useCallback(async () => {
    setDownloading(true);
    setDocError(null);
    try {
      await apiDownload(`/orgs/${orgId}/onboarding/profile-template`, "GET");
    } catch (err) {
      setDocError(errorMessage(err, "Couldn't download the template. Please try again."));
    } finally {
      setDownloading(false);
    }
  }, [orgId]);

  const onFile = useCallback(
    (file: File | null) => {
      setDocError(null);
      if (!file) return;
      if (file.size > 100_000) {
        setDocError("That file is too large — keep the profile under 100 KB of text.");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        set("profileText", typeof reader.result === "string" ? reader.result : "");
        set("profileFilename", file.name);
      };
      reader.onerror = () => setDocError("Couldn't read that file. Try pasting the text instead.");
      reader.readAsText(file);
    },
    [set],
  );

  const chars = data.profileText.trim().length;

  return (
    <div className="gr-animate-rise">
      <StepHeading>Add a company profile</StepHeading>
      <StepIntro>
        Have a company one-pager? Download our template, fill it out (ChatGPT or Claude can help),
        then upload or paste it. We read it as background — never as instructions. Totally optional.
      </StepIntro>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 22 }}>
        <button
          type="button"
          onClick={download}
          disabled={downloading}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "11px 16px",
            borderRadius: 9,
            fontSize: 13.5,
            fontWeight: 600,
            fontFamily: "var(--gr-font-sans)",
            cursor: downloading ? "default" : "pointer",
            background: "var(--gr-input)",
            border: "1px solid var(--gr-border-input)",
            color: "#C9BEA4",
            opacity: downloading ? 0.6 : 1,
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" />
          </svg>
          {downloading ? "Preparing…" : "Download template"}
        </button>

        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "11px 16px",
            borderRadius: 9,
            fontSize: 13.5,
            fontWeight: 600,
            fontFamily: "var(--gr-font-sans)",
            cursor: "pointer",
            background: "var(--gr-input)",
            border: "1px solid var(--gr-border-input)",
            color: "#C9BEA4",
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 21h16M12 3v12m0-12L8 7m4-4 4 4" />
          </svg>
          Upload .md file
          <input
            type="file"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            style={{ display: "none" }}
          />
        </label>
      </div>

      <label style={FIELD_LABEL}>…or paste your profile</label>
      <Textarea
        value={data.profileText}
        onChange={(e) => {
          set("profileText", e.target.value);
          if (data.profileFilename) set("profileFilename", "");
        }}
        rows={8}
        placeholder={"# Company Profile\n\nPaste the filled-in template (or any company summary) here."}
        maxLength={100_000}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          marginTop: 7,
          fontSize: 12,
          color: "var(--gr-muted-3)",
        }}
      >
        <span>
          {data.profileFilename
            ? `Loaded ${data.profileFilename}`
            : chars > 0
              ? `${chars.toLocaleString()} characters ready`
              : "Untrusted text is read as data, never executed."}
        </span>
        {chars > 0 && (
          <button
            type="button"
            onClick={() => {
              set("profileText", "");
              set("profileFilename", "");
            }}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              cursor: "pointer",
              color: "var(--gr-muted)",
              fontSize: 12,
              fontFamily: "var(--gr-font-sans)",
            }}
          >
            Clear
          </button>
        )}
      </div>

      {docError && (
        <p style={{ marginTop: 12, marginBottom: 0, color: "#F0A593", fontSize: 13, lineHeight: 1.5 }}>
          {docError}
        </p>
      )}
    </div>
  );
}

// ---- Brain review (post-scan) ---------------------------------------------

// After the enrichment + scan finishes we surface the assembled Company Brain so the
// owner can SEE what was inferred and CORRECT it before landing on Find. Corrections
// PATCH the profile (persisted as user_provided evidence that wins over inferred).
function BrainReview({
  orgId,
  profile,
  onProfile,
  onDone,
}: {
  orgId: string;
  profile: CompanyProfile;
  onProfile: (p: CompanyProfile) => void;
  onDone: () => void;
}) {
  const [industry, setIndustry] = useState(profile.industry ?? "");
  const [description, setDescription] = useState(profile.description ?? "");
  const [capability, setCapability] = useState(profile.capabilityStatement ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty =
    industry !== (profile.industry ?? "") ||
    description !== (profile.description ?? "") ||
    capability !== (profile.capabilityStatement ?? "");

  const save = useCallback(async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const body: Record<string, unknown> = {};
      if (industry !== (profile.industry ?? "")) body.industry = industry.trim() || null;
      if (description !== (profile.description ?? "")) body.description = description.trim() || null;
      if (capability !== (profile.capabilityStatement ?? ""))
        body.capabilityStatement = capability.trim() || null;
      const updated = await apiFetch<CompanyProfile>(`/orgs/${orgId}/company-profile`, {
        method: "PATCH",
        body,
      });
      onProfile(updated);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save your corrections. Please try again."));
    } finally {
      setSaving(false);
    }
  }, [orgId, industry, description, capability, profile, onProfile]);

  const services = profile.services ?? [];
  const naics = profile.naicsGuesses ?? [];
  const certs = profile.certifications ?? [];
  const funding = profile.fundingCategories ?? [];
  const customers = profile.targetCustomers ?? [];

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
      <div style={{ width: "100%", maxWidth: 640 }}>
        <div style={{ display: "flex", justifyContent: "center", gap: 11, marginBottom: 30 }}>
          <CaptureOSLogo markSize={30} wordmarkSize={20} />
        </div>

        <Eyebrow color="var(--gr-muted-2)" style={{ letterSpacing: ".14em", marginBottom: 10 }}>
          Your company brain
        </Eyebrow>
        <StepHeading>Here&apos;s what we assembled</StepHeading>
        <StepIntro>
          We built this from your answers{profile.websiteUrl ? ", your website," : ""} and any
          profile you shared — each fact is backed by a source. Correct anything that looks off;
          your edits always win over our guesses.
        </StepIntro>

        <Card tone="money" padding={22} style={{ marginBottom: 18 }}>
          <div style={{ display: "flex", gap: 22, flexWrap: "wrap" }}>
            <StatBlock value={String(profile.evidenceCount)} label="Sourced facts" />
            <StatBlock value={String(services.length)} label="Services" />
            <StatBlock value={String(naics.length)} label="NAICS codes" />
            <StatBlock value={String(certs.length)} label="Certifications" />
          </div>
        </Card>

        <Card padding={26} style={{ marginBottom: 18 }}>
          <SectionLabel>What you do</SectionLabel>
          {services.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 6 }}>
              {services.map((s, i) => (
                <div key={i} style={{ fontSize: 14, color: "var(--gr-text)", lineHeight: 1.5 }}>
                  <span style={{ fontWeight: 700 }}>{s.name}</span>
                  {s.description ? (
                    <span style={{ color: "var(--gr-muted)" }}> — {s.description}</span>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyNote>No services inferred yet — add a website or profile to enrich this.</EmptyNote>
          )}

          {naics.length > 0 && (
            <>
              <SectionLabel style={{ marginTop: 20 }}>NAICS guesses</SectionLabel>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {naics.map((n, i) => (
                  <Pill key={i}>
                    {n.code}
                    {n.label ? ` · ${n.label}` : ""}
                  </Pill>
                ))}
              </div>
            </>
          )}

          {certs.length > 0 && (
            <>
              <SectionLabel style={{ marginTop: 20 }}>Certifications</SectionLabel>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {certs.map((c, i) => (
                  <Pill key={i}>
                    {c.name}
                    {c.status ? ` · ${c.status}` : ""}
                  </Pill>
                ))}
              </div>
            </>
          )}

          {(funding.length > 0 || customers.length > 0) && (
            <>
              <SectionLabel style={{ marginTop: 20 }}>Match signals</SectionLabel>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {funding.map((f, i) => (
                  <Pill key={`f${i}`}>{f}</Pill>
                ))}
                {customers.map((c, i) => (
                  <Pill key={`c${i}`}>{c}</Pill>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card padding={26} style={{ marginBottom: 18 }}>
          <SectionLabel>Correct the details</SectionLabel>
          <label style={FIELD_LABEL}>Industry</label>
          <Input
            value={industry}
            onChange={(e) => {
              setIndustry(e.target.value);
              setSaved(false);
            }}
            placeholder="e.g. Health tech"
            style={{ marginBottom: 18 }}
          />
          <label style={FIELD_LABEL}>What you do</label>
          <Textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setSaved(false);
            }}
            rows={3}
            placeholder="A sentence or two describing your business."
            style={{ marginBottom: 18 }}
          />
          <label style={FIELD_LABEL}>Capability statement · optional</label>
          <Textarea
            value={capability}
            onChange={(e) => {
              setCapability(e.target.value);
              setSaved(false);
            }}
            rows={3}
            placeholder="Your positioning for buyers and agencies."
          />
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 16 }}>
            <Button variant="secondary" onClick={save} disabled={saving || !dirty}>
              {saving ? "Saving…" : "Save corrections"}
            </Button>
            {saved && !dirty && (
              <span style={{ fontSize: 13, color: "var(--gr-green-bright)", fontWeight: 600 }}>
                Saved — your edits win over our guesses.
              </span>
            )}
          </div>
          {error && (
            <p style={{ marginTop: 12, marginBottom: 0, color: "#F0A593", fontSize: 13 }}>{error}</p>
          )}
        </Card>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button onClick={onDone}>
            See my money <span style={{ fontSize: 16 }}>→</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--gr-font-serif)", fontSize: 30, fontWeight: 400, color: "#eaf7ee" }}>
        {value}
      </div>
      <div
        style={{
          fontFamily: "var(--gr-font-mono)",
          fontSize: 10.5,
          fontWeight: 600,
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: "rgba(234,247,238,.66)",
          marginTop: 2,
        }}
      >
        {label}
      </div>
    </div>
  );
}

function SectionLabel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        fontFamily: "var(--gr-font-mono)",
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: ".1em",
        textTransform: "uppercase",
        color: "var(--gr-muted-2)",
        marginBottom: 10,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "6px 11px",
        borderRadius: 999,
        fontSize: 12.5,
        fontWeight: 600,
        background: "rgba(46,158,102,.12)",
        border: "1px solid rgba(116,216,165,.3)",
        color: "var(--gr-text)",
      }}
    >
      {children}
    </span>
  );
}

function EmptyNote({ children }: { children: ReactNode }) {
  return <p style={{ margin: 0, fontSize: 13.5, color: "var(--gr-muted-3)", lineHeight: 1.5 }}>{children}</p>;
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

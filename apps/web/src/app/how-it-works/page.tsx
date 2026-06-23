"use client";

import { useState } from "react";
import Link from "next/link";

import { useAuth } from "@/lib/auth";

// Public introductory / "how it works" page for Handled. Self-contained: it
// reuses the app's neutral Tailwind design language, useAuth for CTA targeting,
// and React state for the interactive step-through, hover states, and expandable
// category cards — no new dependencies.

type Step = {
  id: string;
  kicker: string;
  title: string;
  blurb: string;
  detail: string;
  bullets: string[];
};

const STEPS: Step[] = [
  {
    id: "brain",
    kicker: "Step 1",
    title: "Build the Company Brain",
    blurb: "A sourced profile of who you are and what you do.",
    detail:
      "Paste your website, upload capability docs, or describe your business. Handled drafts a capability statement, guesses NAICS codes, and tracks certifications — with every fact tied back to the document or page it came from.",
    bullets: [
      "Capability statement + service catalog",
      "NAICS code guesses with confidence",
      "Certifications, past performance, and missing-info checklist",
    ],
  },
  {
    id: "scan",
    kicker: "Step 2",
    title: "Scan opportunities",
    blurb: "Find and rank what you should actually pursue.",
    detail:
      "Scan live government data — contracts via SAM.gov and USAspending, grants via Grants.gov. Each opportunity gets an AI fit score against your Company Brain and a bid/no-bid (or apply/no-apply) hint, with the reasons for and against laid out.",
    bullets: [
      "Contracts from SAM.gov & USAspending",
      "Research grants from Grants.gov",
      "Fit score + bid/no-bid with rationale",
    ],
  },
  {
    id: "filing",
    kicker: "Step 3",
    title: "Start a filing",
    blurb: "Extract requirements, match evidence, get a recommendation.",
    detail:
      "Turn an opportunity into a filing. Handled extracts the requirements from the solicitation, matches them against your evidence in a live compliance matrix, and produces a pursue / no-pursue recommendation — which a human reviews and approves before anything moves forward.",
    bullets: [
      "Automatic requirement extraction",
      "Live compliance matrix (met / gap / unknown)",
      "AI pursue/no-pursue recommendation, human-approved",
    ],
  },
  {
    id: "package",
    kicker: "Step 4",
    title: "Build & export the package",
    blurb: "A fully-cited package you approve before it leaves.",
    detail:
      "Assemble a complete, citation-backed package. Once a human approves it at the gate, export to Markdown, PDF, or DOCX. Handled never auto-submits — the file is yours to file.",
    bullets: [
      "Every claim cited to its source",
      "Approval gate before any export",
      "Export to MD, PDF, or DOCX — nothing auto-submits",
    ],
  },
];

type Category = {
  id: string;
  name: string;
  tag: string;
  tone: "emerald" | "sky" | "violet" | "amber";
  summary: string;
  points: string[];
};

const CATEGORIES: Category[] = [
  {
    id: "contracts",
    name: "Government Contracts",
    tag: "bid / no-bid",
    tone: "emerald",
    summary:
      "Discover federal contract opportunities from SAM.gov and USAspending, scored against your Company Brain.",
    points: [
      "AI fit scoring with reasons for and against",
      "Requirement extraction into a compliance matrix",
      "Pursue/no-pursue recommendation behind an approval gate",
    ],
  },
  {
    id: "grants",
    name: "Research Grants",
    tag: "apply / no-apply",
    tone: "sky",
    summary:
      "Surface research and program grants from Grants.gov and qualify them before you spend effort writing.",
    points: [
      "Apply/no-apply signal with eligibility rationale",
      "Narrative requirements and report obligations extracted",
      "Cited package assembly for the submission",
    ],
  },
  {
    id: "compliance",
    name: "Compliance Documents",
    tag: "matrix builder",
    tone: "violet",
    summary:
      "Point Handled at any solicitation or regulation and get a structured compliance matrix you can work through.",
    points: [
      "Requirements extracted from any source document",
      "Evidence matched line-by-line (met / gap / unknown)",
      "Gaps flagged before you commit",
    ],
  },
  {
    id: "renewals",
    name: "Renewals & Deadlines",
    tag: "stay current",
    tone: "amber",
    summary:
      "Track the recurring obligations that quietly lapse — registrations, recertifications, and report due dates.",
    points: [
      "SAM.gov registration renewals",
      "WOSB / 8(a) / HUBZone recertifications",
      "Grant reports and deadlines with reminders",
    ],
  },
];

const WHY = [
  {
    title: "Sourced & cited",
    body: "Every claim is tied to its source document or page. No hallucinated facts — if it isn't backed by evidence, it's flagged.",
  },
  {
    title: "Human-in-the-loop",
    body: "AI recommends; people decide. Approval gates sit in front of every recommendation and every export. Nothing auto-submits.",
  },
  {
    title: "Always current",
    body: "Grounded in live government data — SAM.gov, USAspending, and Grants.gov — so opportunities reflect what's actually open.",
  },
];

const TONE_STYLES: Record<Category["tone"], { chip: string; ring: string; dot: string }> = {
  emerald: {
    chip: "bg-emerald-100 text-emerald-800",
    ring: "hover:border-emerald-400",
    dot: "bg-emerald-500",
  },
  sky: {
    chip: "bg-sky-100 text-sky-800",
    ring: "hover:border-sky-400",
    dot: "bg-sky-500",
  },
  violet: {
    chip: "bg-violet-100 text-violet-800",
    ring: "hover:border-violet-400",
    dot: "bg-violet-500",
  },
  amber: {
    chip: "bg-amber-100 text-amber-800",
    ring: "hover:border-amber-400",
    dot: "bg-amber-500",
  },
};

export default function HowItWorksPage() {
  const { isAuthenticated } = useAuth();
  const ctaHref = isAuthenticated ? "/dashboard" : "/login";
  const ctaLabel = isAuthenticated ? "Open your dashboard" : "Log in or create an account";

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="flex items-center justify-between">
        <span className="text-lg font-semibold tracking-tight">Handled</span>
        <Link
          href={ctaHref}
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-100"
        >
          {isAuthenticated ? "Dashboard" : "Sign in"}
        </Link>
      </header>

      {/* Hero */}
      <section className="mt-14 max-w-3xl">
        <span className="inline-flex items-center gap-2 rounded-full bg-neutral-900 px-3 py-1 text-xs font-medium text-white">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          AI compliance & capture platform
        </span>
        <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          Find, qualify, and prepare government bids — without the busywork.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-neutral-600">
          Handled helps small businesses discover government contract bids, research grants, and
          compliance paperwork — qualifying each one with AI, citing every claim to its source, and
          keeping a human approval gate in front of anything that leaves. Nothing auto-submits.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href={ctaHref}
            className="rounded-lg bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-700"
          >
            {ctaLabel} →
          </Link>
          <a
            href="#how"
            className="rounded-lg border border-neutral-300 px-5 py-2.5 text-sm font-medium transition hover:bg-neutral-100"
          >
            See how it works
          </a>
        </div>
      </section>

      <HowItWorksFlow />

      <CategoriesGrid />

      <WhyUs />

      {/* Final CTA */}
      <section className="mt-20 overflow-hidden rounded-2xl bg-neutral-900 px-8 py-12 text-center text-white">
        <h2 className="text-2xl font-semibold tracking-tight">Ready to capture your next opportunity?</h2>
        <p className="mx-auto mt-3 max-w-xl text-neutral-300">
          Build your Company Brain, scan live opportunities, and assemble a cited, approval-gated
          package — all in one place.
        </p>
        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          <Link
            href={ctaHref}
            className="rounded-lg bg-white px-5 py-2.5 text-sm font-medium text-neutral-900 transition hover:bg-neutral-200"
          >
            {ctaLabel} →
          </Link>
          {!isAuthenticated && (
            <Link
              href="/login"
              className="rounded-lg border border-neutral-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-800"
            >
              Sign in
            </Link>
          )}
        </div>
      </section>

      <footer className="mt-12 text-center text-xs text-neutral-400">
        Handled · AI-assisted, human-approved. The platform prepares packages — it never submits them.
      </footer>
    </main>
  );
}

function HowItWorksFlow() {
  const [active, setActive] = useState(0);
  const step = STEPS[active];

  return (
    <section id="how" className="mt-20 scroll-mt-8">
      <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">How it works</h2>
      <p className="mt-1 text-xl font-semibold tracking-tight">
        From a cold start to a filing-ready package, in four steps.
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Step rail */}
        <ol className="space-y-2">
          {STEPS.map((s, i) => {
            const isActive = i === active;
            return (
              <li key={s.id}>
                <button
                  onClick={() => setActive(i)}
                  aria-current={isActive ? "step" : undefined}
                  className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition ${
                    isActive
                      ? "border-neutral-900 bg-neutral-900 text-white"
                      : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-400 hover:bg-neutral-50"
                  }`}
                >
                  <span
                    className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold transition ${
                      isActive ? "bg-white text-neutral-900" : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    {i + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{s.title}</span>
                    <span
                      className={`block truncate text-xs ${
                        isActive ? "text-neutral-300" : "text-neutral-500"
                      }`}
                    >
                      {s.blurb}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        {/* Active step detail — keyed so it re-mounts and fades in on change */}
        <div
          key={step.id}
          className="animate-in rounded-2xl border border-neutral-200 bg-white p-7"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
            {step.kicker}
          </p>
          <h3 className="mt-1 text-2xl font-semibold tracking-tight">{step.title}</h3>
          <p className="mt-3 leading-relaxed text-neutral-600">{step.detail}</p>

          <ul className="mt-5 space-y-2">
            {step.bullets.map((b) => (
              <li key={b} className="flex items-start gap-2.5 text-sm text-neutral-800">
                <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-700">
                  ✓
                </span>
                {b}
              </li>
            ))}
          </ul>

          <div className="mt-7 flex items-center justify-between border-t border-neutral-100 pt-4">
            <button
              onClick={() => setActive((a) => Math.max(0, a - 1))}
              disabled={active === 0}
              className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium transition hover:bg-neutral-100 disabled:opacity-40"
            >
              ← Back
            </button>
            <div className="flex gap-1.5" aria-hidden>
              {STEPS.map((s, i) => (
                <span
                  key={s.id}
                  className={`h-1.5 rounded-full transition-all ${
                    i === active ? "w-6 bg-neutral-900" : "w-1.5 bg-neutral-300"
                  }`}
                />
              ))}
            </div>
            <button
              onClick={() => setActive((a) => Math.min(STEPS.length - 1, a + 1))}
              disabled={active === STEPS.length - 1}
              className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function CategoriesGrid() {
  const [open, setOpen] = useState<string | null>(CATEGORIES[0].id);

  return (
    <section className="mt-20">
      <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
        What we cover
      </h2>
      <p className="mt-1 text-xl font-semibold tracking-tight">
        Four categories, one workflow.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {CATEGORIES.map((cat) => {
          const tone = TONE_STYLES[cat.tone];
          const isOpen = open === cat.id;
          return (
            <div
              key={cat.id}
              className={`rounded-2xl border bg-white p-6 transition ${tone.ring} ${
                isOpen ? "border-neutral-300 shadow-sm" : "border-neutral-200"
              }`}
            >
              <button
                onClick={() => setOpen(isOpen ? null : cat.id)}
                aria-expanded={isOpen}
                className="flex w-full items-start justify-between gap-3 text-left"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
                    <h3 className="text-base font-semibold tracking-tight">{cat.name}</h3>
                  </div>
                  <span
                    className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${tone.chip}`}
                  >
                    {cat.tag}
                  </span>
                </div>
                <span
                  className={`mt-1 text-neutral-400 transition-transform ${
                    isOpen ? "rotate-180" : ""
                  }`}
                  aria-hidden
                >
                  ▾
                </span>
              </button>

              <p className="mt-3 text-sm leading-relaxed text-neutral-600">{cat.summary}</p>

              {/* Expandable detail — grid-rows trick animates height without JS measurement */}
              <div
                className={`grid transition-all duration-300 ${
                  isOpen ? "mt-4 grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                }`}
              >
                <ul className="overflow-hidden space-y-2">
                  {cat.points.map((p) => (
                    <li key={p} className="flex items-start gap-2 text-sm text-neutral-800">
                      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone.dot}`} />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function WhyUs() {
  return (
    <section className="mt-20">
      <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">Why Handled</h2>
      <p className="mt-1 text-xl font-semibold tracking-tight">
        Built so you can trust what it gives you.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {WHY.map((w) => (
          <div
            key={w.title}
            className="group rounded-2xl border border-neutral-200 bg-white p-6 transition hover:-translate-y-0.5 hover:border-neutral-400 hover:shadow-sm"
          >
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-neutral-900 text-white transition group-hover:bg-emerald-600">
              <span className="h-2 w-2 rounded-full bg-emerald-400 transition group-hover:bg-white" />
            </div>
            <h3 className="mt-4 text-base font-semibold tracking-tight">{w.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-neutral-600">{w.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

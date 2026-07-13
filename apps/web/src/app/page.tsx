"use client";

import { useEffect, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button, Card, CaptureOSLogo, Eyebrow } from "@/components/captureos";
import { captureosFontVars } from "@/lib/captureos-fonts";
import { useAuth } from "@/lib/auth";

// Public landing page for CaptureOS. Unauthenticated visitors land here (not a
// redirect to /login); authenticated visitors are bounced straight to /dashboard.
// Built in the same dark-green system as the onboarding wizard and workspace
// (`.captureos` tokens, Instrument Serif / Hanken Grotesk / JetBrains Mono),
// using the SAME primitives (Card, Button, Eyebrow, CaptureOSLogo) so nothing
// here is a one-off. The hero re-enacts the real Find-tab mechanic — describe
// your business, watch it scan federal/state sources, watch a dollar figure
// rise — as an honest, labeled example rather than a generic headline+CTA.

// ---- Hero demo content ------------------------------------------------------

const EXAMPLES = [
  { biz: "a 12-person robotics startup in Ohio", amount: "$184,000", programs: 6, contracts: 2 },
  { biz: "a woman-owned marketing agency in Austin", amount: "$92,500", programs: 4, contracts: 1 },
  { biz: "an R&D software team building climate tech", amount: "$310,000", programs: 8, contracts: 3 },
] as const;

const SCAN_SOURCES = ["SAM.gov", "Grants.gov", "SBA", "IRS", "SBIR.gov"] as const;

// ---- How it works ------------------------------------------------------------

const STEPS = [
  {
    n: "01",
    title: "Build the Company Brain",
    body: "Paste your website or describe your business. CaptureOS drafts a capability statement, guesses NAICS codes, and tracks certifications — every fact tied to its source.",
  },
  {
    n: "02",
    title: "Scan opportunities",
    body: "Live federal and state data — contracts via SAM.gov and USAspending, grants via Grants.gov. Every match gets a fit score and a bid/no-bid rationale.",
  },
  {
    n: "03",
    title: "Start a filing",
    body: "CaptureOS extracts requirements, builds a live compliance matrix against your evidence, and drafts a pursue/no-pursue recommendation — a human approves it.",
  },
  {
    n: "04",
    title: "Build & export the package",
    body: "A fully-cited package, assembled only after approval. Export to Markdown, PDF, or DOCX. CaptureOS never auto-submits — the file is yours to file.",
  },
] as const;

// ---- Categories ---------------------------------------------------------------
// Two families, not four arbitrary hues: green = money you can go get, amber =
// the compliance/admin work that protects it. The color carries meaning.

const CATEGORIES = [
  {
    name: "Government Contracts",
    tag: "bid / no-bid",
    tone: "green" as const,
    summary: "Federal contract opportunities from SAM.gov and USAspending, scored against your Company Brain.",
  },
  {
    name: "Research Grants",
    tag: "apply / no-apply",
    tone: "green" as const,
    summary: "Research and program grants from Grants.gov, qualified before you spend effort writing.",
  },
  {
    name: "Compliance Documents",
    tag: "matrix builder",
    tone: "amber" as const,
    summary: "Point CaptureOS at any solicitation or regulation and get a structured compliance matrix.",
  },
  {
    name: "Renewals & Deadlines",
    tag: "stay current",
    tone: "amber" as const,
    summary: "The recurring obligations that quietly lapse — registrations, recertifications, report due dates.",
  },
] as const;

const WHY = [
  {
    title: "Sourced & cited",
    body: "Every claim ties back to its source document or page. If it isn't backed by evidence, it's flagged, not guessed.",
  },
  {
    title: "Human-in-the-loop",
    body: "AI recommends; people decide. Approval gates sit in front of every recommendation and every export. Nothing auto-submits.",
  },
  {
    title: "Always current",
    body: "Grounded in live government data — SAM.gov, USAspending, Grants.gov — so what you see is what's actually open.",
  },
] as const;

export default function LandingPage() {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && isAuthenticated) router.replace("/dashboard");
  }, [loading, isAuthenticated, router]);

  if (loading || isAuthenticated) {
    return (
      <div
        className={`captureos ${captureosFontVars}`}
        style={{ display: "grid", placeItems: "center", minHeight: "100vh", color: "var(--gr-muted)" }}
      >
        Loading CaptureOS…
      </div>
    );
  }

  return (
    <div className={`captureos ${captureosFontVars}`} style={{ minHeight: "100vh" }}>
      <PublicNav />
      <Hero />
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "0 28px" }}>
        <HowItWorks />
        <Categories />
        <Why />
      </div>
      <FinalCta />
      <Footer />
    </div>
  );
}

// ---- Nav ----------------------------------------------------------------------

function PublicNav() {
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        background: "rgba(22,19,14,.88)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        borderBottom: "1px solid var(--gr-border-soft)",
      }}
    >
      <style>{`
        .gr-public-nav-links { display: none; }
        @media (min-width: 640px) {
          .gr-public-nav-links { display: flex !important; }
        }
      `}</style>
      <div
        style={{
          maxWidth: 1160,
          margin: "0 auto",
          padding: "0 20px",
          height: 64,
          display: "flex",
          alignItems: "center",
          gap: 20,
        }}
      >
        <CaptureOSLogo markSize={26} wordmarkSize={17} />
        <nav className="gr-public-nav-links" style={{ gap: 22, marginLeft: 8 }}>
          <NavLink href="#how">How it works</NavLink>
          <NavLink href="#categories">What we cover</NavLink>
        </nav>
        <div style={{ flex: 1 }} />
        <Link
          href="/login"
          className="gr-public-nav-links"
          style={{ alignItems: "center", fontSize: 14, fontWeight: 600, color: "var(--gr-muted-2)", textDecoration: "none" }}
        >
          Sign in
        </Link>
        <Link href="/login" style={{ textDecoration: "none" }}>
          <Button variant="primary" style={{ padding: "10px 16px", fontSize: 13.5 }}>
            Get started
          </Button>
        </Link>
      </div>
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={href}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontSize: 14,
        fontWeight: 600,
        textDecoration: "none",
        color: hover ? "var(--gr-heading)" : "var(--gr-muted-2)",
        transition: "color .12s ease",
      }}
    >
      {children}
    </a>
  );
}

// ---- Hero -----------------------------------------------------------------

function Hero() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");

  return (
    <section
      className="gr-weave"
      style={{
        borderBottom: "1px solid var(--gr-border-soft)",
        padding: "64px 28px 76px",
      }}
    >
      <div
        style={{
          maxWidth: 1160,
          margin: "0 auto",
          display: "grid",
          gap: 52,
          gridTemplateColumns: "1fr",
        }}
      >
        <style>{`
          @media (min-width: 940px) {
            .gr-hero-grid { grid-template-columns: 1fr 440px !important; align-items: start; }
          }
        `}</style>
        <div className="gr-hero-grid" style={{ display: "grid", gap: 52, gridTemplateColumns: "1fr" }}>
          <div style={{ maxWidth: 560 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                fontFamily: "var(--gr-font-mono)",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: ".14em",
                textTransform: "uppercase",
                color: "var(--gr-green-bright)",
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "var(--gr-green-bright-2)",
                  boxShadow: "0 0 8px var(--gr-green-bright-2)",
                }}
              />
              AI compliance &amp; capture platform
            </span>

            <h1
              style={{
                fontFamily: "var(--gr-font-serif)",
                fontSize: "clamp(38px, 5.2vw, 58px)",
                fontWeight: 400,
                lineHeight: 1.03,
                letterSpacing: "-.01em",
                margin: "18px 0 16px",
                color: "var(--gr-heading)",
              }}
            >
              Find the government money you already qualify for.
            </h1>
            <p style={{ margin: "0 0 28px", color: "var(--gr-muted)", fontSize: 17, lineHeight: 1.55 }}>
              CaptureOS discovers contracts, grants, and tax credits you&apos;re eligible for, cites
              every claim to its source, and keeps a human approval gate in front of anything that
              leaves. Nothing auto-submits.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                router.push("/login");
              }}
              style={{ display: "flex", gap: 10, flexWrap: "wrap", maxWidth: 480 }}
            >
              <input
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe what your business does…"
                style={{
                  flex: 1,
                  minWidth: 220,
                  border: "1px solid var(--gr-border-input)",
                  borderRadius: 10,
                  outline: "none",
                  fontSize: 15,
                  padding: "14px 16px",
                  color: "var(--gr-text)",
                  background: "var(--gr-input)",
                  fontFamily: "var(--gr-font-sans)",
                }}
              />
              <Button type="submit" variant="primary" style={{ whiteSpace: "nowrap" }}>
                Find my money <span style={{ fontSize: 16 }}>→</span>
              </Button>
            </form>
            <p style={{ margin: "10px 0 0", fontSize: 12.5, color: "var(--gr-muted-3)" }}>
              No credit card. Takes about two minutes.
            </p>
          </div>

          <ExampleDemo />
        </div>
      </div>
    </section>
  );
}

// prefers-reduced-motion via useSyncExternalStore — matches the codebase's
// existing pattern for reading external browser state (see lib/auth.tsx's
// useHydrated), and keeps SSR/client output consistent without a set-state-
// in-effect footgun.
function subscribeReducedMotion(callback: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}
function getReducedMotionSnapshot() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function getReducedMotionServerSnapshot() {
  return false;
}
function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    getReducedMotionServerSnapshot,
  );
}

// Cycles through a few example businesses: types the description, ticks off
// the sources it checks, then reveals a dollar figure — the same rise-in the
// Find tab uses. Clearly labeled as an example (not live output of the input
// above), respects prefers-reduced-motion by holding on one static state.
function ExampleDemo() {
  const reducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (reducedMotion) return;
    // Deferred via setTimeout(0) rather than called synchronously in the
    // effect body, so each cycle's "reset" doesn't trip set-state-in-effect.
    const resetTimer = setTimeout(() => setRevealed(false), 0);
    const revealTimer = setTimeout(() => setRevealed(true), 1300);
    const advanceTimer = setTimeout(() => setIndex((i) => (i + 1) % EXAMPLES.length), 4400);
    return () => {
      clearTimeout(resetTimer);
      clearTimeout(revealTimer);
      clearTimeout(advanceTimer);
    };
  }, [index, reducedMotion]);

  const ex = EXAMPLES[index];
  const shown = reducedMotion || revealed;

  return (
    <Card tone="money" padding={26} style={{ position: "relative", overflow: "hidden" }}>
      <Eyebrow color="var(--gr-money-text)" style={{ marginBottom: 14 }}>
        Example match
      </Eyebrow>
      <div key={index} className={reducedMotion ? undefined : "gr-animate-rise"}>
        <p style={{ margin: "0 0 16px", fontSize: 14.5, color: "#eaf7ee", lineHeight: 1.5 }}>
          &ldquo;{ex.biz}&rdquo;
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 7, marginBottom: 18 }}>
          {SCAN_SOURCES.map((s, i) => (
            <div
              key={s}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                animation: reducedMotion ? undefined : "gr-rise .4s cubic-bezier(.2,.7,.2,1) both",
                animationDelay: reducedMotion ? undefined : `${i * 110}ms`,
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#9fd8b5" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6 L9 17 L4 12" />
              </svg>
              <span style={{ fontFamily: "var(--gr-font-mono)", fontSize: 12, color: "rgba(234,247,238,.72)" }}>
                {s}
              </span>
            </div>
          ))}
        </div>

        <div style={{ minHeight: 74, opacity: shown ? 1 : 0, transition: "opacity .3s ease" }}>
          <div
            style={{
              fontFamily: "var(--gr-font-serif)",
              fontSize: 46,
              fontWeight: 400,
              lineHeight: 1,
              color: "#ffffff",
            }}
          >
            ≈ {ex.amount}
          </div>
          <div style={{ marginTop: 8, fontSize: 13, color: "#9fd8b5" }}>
            across {ex.programs} programs and {ex.contracts} open contract{ex.contracts === 1 ? "" : "s"}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ---- How it works -----------------------------------------------------------

function HowItWorks() {
  return (
    <section id="how" style={{ scrollMarginTop: 84, paddingTop: 84 }}>
      <SectionKicker>How it works</SectionKicker>
      <SectionTitle>From a cold start to a filing-ready package, in four steps.</SectionTitle>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", marginTop: 30 }}>
        {STEPS.map((s) => (
          <Card key={s.n} padding={24}>
            <div
              style={{
                fontFamily: "var(--gr-font-mono)",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: ".08em",
                color: "var(--gr-green-bright)",
                marginBottom: 12,
              }}
            >
              {s.n}
            </div>
            <h3
              style={{
                fontFamily: "var(--gr-font-serif)",
                fontSize: 21,
                fontWeight: 400,
                color: "var(--gr-heading)",
                margin: "0 0 8px",
              }}
            >
              {s.title}
            </h3>
            <p style={{ margin: 0, fontSize: 13.5, color: "var(--gr-muted)", lineHeight: 1.55 }}>{s.body}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

// ---- Categories ---------------------------------------------------------------

const TONE_DOT: Record<"green" | "amber", string> = {
  green: "var(--gr-green-bright)",
  amber: "var(--gr-amber)",
};
const TONE_CHIP: Record<"green" | "amber", CSSProperties> = {
  green: { background: "rgba(46,158,102,.16)", color: "#74d89b" },
  amber: { background: "rgba(242,182,110,.14)", color: "var(--gr-amber)" },
};

function Categories() {
  return (
    <section id="categories" style={{ scrollMarginTop: 84, paddingTop: 84 }}>
      <SectionKicker>What we cover</SectionKicker>
      <SectionTitle>Two jobs: find the money, keep the paperwork clean.</SectionTitle>

      <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", marginTop: 30 }}>
        {CATEGORIES.map((c) => (
          <Card key={c.name} padding={22}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: TONE_DOT[c.tone] }} />
              <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--gr-text-strong)", margin: 0 }}>
                {c.name}
              </h3>
            </div>
            <span
              style={{
                display: "inline-block",
                borderRadius: 6,
                padding: "3px 9px",
                fontSize: 11,
                fontWeight: 700,
                marginBottom: 12,
                ...TONE_CHIP[c.tone],
              }}
            >
              {c.tag}
            </span>
            <p style={{ margin: 0, fontSize: 13.5, color: "var(--gr-muted)", lineHeight: 1.55 }}>{c.summary}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

// ---- Why ----------------------------------------------------------------------

function Why() {
  return (
    <section style={{ paddingTop: 84, paddingBottom: 84 }}>
      <SectionKicker>Why CaptureOS</SectionKicker>
      <SectionTitle>Built so you can trust what it gives you.</SectionTitle>

      <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", marginTop: 30 }}>
        {WHY.map((w) => (
          <Card key={w.title} padding={22}>
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: 8,
                background: "var(--gr-green)",
                display: "grid",
                placeItems: "center",
                marginBottom: 14,
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--gr-on-green)" }} />
            </div>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: "var(--gr-text-strong)", margin: "0 0 6px" }}>
              {w.title}
            </h3>
            <p style={{ margin: 0, fontSize: 13.5, color: "var(--gr-muted)", lineHeight: 1.55 }}>{w.body}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

// ---- Final CTA + footer --------------------------------------------------------

function FinalCta() {
  return (
    <section style={{ maxWidth: 1080, margin: "0 auto", padding: "0 28px 84px" }}>
      <Card
        tone="money"
        padding="52px 40px"
        style={{ textAlign: "center", backgroundImage: "var(--gr-money-weave, none)" }}
      >
        <h2
          style={{
            fontFamily: "var(--gr-font-serif)",
            fontSize: 32,
            fontWeight: 400,
            color: "#ffffff",
            margin: "0 0 10px",
          }}
        >
          Ready to capture your next opportunity?
        </h2>
        <p style={{ margin: "0 auto 26px", maxWidth: 480, color: "#cfe9db", fontSize: 15, lineHeight: 1.55 }}>
          Build your Company Brain, scan live opportunities, and assemble a cited, approval-gated
          package — all in one place.
        </p>
        <Link href="/login" style={{ textDecoration: "none" }}>
          <Button variant="primary">
            Get started <span style={{ fontSize: 16 }}>→</span>
          </Button>
        </Link>
      </Card>
    </section>
  );
}

function Footer() {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--gr-border-soft)",
        padding: "24px 28px",
        textAlign: "center",
        fontSize: 12,
        color: "var(--gr-muted-3)",
      }}
    >
      CaptureOS · AI-assisted, human-approved. The platform prepares packages — it never submits them.
    </footer>
  );
}

// ---- Shared section headings ---------------------------------------------------

function SectionKicker({ children }: { children: ReactNode }) {
  return <Eyebrow style={{ marginBottom: 8 }}>{children}</Eyebrow>;
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: "var(--gr-font-serif)",
        fontSize: 28,
        fontWeight: 400,
        color: "var(--gr-heading)",
        margin: 0,
        maxWidth: 560,
      }}
    >
      {children}
    </h2>
  );
}

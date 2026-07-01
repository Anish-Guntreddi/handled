"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { EligibilityBadge } from "@/components/captureos";
import { ApiError, apiFetch, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CompanyProfile, CopilotAnswer } from "@/lib/types";

// Copilot — the cited Q&A surface over the Company Brain. A message is sent to
// POST /copilot/ask; the response carries an answer, optional program cards, the
// citations behind it, and an optional next-step note. The Company Brain card
// surfaces "what I know about you" as chips derived from the company profile, and
// a `?q=` deep-link (sent from the Find screen) prefills + auto-sends on mount.

// ---------------------------------------------------------------------------
// Chat thread model. Each user turn produces an assistant turn that moves through
// loading → answered | errored. We keep the original question on the assistant
// turn so an error can be retried without re-typing.
type Status = "loading" | "answered" | "errored";

type UserMessage = { id: string; role: "user"; text: string };

type AssistantMessage = {
  id: string;
  role: "assistant";
  question: string;
  status: Status;
  answer?: CopilotAnswer;
  error?: string;
};

type ChatMessage = UserMessage | AssistantMessage;

const SUGGESTED = [
  "What funding do I qualify for?",
  "Do I qualify for SBIR?",
  "What set-asides can I use?",
  "How do I claim the R&D tax credit?",
];

let messageSeq = 0;
function nextId(prefix: string): string {
  messageSeq += 1;
  return `${prefix}-${messageSeq}`;
}

// ---------------------------------------------------------------------------
// Company Brain chips. Derive a short, ordered set of facts from the profile:
// industry, location, certifications, then a couple of services / NAICS. Each
// fact carries a stable key so React can list them without index churn.
type BrainFact = { key: string; label: string };

function brainFacts(profile: CompanyProfile): BrainFact[] {
  const facts: BrainFact[] = [];
  if (profile.industry) facts.push({ key: "industry", label: profile.industry });
  if (profile.location) facts.push({ key: "location", label: profile.location });

  for (const cert of profile.certifications ?? []) {
    if (cert?.name) facts.push({ key: `cert-${cert.name}`, label: cert.name });
  }
  for (const svc of (profile.services ?? []).slice(0, 2)) {
    if (svc?.name) facts.push({ key: `svc-${svc.name}`, label: svc.name });
  }
  for (const naics of (profile.naicsGuesses ?? []).slice(0, 1)) {
    if (naics?.code) {
      facts.push({
        key: `naics-${naics.code}`,
        label: naics.label ? `${naics.code} · ${naics.label}` : naics.code,
      });
    }
  }
  return facts;
}

// ---------------------------------------------------------------------------
// Icons mirror the design's COPILOT glyphs (brain kicker, CaptureOS avatar check,
// per-card spark, arrows).
function BrainIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-green-bright)"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2a4 4 0 0 0-4 4 4 4 0 0 0-2 7 4 4 0 0 0 2 7 4 4 0 0 0 8 0 4 4 0 0 0 2-7 4 4 0 0 0-2-7 4 4 0 0 0-4-4Z" />
    </svg>
  );
}

function CheckMark({ size = 11 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-on-green)"
      strokeWidth={2.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 17 L11 10 L15 14 L21 7" />
    </svg>
  );
}

function CardSpark() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--gr-green-bright)"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l2.5 2.5M16.5 16.5 19 19M19 5l-2.5 2.5M7.5 16.5 5 19" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
function CopilotInner() {
  const { orgId } = useParams<{ orgId: string }>();
  const { isAuthenticated } = useAuth();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [inputFocused, setInputFocused] = useState(false);

  // Live program count powers the subtext ("search N programs live").
  const discoveryQuery = useQuery({
    queryKey: ["discovery", orgId],
    queryFn: () => apiFetch<{ scanCount: number }>(`/orgs/${orgId}/discovery`),
    enabled: isAuthenticated,
  });
  const scanCount = discoveryQuery.data?.scanCount ?? 0;

  // Company Brain. A 404 means the profile hasn't been built — we show a single
  // onboarding chip instead of the derived facts.
  const profileQuery = useQuery({
    queryKey: ["company-profile", orgId],
    queryFn: () => apiFetch<CompanyProfile>(`/orgs/${orgId}/company-profile`),
    enabled: isAuthenticated,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
  const profileMissing =
    profileQuery.isError &&
    profileQuery.error instanceof ApiError &&
    profileQuery.error.status === 404;
  const facts = useMemo(
    () => (profileQuery.data ? brainFacts(profileQuery.data) : []),
    [profileQuery.data],
  );

  // Fire the request for one assistant turn and resolve it in place. We resolve
  // by id so out-of-order responses (or a retry) only touch their own message.
  const resolveTurn = useCallback(
    async (assistantId: string, question: string) => {
      try {
        const answer = await apiFetch<CopilotAnswer>(`/orgs/${orgId}/copilot/ask`, {
          method: "POST",
          body: { question },
        });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.role === "assistant"
              ? { ...m, status: "answered", answer }
              : m,
          ),
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.role === "assistant"
              ? { ...m, status: "errored", error: errorMessage(err, "Couldn't reach CaptureOS.") }
              : m,
          ),
        );
      }
    },
    [orgId],
  );

  // Send a question: append the user turn + a loading assistant turn, then ask.
  const send = useCallback(
    (raw: string) => {
      const question = raw.trim();
      if (!question) return;

      const assistantId = nextId("a");
      setMessages((prev) => [
        ...prev,
        { id: nextId("u"), role: "user", text: question },
        { id: assistantId, role: "assistant", question, status: "loading" },
      ]);
      void resolveTurn(assistantId, question);
    },
    [resolveTurn],
  );

  // Retry an errored turn: flip it back to loading and re-ask its question.
  const retry = useCallback(
    (assistantId: string, question: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.role === "assistant"
            ? { ...m, status: "loading", error: undefined }
            : m,
        ),
      );
      void resolveTurn(assistantId, question);
    },
    [resolveTurn],
  );

  // Deep-link: read `?q=` once on mount. If present, auto-send it; otherwise the
  // composer stays empty. A ref guards against the effect firing twice (e.g.
  // React 18 strict-mode double-invoke) and re-asking the question.
  const autoSent = useRef(false);
  useEffect(() => {
    if (autoSent.current || !isAuthenticated) return;
    const q = searchParams.get("q")?.trim();
    if (q) {
      autoSent.current = true;
      send(q);
    }
  }, [searchParams, isAuthenticated, send]);

  function submit() {
    const q = input.trim();
    if (!q) return;
    setInput("");
    send(q);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <div style={{ paddingTop: 44, maxWidth: 780 }}>
      {/* ===== Header ===== */}
      <div
        style={{
          fontFamily: "var(--gr-font-mono)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: ".12em",
          textTransform: "uppercase",
          color: "var(--gr-muted-2)",
          marginBottom: 8,
        }}
      >
        Your copilot
      </div>
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
        Ask CaptureOS anything
      </h1>
      <p
        style={{
          margin: "0 0 24px",
          color: "var(--gr-muted)",
          fontSize: 16,
          lineHeight: 1.5,
          maxWidth: 620,
        }}
      >
        I read your Company Brain and search {scanCount.toLocaleString()} programs live. Ask about
        money, eligibility, or what to do next — every answer is cited, and anything you tell me
        makes future matches sharper.
      </p>

      {/* ===== Company Brain card ===== */}
      <div
        style={{
          background: "var(--gr-surface)",
          border: "1px solid var(--gr-border)",
          borderRadius: "var(--gr-radius-card)",
          padding: "18px 20px",
          marginBottom: 26,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontFamily: "var(--gr-font-mono)",
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            color: "var(--gr-green-bright)",
            marginBottom: 13,
          }}
        >
          <BrainIcon />
          Company Brain · what I know about you
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {profileQuery.isLoading ? (
            <BrainChipsSkeleton />
          ) : profileMissing || facts.length === 0 ? (
            <Link
              href={`/orgs/${orgId}/onboarding`}
              style={{
                textDecoration: "none",
                background: "transparent",
                border: "1px dashed var(--gr-border-strong)",
                borderRadius: "var(--gr-radius-chip)",
                padding: "6px 11px",
                fontSize: 12.5,
                fontWeight: 600,
                color: "var(--gr-green-bright)",
              }}
            >
              Tell me about your business →
            </Link>
          ) : (
            <>
              {facts.map((f) => (
                <span
                  key={f.key}
                  style={{
                    background: "var(--gr-hover)",
                    border: "1px solid var(--gr-border-input)",
                    borderRadius: "var(--gr-radius-chip)",
                    padding: "6px 11px",
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: "#c9bea4",
                  }}
                >
                  {f.label}
                </span>
              ))}
              <Link
                href={`/orgs/${orgId}/onboarding`}
                style={{
                  textDecoration: "none",
                  background: "transparent",
                  border: "1px dashed var(--gr-border-strong)",
                  borderRadius: "var(--gr-radius-chip)",
                  padding: "6px 11px",
                  fontSize: 12.5,
                  fontWeight: 600,
                  color: "var(--gr-muted-3)",
                }}
              >
                + Add a detail
              </Link>
            </>
          )}
        </div>
      </div>

      {/* ===== Chat thread ===== */}
      {hasMessages && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 22,
            marginBottom: 26,
          }}
        >
          {messages.map((m) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.text} />
            ) : (
              <AssistantTurn key={m.id} message={m} onRetry={retry} />
            ),
          )}
        </div>
      )}

      {/* ===== Suggested questions (empty thread only) ===== */}
      {!hasMessages && (
        <div style={{ marginBottom: 22 }}>
          <div
            style={{
              fontFamily: "var(--gr-font-mono)",
              fontSize: 10.5,
              fontWeight: 600,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: "var(--gr-muted-2)",
              marginBottom: 11,
            }}
          >
            Try asking
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            {SUGGESTED.map((label) => (
              <SuggestedButton key={label} label={label} onClick={() => send(label)} />
            ))}
          </div>
        </div>
      )}

      {/* ===== Composer ===== */}
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          position: "sticky",
          bottom: 18,
          background: "var(--gr-bg)",
          paddingTop: 6,
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setInputFocused(true)}
          onBlur={() => setInputFocused(false)}
          placeholder="Ask about your business, eligibility, or next steps…"
          aria-label="Ask CaptureOS a question"
          style={{
            flex: 1,
            minWidth: 240,
            border: `1px solid ${inputFocused ? "var(--gr-green)" : "var(--gr-border-input)"}`,
            borderRadius: 11,
            outline: "none",
            fontFamily: "var(--gr-font-sans)",
            fontSize: 15,
            padding: "15px 17px",
            color: "var(--gr-text)",
            background: "var(--gr-surface)",
            boxShadow: inputFocused
              ? "0 0 0 3px rgba(46,158,102,.22)"
              : "0 8px 24px -10px rgba(0,0,0,.6)",
          }}
        />
        <ComposerButton onClick={submit} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
      <div
        style={{
          maxWidth: 560,
          background: "var(--gr-green)",
          color: "var(--gr-on-green)",
          borderRadius: "12px 12px 4px 12px",
          padding: "11px 15px",
          fontSize: 14.5,
          fontWeight: 600,
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
        }}
      >
        {text}
      </div>
    </div>
  );
}

function AssistantTurn({
  message,
  onRetry,
}: {
  message: AssistantMessage;
  onRetry: (id: string, question: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 10 }}>
      {/* Avatar + label */}
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 5,
            background: "var(--gr-green)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CheckMark />
        </div>
        <span
          style={{
            fontFamily: "var(--gr-font-mono)",
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: "var(--gr-muted-2)",
          }}
        >
          CaptureOS
        </span>
      </div>

      {message.status === "loading" ? (
        <ThinkingBubble />
      ) : message.status === "errored" ? (
        <ErrorBubble
          error={message.error ?? "Something went wrong."}
          onRetry={() => onRetry(message.id, message.question)}
        />
      ) : (
        <AnswerBody answer={message.answer!} />
      )}
    </div>
  );
}

function AnswerBody({ answer }: { answer: CopilotAnswer }) {
  return (
    <>
      {answer.answer && (
        <div
          style={{
            maxWidth: 620,
            color: "var(--gr-text)",
            fontSize: 15,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {answer.answer}
        </div>
      )}

      {/* Cards — compact program rows */}
      {answer.cards.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", maxWidth: 580 }}>
          {answer.cards.map((c, i) => (
            <div
              key={`${c.name}-${i}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 13,
                padding: "13px 15px",
                border: "1px solid var(--gr-border)",
                borderRadius: 10,
                background: "var(--gr-input)",
              }}
            >
              <span style={{ display: "flex", color: "var(--gr-green-bright)" }}>
                <CardSpark />
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--gr-text-strong)" }}>
                  {c.name}
                </div>
                {c.citation && (
                  <div
                    style={{
                      fontFamily: "var(--gr-font-mono)",
                      fontSize: 11,
                      color: "var(--gr-muted-4)",
                      marginTop: 2,
                    }}
                  >
                    {c.citation}
                  </div>
                )}
              </div>
              <div style={{ textAlign: "right" }}>
                {c.benefit && (
                  <div
                    style={{
                      fontFamily: "var(--gr-font-serif)",
                      fontSize: 20,
                      color: "var(--gr-green-bright)",
                      lineHeight: 1,
                    }}
                  >
                    {c.benefit}
                  </div>
                )}
                <div style={{ marginTop: 5 }}>
                  <EligibilityBadge status={c.eligibility} label={c.eligibilityLabel} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Citations — source rows, snippet expands on click */}
      {answer.citations.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 620 }}>
          {answer.citations.map((cite, i) => (
            <CitationRow key={`${cite.label}-${cite.locator}-${i}`} citation={cite} />
          ))}
        </div>
      )}

      {/* Note — green ✦ chip */}
      {answer.note && (
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            background: "rgba(46,158,102,.1)",
            border: "1px solid rgba(116,216,155,.22)",
            borderRadius: "var(--gr-radius-chip)",
            padding: "6px 12px",
            fontSize: 12.5,
            color: "#86d9a8",
            fontWeight: 600,
          }}
        >
          <span style={{ fontFamily: "var(--gr-font-serif)", fontSize: 15 }}>✦</span> {answer.note}
        </div>
      )}
    </>
  );
}

// A citation: "Source: {label} · {locator}". Clicking toggles the snippet, which
// the design only hints at on hover — an explicit toggle is more accessible.
function CitationRow({
  citation,
}: {
  citation: { label: string; locator: string; snippet: string };
}) {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(false);
  const hasSnippet = Boolean(citation.snippet);

  return (
    <div>
      <button
        type="button"
        onClick={() => hasSnippet && setOpen((v) => !v)}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          background: "none",
          border: "none",
          padding: 0,
          textAlign: "left",
          cursor: hasSnippet ? "pointer" : "default",
          fontFamily: "var(--gr-font-mono)",
          fontSize: 11.5,
          color: hover && hasSnippet ? "var(--gr-muted-2)" : "var(--gr-muted-4)",
        }}
      >
        <LinkIcon />
        Source: {citation.label}
        {citation.locator ? ` · ${citation.locator}` : ""}
        {hasSnippet && (
          <span style={{ color: "var(--gr-green-bright)" }}>{open ? "−" : "+"}</span>
        )}
      </button>
      {open && hasSnippet && (
        <div
          style={{
            marginTop: 6,
            marginLeft: 19,
            padding: "9px 12px",
            background: "var(--gr-input)",
            border: "1px solid var(--gr-border-soft)",
            borderRadius: 8,
            fontSize: 12.5,
            lineHeight: 1.55,
            color: "var(--gr-muted)",
            fontStyle: "italic",
          }}
        >
          “{citation.snippet}”
        </div>
      )}
    </div>
  );
}

function LinkIcon() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#5c5444"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.5 1.5" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.5-1.5" />
    </svg>
  );
}

function ThinkingBubble() {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 9,
        color: "var(--gr-muted-3)",
        fontSize: 14.5,
      }}
    >
      <span
        className="gr-animate-spin"
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          border: "2px solid var(--gr-border-strong)",
          borderTopColor: "var(--gr-green-bright)",
          display: "inline-block",
        }}
      />
      Reading your Company Brain & scanning programs…
    </div>
  );
}

function ErrorBubble({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div
      style={{
        maxWidth: 580,
        background: "rgba(232,154,138,.08)",
        border: "1px solid rgba(232,154,138,.28)",
        borderRadius: "12px 12px 12px 4px",
        padding: "13px 15px",
        fontSize: 14,
        lineHeight: 1.5,
        color: "#e89a8a",
      }}
    >
      <div style={{ marginBottom: 8 }}>{error}</div>
      <button
        type="button"
        onClick={onRetry}
        style={{
          background: "none",
          border: "1px solid rgba(232,154,138,.4)",
          borderRadius: 7,
          padding: "5px 12px",
          fontSize: 12.5,
          fontWeight: 700,
          color: "#e89a8a",
          cursor: "pointer",
        }}
      >
        Try again →
      </button>
    </div>
  );
}

function SuggestedButton({ label, onClick }: { label: string; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  const style: CSSProperties = {
    textAlign: "left",
    background: hover ? "var(--gr-hover)" : "var(--gr-surface)",
    border: `1px solid ${hover ? "var(--gr-green)" : "var(--gr-border)"}`,
    borderRadius: 10,
    padding: "14px 16px",
    fontSize: 14.5,
    fontWeight: 600,
    color: "#e6dcc8",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 11,
  };
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={style}
    >
      <span style={{ fontFamily: "var(--gr-font-serif)", fontSize: 18, color: "var(--gr-green-bright)" }}>
        →
      </span>
      {label}
    </button>
  );
}

function ComposerButton({ onClick }: { onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "15px 22px",
        borderRadius: 11,
        background: hover ? "var(--gr-green-hover)" : "var(--gr-green)",
        color: "var(--gr-on-green)",
        border: "none",
        fontSize: 14.5,
        fontWeight: 700,
        cursor: "pointer",
        whiteSpace: "nowrap",
      }}
    >
      Ask CaptureOS →
    </button>
  );
}

function BrainChipsSkeleton() {
  return (
    <>
      {[88, 64, 120].map((w) => (
        <div
          key={w}
          style={{
            width: w,
            height: 29,
            borderRadius: "var(--gr-radius-chip)",
            background:
              "linear-gradient(90deg, var(--gr-hover) 25%, var(--gr-surface-raised) 50%, var(--gr-hover) 75%)",
            backgroundSize: "200% 100%",
            animation: "gr-shimmer 1.4s ease-in-out infinite",
          }}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// The page wraps the surface in a Suspense boundary because `useSearchParams`
// opts the subtree into client-side rendering during prerender (Next.js
// requirement). Auth-gating + the 1160px column come from the workspace shell.
export default function CopilotPage() {
  return (
    <Suspense fallback={null}>
      <CopilotInner />
    </Suspense>
  );
}

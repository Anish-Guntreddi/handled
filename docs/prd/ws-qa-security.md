# WS-QA — Cross-Cutting QA & Security Gate

> **Not a build workflow — a gate run via `/loop` after every workflow (A–E).**

## Context
The user's execution model is: `ultracode` builds a phase, then `/loop` runs `/qa` + security review after each phase. This already maps onto an existing convention — `make gate` in the `Makefile`. WS-QA formalizes that convention into a consistent, enforced gate, hardest on money movement (WS1/WS4) and tenant isolation.

## The gate (already partly codified)
```
make check         # ruff check (incl. S/bandit lints) + mypy captureos + pytest -q
make codex-review  # independent Codex review of the working tree
make gate          # check, then run: /security-audit  /security-review  /qa
make web-check     # pnpm lint + pnpm typecheck  (frontend phases)
```

## The gate runs in TWO layers (locked)

### Layer 1 — inside each workflow (automated, during the build)
The ultracode orchestration itself bakes in **adversarial verification**: subagent stages that try to *refute* the phase's changes on the high-risk surfaces (Stripe webhooks, org isolation, citation correctness, corpus dedupe). Independent skeptics are prompted to disprove each correctness-critical finding; anything that does not survive a majority of refuters is dropped **before** the phase reaches the human gate. This is self-checking *within* the phase.

### Layer 2 — after each phase, in the main loop (the `/loop` gate)
Run over the phase's diff, in order:
1. **Automated checks** — `make check` (ruff incl. `S`/bandit + mypy + `pytest -q`) and/or `make web-check` (pnpm lint + typecheck). Must be green.
2. **Codex validator** — `make codex-review` (or the codex agent): an **independent** implementation/diagnosis pass. Per the codex-validator preference, correctness-critical work is validated by Codex before it is accepted.
3. **Security skills** — `/security-audit` + `/security-review` over the diff.
4. **QA skill** — `/qa`.

`make gate` stitches Layer 2 together. If any skill is not wired as invocable in this environment, fall back to `make codex-review` + the security MCPs (Semgrep is authenticated).

## Series vs parallel + final integration
- The gate runs **per phase, regardless** of series/parallel execution — each phase is gated on its own diff before it is "done."
- **Parallel** Phase-2 workflows (Money / Knowledge / Onboarding) each gate on their own branch; if two touch a shared file, isolate them (git worktrees). On localhost, prefer **series** for the first run so gates are unambiguous, then parallelize once boundaries are trusted.
- After **all** phases merge: one **final integration gate** — full `make check` + a cross-phase `/security-review` — because branches that pass individually can still interact badly together.

## Per-workflow emphasis (where the gate bites hardest)
| Workflow | Highest-risk surface | Must-verify |
|---|---|---|
| A · Foundation | provider seam, rename | no secret logged; seam invariant; `test_provider_routing` |
| **B · Money (WS1+WS4)** | **Issuing + subscription webhooks** | **signature verification, idempotency, fail-closed, no self-granted entitlements** |
| C · Knowledge | discovery agent, fetched URLs | SSRF guard, dedupe correctness, no tenant data in corpus |
| D · Onboarding/Brain | uploaded `.md`, website fetch | untrusted-input/prompt-injection safety, SSRF, org isolation |
| E · Custom RAG | re-rank/threshold | never emit unsupported citations; isolation across modes |

## Standing invariants (every phase asserts)
- **Org isolation** — corpus tables carry no `org_id`; tenant queries org-scoped (RLS or repository layer). `test_org_scoping.py` extended as new tables land.
- **Never auto-submit** — CaptureOS prepares; a human files.
- **Every claim cited** — answers/recommendations grounded in retrieved sources; citation invariant enforced in code (`services/packaging.py`), not just prompt.
- **Secrets server-side only** — no key/token in logs, responses, or client.
- **No silent truncation** — any bounded coverage (top-N, sampling, no-retry) is logged.

## Supply chain
- `pyproject.toml` `exclude-newer` cooldown stays current; security MCPs (Semgrep authenticated) run on dependency-touching phases.

## Acceptance criteria
- `make gate` runs clean at the end of every workflow before it's considered done.
- Correctness-critical diffs carry an adversarial-verification record.
- New tables/routes ship with org-scoping tests; new webhooks ship with signature + idempotency tests.

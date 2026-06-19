Reading additional input from stdin...
OpenAI Codex v0.130.0
--------
workdir: /Users/anishguntreddi/Documents/hackathon
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 019ee13a-0d93-7561-bbe1-a65d1bc22ed1
--------
user
You are an independent senior reviewer validating Phase M0 (foundation) of CaptureOS,
an AI filing OS. Authoritative spec: captureos-engineering-prd.md. Code under apps/api
(FastAPI + SQLAlchemy 2 async + Alembic + pgvector) and apps/web (Next.js).

Find REAL, concrete defects only. For each: file:line, severity (critical/high/medium/low),
why it's wrong, and the fix. Prioritize, in order:
1. CON-5 multi-tenant isolation: can any route read/write another org's data? Check
   captureos/core/deps.py (require_org/_load_org_context), api/orgs.py, api/auth.py.
2. AuthN/AuthZ: JWT issuance/verification (core/security.py), Argon2 usage, token type
   confusion (access vs refresh), missing role checks on mutating routes.
3. Injection / unsafe SQL / path traversal (providers/storage.py LocalStorage keys).
4. Async/session correctness: session lifecycle (db/session.py), commit/rollback, the
   audit sink opening its own session, any cross-loop engine misuse.
5. Migration correctness vs models (migrations/versions/*initial*): missing columns,
   wrong FK ondelete, the pgvector/HNSW index, extension bootstrap.
6. Provider abstraction soundness and secrets handling (CON-4: no secret to client).
7. Any silent failure, swallowed exception, or footgun.

Be skeptical and specific. If something is actually fine, don't pad. End with a short
VERDICT: is M0 sound to build on? List the must-fix items.
codex
Reviewing `captureos-engineering-prd.md` and the targeted backend/frontend areas first, then I’ll trace the auth, org scoping, storage, session, and migration paths to isolate concrete defects only.
exec
/bin/zsh -lc pwd in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
/Users/anishguntreddi/Documents/hackathon

exec
/bin/zsh -lc 'rg --files' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
docker-compose.yml
.env.example
captureos-engineering-prd.md
README.md
Makefile
infra/db/init/01-extensions.sql
apps/api/Dockerfile
apps/api/alembic.ini
apps/api/uv.lock
apps/api/captureos/main.py
apps/api/tests/test_health.py
apps/api/tests/test_org_scoping.py
apps/api/tests/__init__.py
apps/api/tests/test_auth.py
apps/api/tests/conftest.py
apps/api/pyproject.toml
apps/api/captureos/__init__.py
apps/api/migrations/versions/f28c812fca98_initial_schema.py
apps/api/migrations/env.py
apps/api/migrations/script.py.mako
apps/api/captureos/config.py
apps/api/captureos/logging.py
apps/api/README.md
apps/api/captureos/worker/main.py
apps/api/captureos/worker/__init__.py
apps/api/captureos/providers/base.py
apps/api/captureos/providers/storage.py
apps/api/captureos/providers/secrets.py
apps/api/captureos/providers/embeddings.py
apps/api/captureos/providers/llm.py
apps/api/captureos/providers/__init__.py
apps/api/captureos/providers/audit.py
apps/api/captureos/providers/docparse.py
apps/api/captureos/providers/queue.py
apps/api/captureos/core/errors.py
apps/api/captureos/core/__init__.py
apps/api/captureos/core/security.py
apps/api/captureos/core/deps.py
apps/api/captureos/api/router.py
apps/api/captureos/api/__init__.py
apps/api/captureos/api/orgs.py
apps/api/captureos/api/health.py
apps/api/captureos/api/auth.py
apps/api/captureos/auth/base.py
apps/api/captureos/auth/firebase.py
apps/api/captureos/auth/__init__.py
apps/api/captureos/auth/local.py
apps/api/captureos/audit/__init__.py
apps/api/captureos/audit/service.py
apps/api/captureos/db/base.py
apps/api/captureos/db/migrate.py
apps/api/captureos/db/__init__.py
apps/api/captureos/db/session.py
apps/api/captureos/scripts/seed.py
apps/api/captureos/scripts/__init__.py
apps/api/captureos/schemas/common.py
apps/api/captureos/schemas/__init__.py
apps/api/captureos/schemas/org.py
apps/api/captureos/schemas/auth.py
apps/api/captureos/models/evidence.py
apps/api/captureos/models/workflow.py
apps/api/captureos/models/filings.py
apps/api/captureos/models/opportunities.py
apps/api/captureos/models/__init__.py
apps/api/captureos/models/documents.py
apps/api/captureos/models/billing.py
apps/api/captureos/models/audit.py
apps/api/captureos/models/company.py
apps/api/captureos/models/org.py
apps/api/captureos/models/enums.py
apps/web/src/lib/providers.tsx
apps/web/src/lib/tokenStore.ts
apps/web/src/lib/types.ts
apps/web/src/lib/api.ts
apps/web/src/lib/auth.tsx
apps/web/src/app/login/page.tsx
apps/web/src/app/globals.css
apps/web/src/app/page.tsx
apps/web/src/app/layout.tsx
apps/web/src/app/dashboard/page.tsx
apps/web/src/app/favicon.ico
apps/web/pnpm-workspace.yaml
apps/web/next.config.ts
apps/web/CLAUDE.md
apps/web/eslint.config.mjs
apps/web/AGENTS.md
apps/web/tsconfig.json
apps/web/package.json
apps/web/public/window.svg
apps/web/public/globe.svg
apps/web/public/next.svg
apps/web/public/vercel.svg
apps/web/public/file.svg
apps/web/README.md
apps/web/postcss.config.mjs
apps/web/pnpm-lock.yaml

codex
The codebase is small enough to inspect directly. I’m pulling the spec clauses and the exact backend files named in your scope before checking tests for blind spots.
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/core/deps.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/api/orgs.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Organization routes. ``GET /orgs/{org_id}`` is the M0 org-scoping acceptance test."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.core.deps import CurrentUser, OrgOwner, OrgViewer, SessionDep
from captureos.core.errors import ConflictError, NotFoundError
from captureos.models.enums import ActorType, OrgRole
from captureos.models.org import Organization, OrgMember, User
from captureos.schemas.org import InviteMemberRequest, OrgCreate, OrgMemberResponse, OrgResponse

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(body: OrgCreate, user: CurrentUser, session: SessionDep) -> OrgResponse:
    org = Organization(name=body.name, uei=body.uei)
    session.add(org)
    await session.flush()
    session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
    return OrgResponse(
        id=org.id,
        name=org.name,
        uei=org.uei,
        plan=org.plan,
        role=OrgRole.owner.value,
        created_at=org.created_at,
    )


@router.get("", response_model=list[OrgResponse])
async def list_orgs(user: CurrentUser, session: SessionDep) -> list[OrgResponse]:
    result = await session.execute(
        select(Organization, OrgMember.role)
        .join(OrgMember, OrgMember.org_id == Organization.id)
        .where(OrgMember.user_id == user.id)
        .order_by(Organization.created_at)
    )
    return [
        OrgResponse(
            id=org.id,
            name=org.name,
            uei=org.uei,
            plan=org.plan,
            role=role,
            created_at=org.created_at,
        )
        for org, role in result.all()
    ]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(ctx: OrgViewer) -> OrgResponse:
    org = ctx.organization
    return OrgResponse(
        id=org.id,
        name=org.name,
        uei=org.uei,
        plan=org.plan,
        role=ctx.role,
        created_at=org.created_at,
    )


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
async def list_members(ctx: OrgViewer, session: SessionDep) -> list[OrgMemberResponse]:
    result = await session.execute(
        select(User, OrgMember.role)
        .join(OrgMember, OrgMember.user_id == User.id)
        .where(OrgMember.org_id == ctx.org_id)
        .order_by(OrgMember.created_at)
    )
    return [
        OrgMemberResponse(user_id=u.id, email=u.email, full_name=u.full_name, role=role)
        for u, role in result.all()
    ]


@router.post(
    "/{org_id}/members", response_model=OrgMemberResponse, status_code=status.HTTP_201_CREATED
)
async def add_member(
    body: InviteMemberRequest, ctx: OrgOwner, session: SessionDep
) -> OrgMemberResponse:
    role = OrgRole(body.role).value  # validates the role string
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    target = result.scalar_one_or_none()
    if target is None:
        raise NotFoundError("No user with that email exists")
    existing = await session.execute(
        select(OrgMember).where(OrgMember.org_id == ctx.org_id, OrgMember.user_id == target.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("User is already a member of this organization")
    session.add(OrgMember(org_id=ctx.org_id, user_id=target.id, role=role))
    await record_event(
        "org.member_added",
        org_id=ctx.org_id,
        actor=ActorType.user,
        actor_id=str(ctx.user.id),
        payload={"added_user_id": str(target.id), "role": role},
    )
    return OrgMemberResponse(
        user_id=target.id, email=target.email, full_name=target.full_name, role=role
    )

 succeeded in 0ms:
"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from captureos.auth import get_auth_provider
from captureos.core.errors import AuthError, ForbiddenError, NotFoundError
from captureos.db.session import get_session
from captureos.models.enums import OrgRole
from captureos.models.org import Organization, OrgMember, User

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

_ROLE_ORDER = {OrgRole.viewer: 0, OrgRole.editor: 1, OrgRole.owner: 2}


async def get_current_user(session: SessionDep, creds: BearerDep = None) -> User:
    if creds is None or not creds.credentials:
        raise AuthError("Missing or malformed Authorization header")
    principal = await get_auth_provider().verify_token(creds.credentials)

    if principal.is_local:
        try:
            user_id = uuid.UUID(principal.subject)
        except ValueError as exc:
            raise AuthError("Invalid token subject") from exc
        user = await session.get(User, user_id)
    else:
        result = await session.execute(
            select(User).where(User.external_auth_id == principal.subject)
        )
        user = result.scalar_one_or_none()
        if user is None and principal.email:
            user = User(email=principal.email, external_auth_id=principal.subject)
            session.add(user)
            await session.flush()

    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass(slots=True)
class OrgContext:
    user: User
    organization: Organization
    membership: OrgMember

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def org_id(self) -> uuid.UUID:
        return self.organization.id


async def _load_org_context(org_id: uuid.UUID, user: User, session: AsyncSession) -> OrgContext:
    org = await session.get(Organization, org_id)
    # Non-existent OR not-a-member both return 404 to avoid leaking org existence (CON-5).
    if org is None:
        raise NotFoundError("Organization not found")
    result = await session.execute(
        select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Organization not found")
    return OrgContext(user=user, organization=org, membership=membership)


def require_org(
    min_role: OrgRole = OrgRole.viewer,
) -> Callable[..., Awaitable[OrgContext]]:
    """Dependency factory: resolves the org from the path, asserts membership and a
    minimum role, and returns the OrgContext. Use on every org-scoped route."""

    async def dependency(
        user: CurrentUser,
        session: SessionDep,
        org_id: Annotated[uuid.UUID, Path()],
    ) -> OrgContext:
        ctx = await _load_org_context(org_id, user, session)
        if _ROLE_ORDER[OrgRole(ctx.membership.role)] < _ROLE_ORDER[min_role]:
            raise ForbiddenError(f"This action requires '{min_role.value}' role")
        return ctx

    return dependency


# Common pre-bound dependencies.
OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]
OrgOwner = Annotated[OrgContext, Depends(require_org(OrgRole.owner))]

exec
/bin/zsh -lc 'rg -n "CON-4|CON-5|tenant|auth|jwt|refresh|access|pgvector|HNSW|LocalStorage|audit|session|org" captureos-engineering-prd.md' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
18:This is an **engineering** PRD. It specifies *what to build and how it is structured*, with testable requirements, interface contracts, a data model, and delivery milestones. It deliberately does **not** include marketing plans, outreach scripts, or pricing strategy — those become engineering requirements only where they touch the system (billing, usage metering, audit evidence). Where the source brief listed strategy or GTM deliverables, those are out of scope for this document and noted in §16.
34:The central domain object is a **Filing**. Everything the system produces hangs off a Filing: its target opportunity, requirements, eligibility rules, evidence found/missing, generated documents, recommendation, approvals, and full audit trail.
36:The MVP delivers two revenue verticals — **government contracts (GovCon)** and **grants** — across five workflows (Company Brain → Opportunity Scan → Requirement Extraction → Evidence Matching → Package Build), plus an audit/logs surface and billing. Permits/licenses are an explicit future vertical and must not require schema rewrites.
38:**Non-negotiable behaviors:** (1) the system never auto-submits a binding external filing — a human approves first; (2) every claim-bearing output is source-backed; (3) every agent action is logged to an exportable audit trail.
44:Small businesses lose enormous time on the *research-and-preparation* phase of business-critical filings (contracts, grants, permits, certifications, onboarding packets). The work is high-stakes, deadline-driven, and requires synthesizing scattered internal evidence against external requirements. Existing tools solve thin slices (RFP summarizers, grant-writing assistants, checklist apps) but none orchestrate the end-to-end pipeline: *discover → research → extract requirements → gather evidence → check eligibility → recommend → assemble package*, with citations and an audit trail.
54:1. Let an org build a structured **Company Brain** from minimal input (name + website, optionally UEI/docs).
55:2. Discover and rank **GovCon and grant opportunities** the org plausibly qualifies for, with fit scores and source-backed reasoning.
61:8. Record a complete, **exportable audit trail** of every agent run, source checked, Gemini call, and user action.
90:| **Company Brain** | Structured profile of the org (services, NAICS guesses, certifications, past performance, capability statement) derived from website/docs/public sources. Stored in `company_profiles` + `evidence_items`. |
91:| **Evidence Vault** | The org's accumulated `evidence_items` (atomic, sourced facts) reusable across filings. |
92:| **Filing** | The central object. A pursuit of one opportunity of a given `kind`. Aggregates requirements, evidence matches, recommendation, generated docs, approvals, audit. |
96:| **Workflow run** | One execution of a multi-step pipeline for an org/filing; composed of `workflow_steps`, each driving one `agent_run`. |
110:- **FR-CB-6** — The profile must be regenerable/refreshable on demand without destroying user overrides.
125:- **FR-OD-3** — Persist discovered opportunities to `opportunities` with `source` references and a content snapshot (so results are auditable even if the live source changes).
169:- **FR-AP-1** — Before a filing's recommendation is treated as "pursue," it must be explicitly approved by an authorized org user; the approval (who/when/decision) is persisted.
171:- **FR-AP-3** — Approval state is visible in the UI and recorded in the audit trail; rejection routes the filing back to an editable state with the reviewer's notes.
179:- **FR-AU-5** — The audit trail must be **exportable** (CSV/JSON) for external review (hackathon evidence). Authoritative event stream lives in BigQuery; transactional run/step summaries live in Postgres for the UI.
185:- **FR-BL-3** — Record each successful charge with amount, product, org, and timestamp (real revenue + hackathon evidence).
193:- **CON-3** — Every agent action that touches data or an external source is logged to the audit trail.
194:- **CON-4** — Secrets (API keys, provider tokens) live only in Secret Manager and are never sent to the client.
195:- **CON-5** — All data access is org-scoped; one org can never read another org's data.
213:| Orchestration | **Custom workflow engine** (`workflow_runs`/`workflow_steps`) | Simpler, fully observable, maps 1:1 to the audit requirement. | LangGraph (optional, if graph complexity grows) |
214:| Core DB | Cloud SQL **Postgres + pgvector** | The model is highly relational (filing→requirements→matches→evidence); pgvector keeps RAG in the same store. | Firestore + Vertex Vector Search |
219:| Embeddings | Managed text-embedding model (Vertex/Gemini embeddings) | Powers pgvector retrieval. | Confirm exact model at build time |
220:| Secrets | Secret Manager | `CON-4`. | — |
240:      SQL["Cloud SQL Postgres<br/>+ pgvector"]
242:      BQ["BigQuery<br/>(audit/events)"]
302:Postgres is authoritative for transactional/relational data; BigQuery holds the append-only audit event stream; Cloud Storage holds binaries.
331:Conventions: every table has `id uuid pk`, `org_id uuid` (except global `users`), `created_at`, `updated_at`. All non-`users` queries are filtered by `org_id` (`CON-5`).
333:**`organizations`**
340:| plan | text | free / audit / sprint / autopilot |
342:**`users`**, **`org_members`** — standard multi-tenant membership (`org_members(user_id, org_id, role)`), `role ∈ {owner, editor, viewer}`.
348:| org_id | uuid | fk, unique |
363:| org_id | uuid | fk |
379:| embedding | vector(N) | pgvector; N = embedding dim |
385:| org_id | uuid | fk |
389:| snapshot_uri | text null | cached content snapshot (auditability) |
396:| org_id | uuid | fk |
407:| org_id | uuid | fk |
421:| org_id | uuid | fk |
484:| org_id | uuid | fk |
485:| filing_id | uuid null | fk (null for org-level runs like Company Brain) |
523:### 8.4 BigQuery audit stream
525:A single append-only `events` table (partitioned by date) with: `event_id, org_id, filing_id, run_id, step_id, actor (user/agent/system), action, source_url, model, tokens, latency_ms, status, payload (json), occurred_at`. This is the authoritative log for `FR-AU-2/5` and the exportable hackathon evidence; the dashboard reads aggregates from here.
541:Base path `/api/v1`. Auth via Firebase ID token in `Authorization: Bearer`. The backend verifies the token, resolves the user, and enforces `org_id` scoping on every route. Long-running operations return `202` + a `workflow_run_id`.
546:POST /orgs/{orgId}/company-profile:build
550:GET  /orgs/{orgId}/company-profile
553:PATCH /orgs/{orgId}/company-profile
561:POST /orgs/{orgId}/documents:initiate-upload
565:POST /orgs/{orgId}/documents/{id}:ingest    # after upload, or for pasted text
569:GET  /orgs/{orgId}/documents/{id}
576:POST /orgs/{orgId}/opportunity-scans
584:GET  /orgs/{orgId}/opportunities?kind=&minFit=
591:GET /orgs/{orgId}/workflow-runs/{id}
603:POST /orgs/{orgId}/filings
607:GET  /orgs/{orgId}/filings/{id}            # full aggregate
613:POST /orgs/{orgId}/filings/{id}:extract-requirements   → 202 { workflowRunId }
614:POST /orgs/{orgId}/filings/{id}:match-evidence         → 202 { workflowRunId }
615:POST /orgs/{orgId}/filings/{id}:recommend              → 202 { workflowRunId }
616:POST /orgs/{orgId}/filings/{id}:build-package          → 202 { workflowRunId }  # requires recommendation approved (CON-1)
618:POST /orgs/{orgId}/filings/{id}/gaps/{requirementId}:resolve
626:POST /orgs/{orgId}/filings/{id}/approvals
631:### 9.7 Export & audit
634:POST /orgs/{orgId}/filings/{id}/package:export
638:GET  /orgs/{orgId}/audit/events?runId=&from=&to=&format=json|csv
645:POST /orgs/{orgId}/billing/checkout
646:  body: { product: "audit" | "sprint" | "autopilot" }
654:All errors return `{ error: { code, message, details? } }`. Async failures are reflected in the workflow run (`status=failed`, plus a step-level error and an audit event), never as a silent empty result (`FR-RE-2`).
668:| 1 | **Intent Router** | Classify objective (contracts/grants/permits/general) and route. | user objective, org context | `{kind, params}` | Gemini Flash | ambiguous intent | re-prompt once, else ask user |
673:| 6 | **Evidence Acquisition** | Gather supporting evidence (RAG over docs + sources). | requirements, vault | candidate evidence | pgvector + Gemini | no evidence found | mark gap |
713:- **Schema-retry**: if an agent's output fails Pydantic validation, re-prompt up to N=2 times with the validation error appended; on final failure, set step `failed`, run `failed` (or `needs_input` if user-resolvable), and emit an audit event. Never return a silently empty result (`FR-RE-2`).
722:- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
723:- **NFR-2 Security** — secrets only in Secret Manager (`CON-4`); documents encrypted at rest (Cloud Storage default); signed URLs for upload/download; no third-party tokens reach the client.
724:- **NFR-3 Privacy/PII** — treat company docs as sensitive; restrict log payloads (store pointers/summaries, not full PII, in BigQuery where avoidable); support per-org data deletion.
725:- **NFR-4 Observability** — structured JSON logs; the BigQuery audit stream; an in-app logs dashboard (`FR-AU-4`); each agent run records model, tokens, latency.
730:- **NFR-9 Compliance/legal** — `CON-1` (no auto-submission), `CON-2` (sourced claims), `CON-3` (audit trail) are product-level legal protections, not optional.
742:| **M0 — Foundation** | Project boots end-to-end. | Repo, CI, Next.js + FastAPI scaffold, Firebase Auth, Cloud Run deploy, Cloud SQL + pgvector, Secret Manager, base schema + org multi-tenancy. | A logged-in user creates an org; an authenticated `GET /orgs/{id}` returns org-scoped data; app is deployed on Cloud Run. |
744:| **M2 — GovCon scanner** | Discover + rank contracts. | Source Discovery + Opportunity Research + Fit Recommendation (draft); async workflow engine + Pub/Sub + worker; polling UI. | A scan returns ranked opportunities with fit scores and sourced bid/no-bid rationale within minutes; run is auditable. |
748:| **M6 — Audit dashboard + billing + demo evidence** | Make it sellable and provable. | Logs/activity dashboard; audit export (CSV/JSON); Stripe checkout + webhooks + `revenue_records`; time-saved metric; usage/cost surfacing. | Dashboard shows runs/steps/sources/metrics; audit exports cleanly; a real charge writes a `revenue_record`; Gemini + ≥1 GCP service demonstrably in production. |
750:> Sequencing note: the workflow engine (M2) is the backbone for M3–M5; build it once, reuse for all pipelines. Demo evidence (M6) should be wired incrementally from M2 onward so the audit trail is rich by submission time.
761:| Product | Paid conversions (audit/sprint/subscription) | ≥ 1 real paying org (hackathon) |
774:| External source access (SAM.gov/Grants.gov/USAspending) — auth, rate limits, ToS, availability | Scans degrade or break | Confirm API access early (§15); cache snapshots; graceful partial results; pluggable source adapters; allow pasted/uploaded solicitations as a fallback path |
778:| Data privacy of company docs | Breach / compliance | `NFR-2/3`; encryption; signed URLs; org isolation; deletion support |
791:- Firebase Auth and Stripe are the auth and billing providers (substitutable).
798:2. **SAM.gov / Grants.gov / USAspending** — confirm API availability, authentication, rate limits, and terms of use; choose per-source adapter strategy accordingly.
800:4. **Embedding model** — exact embedding model + vector dimension for the pgvector column (`document_chunks.embedding`).
801:5. **pgvector vs. Vertex Vector Search** — confirm pgvector suffices at MVP scale; Vertex is the fallback if retrieval volume grows.

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/api/auth.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Authentication routes (local provider). Firebase clients authenticate via the
Firebase SDK and skip register/login here."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from captureos.audit import record_event
from captureos.config import AuthProviderName, get_settings
from captureos.core.deps import CurrentUser, SessionDep
from captureos.core.errors import AuthError, ConflictError
from captureos.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from captureos.models.enums import ActorType, OrgRole
from captureos.models.org import Organization, OrgMember, User
from captureos.schemas.auth import (
    LoginRequest,
    MeResponse,
    OrgMembershipSummary,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_local() -> None:
    if get_settings().auth_provider is not AuthProviderName.local:
        raise AuthError(
            "Local registration/login is disabled; this deployment uses an external auth provider",
            code="auth_provider_external",
        )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: SessionDep) -> TokenResponse:
    _ensure_local()
    existing = await session.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    session.add(user)
    await session.flush()

    if body.org_name:
        org = Organization(name=body.org_name)
        session.add(org)
        await session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
        await record_event(
            "org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id)
        )

    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    _ensure_local()
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    # Constant-ish behavior: same error whether the email or password is wrong.
    if (
        user is None
        or not user.hashed_password
        or not verify_password(body.password, user.hashed_password)
    ):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is inactive")
    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenResponse:
    _ensure_local()
    payload = decode_token(body.refresh_token, expected_type="refresh")
    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return TokenResponse(
        access_token=create_access_token(user.id, extra={"email": user.email}),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    result = await session.execute(
        select(OrgMember, Organization)
        .join(Organization, Organization.id == OrgMember.org_id)
        .where(OrgMember.user_id == user.id)
    )
    orgs = [
        OrgMembershipSummary(org_id=org.id, name=org.name, role=member.role, plan=org.plan)
        for member, org in result.all()
    ]
    return MeResponse(
        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name),
        orgs=orgs,
    )

codex
The core org dependency and org routes are straightforward on first pass. Next I’m checking whether auth/security, storage, audit, and migration details undermine that apparent correctness.
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/db/session.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/core/security.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Password hashing (Argon2) and JWT issuance/verification for local auth."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from captureos.config import get_settings
from captureos.core.errors import AuthError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, Exception):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except Exception:
        return False


def _create_token(subject: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str | uuid.UUID, extra: dict | None = None) -> str:
    settings = get_settings()
    return _create_token(
        str(user_id), "access", timedelta(minutes=settings.jwt_access_ttl_minutes), extra
    )


def create_refresh_token(user_id: str | uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(str(user_id), "refresh", timedelta(days=settings.jwt_refresh_ttl_days))


def decode_token(token: str, *, expected_type: str | None = None) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token")
    return payload

 succeeded in 0ms:
"""Async engine + session management.

A single lazily-created engine/sessionmaker per process. ``get_session`` is the
FastAPI dependency; ``session_scope`` is the equivalent for workers/scripts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from captureos.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Commits on success, rolls back on error."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager for non-request code (workers, scripts, seeds)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/providers/audit.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Audit sinks (CON-3, FR-AU-2/5).

PostgresAuditSink writes append-only rows in its own transaction so audit durability is
decoupled from the business transaction. BigQueryAuditSink is the production stream.
"""

from __future__ import annotations

import uuid

from captureos.config import Settings
from captureos.logging import get_logger
from captureos.providers.base import AuditSink

logger = get_logger(__name__)

_UUID_FIELDS = ("org_id", "filing_id", "run_id", "step_id")
_ALLOWED = {
    "org_id",
    "filing_id",
    "run_id",
    "step_id",
    "actor",
    "actor_id",
    "action",
    "source_url",
    "model",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "status",
    "payload",
}


def _coerce(event: dict) -> dict:
    out: dict = {k: v for k, v in event.items() if k in _ALLOWED}
    for field in _UUID_FIELDS:
        val = out.get(field)
        if isinstance(val, str):
            out[field] = uuid.UUID(val)
    out.setdefault("payload", {})
    return out


class PostgresAuditSink(AuditSink):
    name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def emit(self, event: dict) -> None:
        from captureos.db.session import session_scope
        from captureos.models.audit import AuditEvent

        data = _coerce(event)
        try:
            async with session_scope() as session:
                session.add(AuditEvent(**data))
        except Exception as exc:  # audit must never break the caller
            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))


class BigQueryAuditSink(AuditSink):  # pragma: no cover - requires GCP credentials
    name = "bigquery"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID required when AUDIT_SINK=bigquery")
        try:
            from google.cloud import bigquery  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-bigquery not installed (uv sync --extra gcp)") from exc
        self._settings = settings
        self._client = bigquery.Client(project=settings.gcp_project_id)
        self._table = (
            f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
        )

    async def emit(self, event: dict) -> None:
        import anyio

        row = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in event.items()}
        errors = await anyio.to_thread.run_sync(
            lambda: self._client.insert_rows_json(self._table, [row])
        )
        if errors:
            logger.error("audit.bigquery_insert_failed", errors=str(errors))

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/providers/storage.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Blob storage: LocalStorage (filesystem, default) and GCSStorage (prod).

Security: keys are sanitized to prevent path traversal outside the base dir (NFR-2).
URIs use a ``local://<key>`` or ``gs://<bucket>/<key>`` scheme.
"""

from __future__ import annotations

from pathlib import Path

from captureos.config import Settings
from captureos.providers.base import PresignedUpload, StorageProvider, StoredBlob

_LOCAL_SCHEME = "local://"


def _key_from_uri(uri: str) -> str:
    return uri[len(_LOCAL_SCHEME) :] if uri.startswith(_LOCAL_SCHEME) else uri


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._base = Path(settings.storage_local_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Reject traversal: the resolved path must stay under the base dir.
        candidate = (self._base / key.lstrip("/")).resolve()
        if not str(candidate).startswith(str(self._base)):
            raise ValueError(f"Illegal storage key (path traversal): {key!r}")
        return candidate

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredBlob(uri=f"{_LOCAL_SCHEME}{key}", size=len(data))

    async def get(self, uri: str) -> bytes:
        return self._path(_key_from_uri(uri)).read_bytes()

    async def delete(self, uri: str) -> None:
        path = self._path(_key_from_uri(uri))
        if path.exists():
            path.unlink()

    async def exists(self, uri: str) -> bool:
        return self._path(_key_from_uri(uri)).exists()

    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
        # The backend hosts the upload route for local storage (added in M1).
        return PresignedUpload(
            url=f"/api/v1/blobs/{key}",
            method="PUT",
            headers={"content-type": content_type} if content_type else {},
            storage_uri=f"{_LOCAL_SCHEME}{key}",
        )

    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
        return f"/api/v1/blobs/{_key_from_uri(uri)}"


class GCSStorage(StorageProvider):  # pragma: no cover - requires GCP credentials
    name = "gcs"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET required when STORAGE_PROVIDER=gcs")
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage not installed (uv sync --extra gcp)") from exc
        self._bucket_name = settings.gcs_bucket
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket)

    def _key_from_uri(self, uri: str) -> str:
        prefix = f"gs://{self._bucket_name}/"
        return uri[len(prefix) :] if uri.startswith(prefix) else uri

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
        import anyio

        blob = self._bucket.blob(key)
        await anyio.to_thread.run_sync(
            lambda: blob.upload_from_string(data, content_type=content_type)
        )
        return StoredBlob(uri=f"gs://{self._bucket_name}/{key}", size=len(data))

    async def get(self, uri: str) -> bytes:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        return await anyio.to_thread.run_sync(blob.download_as_bytes)

    async def delete(self, uri: str) -> None:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        await anyio.to_thread.run_sync(blob.delete)

    async def exists(self, uri: str) -> bool:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        return await anyio.to_thread.run_sync(blob.exists)

    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
        from datetime import timedelta

        blob = self._bucket.blob(key)
        url = blob.generate_signed_url(
            version="v4", expiration=timedelta(minutes=15), method="PUT", content_type=content_type
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"content-type": content_type} if content_type else {},
            storage_uri=f"gs://{self._bucket_name}/{key}",
        )

    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
        from datetime import timedelta

        blob = self._bucket.blob(self._key_from_uri(uri))
        return blob.generate_signed_url(
            version="v4", expiration=timedelta(seconds=expires_seconds), method="GET"
        )

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/migrations/versions/f28c812fca98_initial_schema.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""initial schema

Revision ID: f28c812fca98
Revises: 
Create Date: 2026-06-19 14:38:07.288248
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = 'f28c812fca98'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required extensions must exist before any vector column / trigram index is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('organizations',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('uei', sa.String(length=32), nullable=True),
    sa.Column('plan', sa.String(length=32), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=True),
    sa.Column('external_auth_id', sa.String(length=255), nullable=True),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_external_auth_id'), 'users', ['external_auth_id'], unique=True)
    op.create_table('audit_events',
    sa.Column('filing_id', sa.UUID(), nullable=True),
    sa.Column('run_id', sa.UUID(), nullable=True),
    sa.Column('step_id', sa.UUID(), nullable=True),
    sa.Column('actor', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.String(length=255), nullable=True),
    sa.Column('action', sa.String(length=128), nullable=False),
    sa.Column('source_url', sa.String(length=2048), nullable=True),
    sa.Column('model', sa.String(length=128), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_audit_events_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_occurred_at'), 'audit_events', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_audit_events_org_id'), 'audit_events', ['org_id'], unique=False)
    op.create_index('ix_audit_events_org_occurred', 'audit_events', ['org_id', 'occurred_at'], unique=False)
    op.create_index('ix_audit_events_run', 'audit_events', ['run_id'], unique=False)
    op.create_table('company_profiles',
    sa.Column('website_url', sa.String(length=2048), nullable=True),
    sa.Column('industry', sa.String(length=255), nullable=True),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('services', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('naics_guesses', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('funding_categories', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('target_customers', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('certifications', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('missing_fields', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('user_overrides', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('capability_statement', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_company_profiles_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_company_profiles')),
    sa.UniqueConstraint('org_id', name=op.f('uq_company_profiles_org_id'))
    )
    op.create_index(op.f('ix_company_profiles_org_id'), 'company_profiles', ['org_id'], unique=False)
    op.create_table('customer_feedback',
    sa.Column('rating', sa.Numeric(precision=2, scale=0), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_customer_feedback_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_feedback'))
    )
    op.create_index(op.f('ix_customer_feedback_org_id'), 'customer_feedback', ['org_id'], unique=False)
    op.create_table('documents',
    sa.Column('filename', sa.String(length=512), nullable=False),
    sa.Column('storage_uri', sa.String(length=2048), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('mime_type', sa.String(length=255), nullable=True),
    sa.Column('source_kind', sa.String(length=32), nullable=False),
    sa.Column('parse_status', sa.String(length=16), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_documents_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
    sa.UniqueConstraint('org_id', 'content_hash', name=op.f('uq_documents_org_id'))
    )
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)
    op.create_index(op.f('ix_documents_org_id'), 'documents', ['org_id'], unique=False)
    op.create_table('org_members',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_org_members_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_org_members_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_org_members')),
    sa.UniqueConstraint('org_id', 'user_id', name=op.f('uq_org_members_org_id'))
    )
    op.create_index(op.f('ix_org_members_org_id'), 'org_members', ['org_id'], unique=False)
    op.create_index(op.f('ix_org_members_user_id'), 'org_members', ['user_id'], unique=False)
    op.create_table('revenue_records',
    sa.Column('product', sa.String(length=32), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('charged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_revenue_records_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_revenue_records')),
    sa.UniqueConstraint('external_id', name=op.f('uq_revenue_records_external_id'))
    )
    op.create_index(op.f('ix_revenue_records_org_id'), 'revenue_records', ['org_id'], unique=False)
    op.create_table('subscriptions',
    sa.Column('product', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_subscriptions_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subscriptions'))
    )
    op.create_index(op.f('ix_subscriptions_external_id'), 'subscriptions', ['external_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_org_id'), 'subscriptions', ['org_id'], unique=False)
    op.create_table('document_chunks',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('locator', sa.String(length=255), nullable=True),
    sa.Column('embedding', Vector(768), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_chunks_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_document_chunks_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks')),
    sa.UniqueConstraint('document_id', 'ordinal', name=op.f('uq_document_chunks_document_id'))
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index('ix_document_chunks_embedding', 'document_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_document_chunks_org_id'), 'document_chunks', ['org_id'], unique=False)
    op.create_table('sources',
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=True),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('snapshot_uri', sa.String(length=2048), nullable=True),
    sa.Column('title', sa.String(length=512), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_sources_document_id_documents'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_sources_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sources'))
    )
    op.create_index(op.f('ix_sources_document_id'), 'sources', ['document_id'], unique=False)
    op.create_index(op.f('ix_sources_org_id'), 'sources', ['org_id'], unique=False)
    op.create_table('evidence_items',
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('origin', sa.String(length=16), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('document_chunk_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_chunk_id'], ['document_chunks.id'], name=op.f('fk_evidence_items_document_chunk_id_document_chunks'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_items_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_evidence_items_source_id_sources'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_items'))
    )
    op.create_index(op.f('ix_evidence_items_document_chunk_id'), 'evidence_items', ['document_chunk_id'], unique=False)
    op.create_index(op.f('ix_evidence_items_org_id'), 'evidence_items', ['org_id'], unique=False)
    op.create_index(op.f('ix_evidence_items_source_id'), 'evidence_items', ['source_id'], unique=False)
    op.create_table('opportunities',
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=1024), nullable=False),
    sa.Column('sponsor', sa.String(length=512), nullable=True),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('fit_score', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('decision_hint', sa.String(length=32), nullable=True),
    sa.Column('fit_rationale', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_opportunities_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_opportunities_source_id_sources'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_opportunities'))
    )
    op.create_index(op.f('ix_opportunities_external_id'), 'opportunities', ['external_id'], unique=False)
    op.create_index(op.f('ix_opportunities_kind'), 'opportunities', ['kind'], unique=False)
    op.create_index(op.f('ix_opportunities_org_id'), 'opportunities', ['org_id'], unique=False)
    op.create_index(op.f('ix_opportunities_source_id'), 'opportunities', ['source_id'], unique=False)
    op.create_table('filings',
    sa.Column('opportunity_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('owner_user_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], name=op.f('fk_filings_opportunity_id_opportunities'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filings_org_id_organizations'), ondelete='CASCADE'),

exec
/bin/zsh -lc "sed -n '260,520p' apps/api/migrations/versions/f28c812fca98_initial_schema.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filings_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], name=op.f('fk_filings_owner_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_filings'))
    )
    op.create_index(op.f('ix_filings_opportunity_id'), 'filings', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_filings_org_id'), 'filings', ['org_id'], unique=False)
    op.create_index(op.f('ix_filings_status'), 'filings', ['status'], unique=False)
    op.create_table('approvals',
    sa.Column('filing_id', sa.UUID(), nullable=False),
    sa.Column('target', sa.String(length=16), nullable=False),
    sa.Column('approver_user_id', sa.UUID(), nullable=True),
    sa.Column('decision', sa.String(length=16), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], name=op.f('fk_approvals_approver_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_approvals_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_approvals_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_approvals'))
    )
    op.create_index(op.f('ix_approvals_filing_id'), 'approvals', ['filing_id'], unique=False)
    op.create_index(op.f('ix_approvals_org_id'), 'approvals', ['org_id'], unique=False)
    op.create_table('filing_requirements',
    sa.Column('filing_id', sa.UUID(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('mandatory', sa.Boolean(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('locator', sa.String(length=255), nullable=True),
    sa.Column('needs_review', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_filing_requirements_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filing_requirements_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_filing_requirements_source_id_sources'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_filing_requirements'))
    )
    op.create_index(op.f('ix_filing_requirements_filing_id'), 'filing_requirements', ['filing_id'], unique=False)
    op.create_index(op.f('ix_filing_requirements_org_id'), 'filing_requirements', ['org_id'], unique=False)
    op.create_table('generated_documents',
    sa.Column('filing_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_md', sa.Text(), nullable=False),
    sa.Column('export_uri', sa.String(length=2048), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('citation_validated', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_generated_documents_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_generated_documents_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_generated_documents')),
    sa.UniqueConstraint('filing_id', 'type', 'version', name=op.f('uq_generated_documents_filing_id'))
    )
    op.create_index(op.f('ix_generated_documents_filing_id'), 'generated_documents', ['filing_id'], unique=False)
    op.create_index(op.f('ix_generated_documents_org_id'), 'generated_documents', ['org_id'], unique=False)
    op.create_table('recommendations',
    sa.Column('filing_id', sa.UUID(), nullable=False),
    sa.Column('decision', sa.String(length=16), nullable=False),
    sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('rationale', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('approved', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_recommendations_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_recommendations_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendations')),
    sa.UniqueConstraint('filing_id', name=op.f('uq_recommendations_filing_id'))
    )
    op.create_index(op.f('ix_recommendations_filing_id'), 'recommendations', ['filing_id'], unique=False)
    op.create_index(op.f('ix_recommendations_org_id'), 'recommendations', ['org_id'], unique=False)
    op.create_table('workflow_runs',
    sa.Column('filing_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('input_params', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('partial_results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('time_saved_minutes', sa.Integer(), nullable=True),
    sa.Column('total_input_tokens', sa.Integer(), nullable=False),
    sa.Column('total_output_tokens', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_workflow_runs_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_runs_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_runs'))
    )
    op.create_index(op.f('ix_workflow_runs_filing_id'), 'workflow_runs', ['filing_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_org_id'), 'workflow_runs', ['org_id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_status'), 'workflow_runs', ['status'], unique=False)
    op.create_table('evidence_matches',
    sa.Column('filing_id', sa.UUID(), nullable=False),
    sa.Column('requirement_id', sa.UUID(), nullable=False),
    sa.Column('evidence_item_id', sa.UUID(), nullable=True),
    sa.Column('score', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['evidence_item_id'], ['evidence_items.id'], name=op.f('fk_evidence_matches_evidence_item_id_evidence_items'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_evidence_matches_filing_id_filings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_matches_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requirement_id'], ['filing_requirements.id'], name=op.f('fk_evidence_matches_requirement_id_filing_requirements'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_matches'))
    )
    op.create_index(op.f('ix_evidence_matches_filing_id'), 'evidence_matches', ['filing_id'], unique=False)
    op.create_index(op.f('ix_evidence_matches_org_id'), 'evidence_matches', ['org_id'], unique=False)
    op.create_index(op.f('ix_evidence_matches_requirement_id'), 'evidence_matches', ['requirement_id'], unique=False)
    op.create_index(op.f('ix_evidence_matches_status'), 'evidence_matches', ['status'], unique=False)
    op.create_table('workflow_steps',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_steps_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], name=op.f('fk_workflow_steps_run_id_workflow_runs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_steps')),
    sa.UniqueConstraint('run_id', 'name', name=op.f('uq_workflow_steps_run_id'))
    )
    op.create_index(op.f('ix_workflow_steps_org_id'), 'workflow_steps', ['org_id'], unique=False)
    op.create_index(op.f('ix_workflow_steps_run_id'), 'workflow_steps', ['run_id'], unique=False)
    op.create_table('agent_runs',
    sa.Column('step_id', sa.UUID(), nullable=False),
    sa.Column('agent_name', sa.String(length=128), nullable=False),
    sa.Column('model', sa.String(length=128), nullable=True),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_agent_runs_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], name=op.f('fk_agent_runs_step_id_workflow_steps'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs'))
    )
    op.create_index(op.f('ix_agent_runs_org_id'), 'agent_runs', ['org_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_step_id'), 'agent_runs', ['step_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_agent_runs_step_id'), table_name='agent_runs')
    op.drop_index(op.f('ix_agent_runs_org_id'), table_name='agent_runs')
    op.drop_table('agent_runs')
    op.drop_index(op.f('ix_workflow_steps_run_id'), table_name='workflow_steps')
    op.drop_index(op.f('ix_workflow_steps_org_id'), table_name='workflow_steps')
    op.drop_table('workflow_steps')
    op.drop_index(op.f('ix_evidence_matches_status'), table_name='evidence_matches')
    op.drop_index(op.f('ix_evidence_matches_requirement_id'), table_name='evidence_matches')
    op.drop_index(op.f('ix_evidence_matches_org_id'), table_name='evidence_matches')
    op.drop_index(op.f('ix_evidence_matches_filing_id'), table_name='evidence_matches')
    op.drop_table('evidence_matches')
    op.drop_index(op.f('ix_workflow_runs_status'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_org_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_filing_id'), table_name='workflow_runs')
    op.drop_table('workflow_runs')
    op.drop_index(op.f('ix_recommendations_org_id'), table_name='recommendations')
    op.drop_index(op.f('ix_recommendations_filing_id'), table_name='recommendations')
    op.drop_table('recommendations')
    op.drop_index(op.f('ix_generated_documents_org_id'), table_name='generated_documents')
    op.drop_index(op.f('ix_generated_documents_filing_id'), table_name='generated_documents')
    op.drop_table('generated_documents')
    op.drop_index(op.f('ix_filing_requirements_org_id'), table_name='filing_requirements')
    op.drop_index(op.f('ix_filing_requirements_filing_id'), table_name='filing_requirements')
    op.drop_table('filing_requirements')
    op.drop_index(op.f('ix_approvals_org_id'), table_name='approvals')
    op.drop_index(op.f('ix_approvals_filing_id'), table_name='approvals')
    op.drop_table('approvals')
    op.drop_index(op.f('ix_filings_status'), table_name='filings')
    op.drop_index(op.f('ix_filings_org_id'), table_name='filings')
    op.drop_index(op.f('ix_filings_opportunity_id'), table_name='filings')
    op.drop_table('filings')
    op.drop_index(op.f('ix_opportunities_source_id'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_org_id'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_kind'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_external_id'), table_name='opportunities')
    op.drop_table('opportunities')
    op.drop_index(op.f('ix_evidence_items_source_id'), table_name='evidence_items')
    op.drop_index(op.f('ix_evidence_items_org_id'), table_name='evidence_items')
    op.drop_index(op.f('ix_evidence_items_document_chunk_id'), table_name='evidence_items')
    op.drop_table('evidence_items')
    op.drop_index(op.f('ix_sources_org_id'), table_name='sources')
    op.drop_index(op.f('ix_sources_document_id'), table_name='sources')
    op.drop_table('sources')
    op.drop_index(op.f('ix_document_chunks_org_id'), table_name='document_chunks')
    op.drop_index('ix_document_chunks_embedding', table_name='document_chunks', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_subscriptions_org_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_external_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    op.drop_index(op.f('ix_revenue_records_org_id'), table_name='revenue_records')
    op.drop_table('revenue_records')
    op.drop_index(op.f('ix_org_members_user_id'), table_name='org_members')
    op.drop_index(op.f('ix_org_members_org_id'), table_name='org_members')
    op.drop_table('org_members')
    op.drop_index(op.f('ix_documents_org_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_customer_feedback_org_id'), table_name='customer_feedback')
    op.drop_table('customer_feedback')
    op.drop_index(op.f('ix_company_profiles_org_id'), table_name='company_profiles')
    op.drop_table('company_profiles')
    op.drop_index('ix_audit_events_run', table_name='audit_events')
    op.drop_index('ix_audit_events_org_occurred', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_org_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_occurred_at'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_users_external_auth_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('organizations')
    # ### end Alembic commands ###

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/workflow.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/filings.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,220p' apps/api/captureos/api/router.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/audit.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/org.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Aggregates all v1 routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from captureos.api import auth, health, orgs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(orgs.router)

 succeeded in 0ms:
"""Tenancy: organizations, global users, and org membership (CON-5, NFR-1)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, TimestampMixin, UUIDPKMixin
from captureos.models.enums import OrgPlan, OrgRole


class Organization(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uei: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default=OrgPlan.free.value)

    members: Mapped[list[OrgMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(UUIDPKMixin, TimestampMixin, Base):
    """Global identity (not org-scoped). Auth credentials live here for local auth;
    ``external_auth_id`` holds the Firebase UID when AUTH_PROVIDER=firebase."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_auth_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    memberships: Mapped[list[OrgMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OrgMember(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=OrgRole.owner.value)

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")

 succeeded in 0ms:
"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.

Drives every async pipeline and is the backbone of the audit trail (CON-3, FR-AU-1).
``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
``workflow_steps.agent_run_id`` is dropped to avoid a circular FK); retries append rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import AgentRunStatus, StepStatus, WorkflowStatus, WorkflowType


class WorkflowRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowType.company_brain.value
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WorkflowStatus.queued.value, index=True
    )
    input_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    partial_results: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_saved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="WorkflowStep.ordinal"
    )


class WorkflowStep(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "workflow_steps"
    # Idempotency: a step name is unique within a run (FR-RE §10.5, idempotent re-delivery).
    __table_args__ = (UniqueConstraint("run_id", "name"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=StepStatus.pending.value
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="steps")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )


class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    step_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AgentRunStatus.success.value
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")

 succeeded in 0ms:
"""Postgres mirror of the append-only audit event stream (PRD §8.4, FR-AU-2).

In production the authoritative stream is BigQuery; this table powers the in-app
dashboard and CSV/JSON export, and is the default sink in local/dev (AUDIT_SINK=postgres).
Rows are append-only — never updated or deleted (CON-3).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, UUIDPKMixin
from captureos.models.enums import ActorType


class AuditEvent(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_occurred", "org_id", "occurred_at"),
        Index("ix_audit_events_run", "run_id"),
    )

    filing_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    actor: Mapped[str] = mapped_column(String(16), nullable=False, default=ActorType.system.value)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # PII-restricted payload: store summaries/pointers, not full document text (NFR-3).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/documents.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""The Filing aggregate and everything that hangs off it (PRD §8, central object)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import (
    ApprovalDecision,
    ApprovalTarget,
    FilingStatus,
    GeneratedDocStatus,
    GeneratedDocType,
    MatchStatus,
    RecommendationDecision,
    RequirementCategory,
)


class Filing(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "filings"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FilingStatus.draft.value, index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requirements: Mapped[list[FilingRequirement]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    evidence_matches: Mapped[list[EvidenceMatch]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    recommendation: Mapped[Recommendation | None] = relationship(
        back_populates="filing", cascade="all, delete-orphan", uselist=False
    )
    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class FilingRequirement(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "filing_requirements"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RequirementCategory.other.value
    )
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Citation back to the solicitation (CON-2).
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Flagged-for-review when extraction confidence is low / schema-retry exhausted (FR-RE-2).
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="requirements")


class EvidenceMatch(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "evidence_matches"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evidence_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MatchStatus.missing.value, index=True
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    filing: Mapped[Filing] = relationship(back_populates="evidence_matches")


class Recommendation(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    # One current recommendation per filing (avoids the PRD's circular FK).
    __table_args__ = (UniqueConstraint("filing_id"),)

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RecommendationDecision.do_not_pursue.value
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    # {for: [...], against: [...], key_gaps: [...]} each item carrying citations (CON-2).
    rationale: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Draft until a human approves (FR-AP-1 / FR-RC-3).
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="recommendation")


class GeneratedDocument(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "generated_documents"
    __table_args__ = (UniqueConstraint("filing_id", "type", "version"),)

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=GeneratedDocType.narrative.value
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    export_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GeneratedDocStatus.draft.value
    )
    # Citations resolved for this doc; the Audit/Citation agent populates/validates this.
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # True only after the Audit/Citation check confirms zero unsourced claims (CON-2).
    citation_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    filing: Mapped[Filing] = relationship(back_populates="generated_documents")


class Approval(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "approvals"

    filing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ApprovalTarget.recommendation.value
    )
    approver_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ApprovalDecision.approved.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    filing: Mapped[Filing] = relationship(back_populates="approvals")

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/company.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Company Brain: the structured org profile (FR-CB-*)."""

from __future__ import annotations

from sqlalchemy import String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin

_EMPTY_LIST = text("'[]'::jsonb")
_EMPTY_OBJ = text("'{}'::jsonb")


class CompanyProfile(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"
    # One profile per org.
    __table_args__ = (UniqueConstraint("org_id"),)

    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # array of {name, description}
    services: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # array of {code, label, confidence}
    naics_guesses: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    funding_categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    target_customers: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # array of {name, status: detected/missing/unknown, source_id}
    certifications: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # checklist of fields that could not be populated (FR-CB-3)
    missing_fields: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    )
    # which fields the user has explicitly overridden (FR-CB-5 precedence)
    user_overrides: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=_EMPTY_OBJ
    )

    capability_statement: Mapped[str | None] = mapped_column(Text, nullable=True)

 succeeded in 0ms:
"""Documents and their embedded chunks (FR-DI-*).

The ``embedding`` column dimension is fixed at schema-creation time and must match
``Settings.embedding_dim`` (D7 = 768, Gemini text-embedding-004 compatible). Changing
the embedding model's dimension requires a migration.
"""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import DocumentSourceKind, ParseStatus

EMBEDDING_DIM = 768  # keep in sync with Settings.embedding_dim


class Document(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    # Idempotent ingestion: same content within an org is not re-ingested (FR-DI-6).
    __table_args__ = (UniqueConstraint("org_id", "content_hash"),)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentSourceKind.upload.value
    )
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ParseStatus.pending.value
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        # IVF/HNSW index added in M1 once data exists; cosine distance for retrieval.
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Page/section reference so citations resolve to a source (FR-DI-5).
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/config.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/auth/local.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Local JWT auth provider. Verifies tokens issued by ``core.security``."""

from __future__ import annotations

from captureos.auth.base import AuthPrincipal, AuthProvider
from captureos.config import Settings
from captureos.core.security import decode_token


class LocalAuthProvider(AuthProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify_token(self, token: str) -> AuthPrincipal:
        payload = decode_token(token, expected_type="access")
        return AuthPrincipal(subject=str(payload["sub"]), email=payload.get("email"), is_local=True)

 succeeded in 0ms:
"""Central typed configuration.

Everything cloud-related is selected here via env vars, so call sites depend only
on abstract provider interfaces (see ``captureos.providers``). This is the seam that
makes the system "local-first, cloud-ready" (PROJECT.md D1).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the repo-root .env regardless of CWD (the app/alembic run from apps/api).
# In containers this path won't exist; real env vars are used instead.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class AppEnv(StrEnum):
    local = "local"
    ci = "ci"
    staging = "staging"
    production = "production"


class AuthProviderName(StrEnum):
    local = "local"
    firebase = "firebase"


class LLMProviderName(StrEnum):
    mock = "mock"
    gemini = "gemini"


class EmbeddingsProviderName(StrEnum):
    mock = "mock"
    gemini = "gemini"


class StorageProviderName(StrEnum):
    local = "local"
    gcs = "gcs"


class QueueProviderName(StrEnum):
    local = "local"
    pubsub = "pubsub"


class DocparseProviderName(StrEnum):
    local = "local"
    docai = "docai"


class AuditSinkName(StrEnum):
    postgres = "postgres"
    bigquery = "bigquery"


class SecretsBackendName(StrEnum):
    env = "env"
    gcp_secret_manager = "gcp_secret_manager"  # noqa: S105 - enum value, not a secret


class BillingProviderName(StrEnum):
    mock = "mock"
    stripe = "stripe"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    captureos_env: AppEnv = AppEnv.local
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 — containerized service binds all interfaces
    api_port: int = 8000
    cors_allow_origins: str = "http://localhost:3000"

    # ---- Auth ----
    auth_provider: AuthProviderName = AuthProviderName.local
    jwt_secret: str = "dev-only-insecure-change-me-please-32chars-min"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 14
    firebase_project_id: str | None = None
    google_application_credentials: str | None = None

    # ---- Database ----
    database_url: str = "postgresql+asyncpg://captureos:captureos@localhost:5432/captureos"
    database_url_sync: str = "postgresql+psycopg://captureos:captureos@localhost:5432/captureos"
    db_echo: bool = False
    run_migrations_on_start: bool = False

    # ---- LLM ----
    llm_provider: LLMProviderName = LLMProviderName.mock
    gemini_api_key: str | None = None
    gemini_model_pro: str = "gemini-2.5-pro"
    gemini_model_flash: str = "gemini-2.5-flash"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2

    # ---- Embeddings ----
    embeddings_provider: EmbeddingsProviderName = EmbeddingsProviderName.mock
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    # ---- Storage ----
    storage_provider: StorageProviderName = StorageProviderName.local
    storage_local_dir: str = "./.data/blobs"
    gcs_bucket: str | None = None

    # ---- Queue ----
    queue_provider: QueueProviderName = QueueProviderName.local
    pubsub_project_id: str | None = None
    pubsub_topic: str = "captureos-workflow-steps"

    # ---- Docparse ----
    docparse_provider: DocparseProviderName = DocparseProviderName.local
    docai_processor_id: str | None = None
    docai_location: str = "us"

    # ---- Audit ----
    audit_sink: AuditSinkName = AuditSinkName.postgres
    bigquery_dataset: str = "captureos_audit"
    bigquery_table: str = "events"

    # ---- Secrets ----
    secrets_backend: SecretsBackendName = SecretsBackendName.env
    gcp_project_id: str | None = None

    # ---- Billing ----
    billing_provider: BillingProviderName = BillingProviderName.mock
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_audit: str | None = None
    stripe_price_sprint: str | None = None
    stripe_price_autopilot: str | None = None

    # ---- External sources ----
    sam_gov_api_key: str | None = None
    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
    source_fetch_cache_ttl_seconds: int = 86400
    source_fetch_rate_limit_per_min: int = 30

    # ---- Cost guard ----
    workflow_token_budget: int = 200_000

    @field_validator("cors_allow_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.captureos_env in (AppEnv.staging, AppEnv.production)

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> Settings:
        """Fail fast if a prod-like env still uses insecure defaults (CON-4)."""
        if self.is_production_like:
            if "insecure" in self.jwt_secret or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be a strong, non-default value (>=32 chars) in production"
                )
            if self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id:
                raise ValueError("FIREBASE_PROJECT_ID required when AUTH_PROVIDER=firebase")
            if self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY required when LLM_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/auth/base.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,240p' apps/api/captureos/audit/service.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/auth/firebase.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/core/errors.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Auth provider interface and the principal it resolves a token to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class AuthPrincipal:
    # For local auth, ``subject`` is the CaptureOS user id. For Firebase it is the uid;
    # the user is then resolved/provisioned by ``external_auth_id``.
    subject: str
    email: str | None = None
    is_local: bool = True


@runtime_checkable
class AuthProvider(Protocol):
    name: str

    async def verify_token(self, token: str) -> AuthPrincipal: ...

 succeeded in 0ms:
"""Thin facade over the configured audit sink. Build an event and persist it.

This is the single choke point routes/agents call to satisfy CON-3, so the audit
schema stays consistent regardless of sink (Postgres vs BigQuery).
"""

from __future__ import annotations

import uuid
from typing import Any

from captureos.models.enums import ActorType
from captureos.providers import get_audit_sink


async def record_event(
    action: str,
    *,
    org_id: str | uuid.UUID,
    actor: ActorType | str = ActorType.system,
    actor_id: str | None = None,
    filing_id: str | uuid.UUID | None = None,
    run_id: str | uuid.UUID | None = None,
    step_id: str | uuid.UUID | None = None,
    source_url: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    status: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "action": action,
        "org_id": str(org_id),
        "actor": str(actor),
        "actor_id": actor_id,
        "filing_id": str(filing_id) if filing_id else None,
        "run_id": str(run_id) if run_id else None,
        "step_id": str(step_id) if step_id else None,
        "source_url": source_url,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "status": status,
        "payload": payload or {},
    }
    await get_audit_sink().emit(event)

 succeeded in 0ms:
"""Uniform error contract (PRD §9.9): every error → {error: {code, message, details?}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from captureos.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    code = "error"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class AuthError(AppError):
    code = "unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class ValidationFailed(AppError):
    code = "validation_error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def _body(code: str, message: str, details: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body("internal_error", "An unexpected error occurred"),
        )

 succeeded in 0ms:
"""Firebase auth provider. Verifies Firebase ID tokens (prod; `gcp` extra)."""

from __future__ import annotations

from captureos.auth.base import AuthPrincipal, AuthProvider
from captureos.config import Settings
from captureos.core.errors import AuthError


class FirebaseAuthProvider(AuthProvider):  # pragma: no cover - requires Firebase config
    name = "firebase"

    def __init__(self, settings: Settings) -> None:
        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials
        except ImportError as exc:
            raise RuntimeError("firebase-admin not installed (uv sync --extra gcp)") from exc
        if not firebase_admin._apps:
            cred = (
                credentials.Certificate(settings.google_application_credentials)
                if settings.google_application_credentials
                else credentials.ApplicationDefault()
            )
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        self._settings = settings

    async def verify_token(self, token: str) -> AuthPrincipal:
        import anyio
        from firebase_admin import auth as fb_auth  # type: ignore

        try:
            decoded = await anyio.to_thread.run_sync(lambda: fb_auth.verify_id_token(token))
        except Exception as exc:
            raise AuthError("Invalid Firebase token") from exc
        return AuthPrincipal(subject=decoded["uid"], email=decoded.get("email"), is_local=False)

exec
/bin/zsh -lc "sed -n '1,200p' apps/api/captureos/audit/__init__.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Audit logging service (CON-3, FR-AU-2)."""

from captureos.audit.service import record_event

__all__ = ["record_event"]

codex
The next pass is about cross-cutting behavior: provider construction, how tokens are stored/used in the web app, and whether the migration actually matches the declared model contract.
exec
/bin/zsh -lc "sed -n '1,320p' apps/api/captureos/providers/__init__.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Provider factory. Selects local vs cloud implementations from config (D1).

Call sites use ``get_llm()``, ``get_storage()``, etc. — never the concrete classes —
so swapping providers is a config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache

from captureos.config import (
    AuditSinkName,
    DocparseProviderName,
    EmbeddingsProviderName,
    LLMProviderName,
    QueueProviderName,
    SecretsBackendName,
    Settings,
    StorageProviderName,
    get_settings,
)
from captureos.providers.audit import BigQueryAuditSink, PostgresAuditSink
from captureos.providers.base import (
    AuditSink,
    DocparseProvider,
    EmbeddingsProvider,
    LLMProvider,
    ModelTier,
    QueueProvider,
    SecretsProvider,
    StorageProvider,
)
from captureos.providers.docparse import DocAIDocparse, LocalDocparse
from captureos.providers.embeddings import GeminiEmbeddings, MockEmbeddings
from captureos.providers.llm import GeminiLLM, MockLLM
from captureos.providers.queue import LocalQueue, PubSubQueue
from captureos.providers.secrets import EnvSecrets, GCPSecretManager
from captureos.providers.storage import GCSStorage, LocalStorage

__all__ = [
    "ModelTier",
    "LLMProvider",
    "EmbeddingsProvider",
    "StorageProvider",
    "QueueProvider",
    "DocparseProvider",
    "SecretsProvider",
    "AuditSink",
    "get_llm",
    "get_embeddings",
    "get_storage",
    "get_queue",
    "get_docparse",
    "get_secrets",
    "get_audit_sink",
    "reset_providers",
]


@lru_cache
def get_llm(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    if s.llm_provider is LLMProviderName.gemini:
        return GeminiLLM(s)
    return MockLLM(s)


@lru_cache
def get_embeddings(settings: Settings | None = None) -> EmbeddingsProvider:
    s = settings or get_settings()
    if s.embeddings_provider is EmbeddingsProviderName.gemini:
        return GeminiEmbeddings(s)
    return MockEmbeddings(s)


@lru_cache
def get_storage(settings: Settings | None = None) -> StorageProvider:
    s = settings or get_settings()
    if s.storage_provider is StorageProviderName.gcs:
        return GCSStorage(s)
    return LocalStorage(s)


@lru_cache
def get_queue(settings: Settings | None = None) -> QueueProvider:
    s = settings or get_settings()
    if s.queue_provider is QueueProviderName.pubsub:
        return PubSubQueue(s)
    return LocalQueue(s)


@lru_cache
def get_docparse(settings: Settings | None = None) -> DocparseProvider:
    s = settings or get_settings()
    if s.docparse_provider is DocparseProviderName.docai:
        return DocAIDocparse(s)
    return LocalDocparse(s)


@lru_cache
def get_secrets(settings: Settings | None = None) -> SecretsProvider:
    s = settings or get_settings()
    if s.secrets_backend is SecretsBackendName.gcp_secret_manager:
        return GCPSecretManager(s)
    return EnvSecrets(s)


@lru_cache
def get_audit_sink(settings: Settings | None = None) -> AuditSink:
    s = settings or get_settings()
    if s.audit_sink is AuditSinkName.bigquery:
        return BigQueryAuditSink(s)
    return PostgresAuditSink(s)


def reset_providers() -> None:
    """Clear cached providers (used by tests that swap config)."""
    for fn in (
        get_llm,
        get_embeddings,
        get_storage,
        get_queue,
        get_docparse,
        get_secrets,
        get_audit_sink,
    ):
        fn.cache_clear()

exec
/bin/zsh -lc "sed -n '1,240p' apps/api/captureos/providers/secrets.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/main.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Secret retrieval (CON-4). Env-backed by default; GCP Secret Manager in prod.

Secrets are read server-side only and never serialized to clients.
"""

from __future__ import annotations

import os

from captureos.config import Settings
from captureos.providers.base import SecretsProvider


class EnvSecrets(SecretsProvider):
    name = "env"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self, key: str) -> str | None:
        # Prefer an explicit env var; fall back to a matching Settings attribute.
        if (val := os.environ.get(key)) is not None:
            return val
        return getattr(self._settings, key.lower(), None)


class GCPSecretManager(SecretsProvider):  # pragma: no cover - requires GCP credentials
    name = "gcp_secret_manager"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID required when SECRETS_BACKEND=gcp_secret_manager")
        try:
            from google.cloud import secretmanager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-secret-manager not installed (uv sync --extra gcp)"
            ) from exc
        self._project = settings.gcp_project_id
        self._client = secretmanager.SecretManagerServiceClient()

    def get(self, key: str) -> str | None:
        name = f"projects/{self._project}/secrets/{key}/versions/latest"
        try:
            response = self._client.access_secret_version(name=name)
            return response.payload.data.decode("utf-8")
        except Exception:
            return None

 succeeded in 0ms:
"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from captureos import __version__
from captureos.api.router import api_router
from captureos.config import get_settings
from captureos.core.errors import register_exception_handlers
from captureos.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info(
        "startup",
        env=settings.captureos_env.value,
        llm=settings.llm_provider.value,
        storage=settings.storage_provider.value,
        auth=settings.auth_provider.value,
    )
    if settings.run_migrations_on_start:
        import anyio

        from captureos.db.migrate import apply_migrations

        logger.info("migrations.apply")
        await anyio.to_thread.run_sync(apply_migrations)
    yield
    from captureos.db.session import get_engine

    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CaptureOS API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def root_health() -> dict:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()

exec
/bin/zsh -lc "sed -n '1,320p' apps/api/captureos/providers/base.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/lib/api.ts" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Provider interfaces (Protocols) and shared result types.

Call sites depend on these abstractions only. Concrete implementations (local + GCP)
live in sibling modules and are selected by config in ``providers/__init__.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ModelTier(StrEnum):
    flash = "flash"  # cheap/extractive (PRD NFR-6)
    pro = "pro"  # reasoning-heavy


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dim: int


@dataclass(slots=True)
class ParsedPage:
    page: int
    text: str


@dataclass(slots=True)
class ParsedDocument:
    text: str
    pages: list[ParsedPage] = field(default_factory=list)
    page_count: int = 0


@dataclass(slots=True)
class StoredBlob:
    uri: str
    size: int


@dataclass(slots=True)
class PresignedUpload:
    """How the client uploads a blob. For local storage this is an API route the
    backend hosts; for GCS it is a signed PUT URL."""

    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)
    storage_uri: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse: ...


@runtime_checkable
class EmbeddingsProvider(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...


@runtime_checkable
class StorageProvider(Protocol):
    name: str

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> StoredBlob: ...
    async def get(self, uri: str) -> bytes: ...
    async def delete(self, uri: str) -> None: ...
    async def exists(self, uri: str) -> bool: ...
    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str: ...


@dataclass(slots=True)
class QueueMessage:
    body: dict
    message_id: str = ""


@runtime_checkable
class QueueProvider(Protocol):
    name: str

    async def publish(self, body: dict) -> str: ...


@runtime_checkable
class DocparseProvider(Protocol):
    name: str

    async def parse(
        self, data: bytes, *, mime_type: str | None, filename: str
    ) -> ParsedDocument: ...


@runtime_checkable
class SecretsProvider(Protocol):
    name: str

    def get(self, key: str) -> str | None: ...


@runtime_checkable
class AuditSink(Protocol):
    name: str

    async def emit(self, event: dict) -> None: ...

 succeeded in 0ms:
// Typed fetch client for the CaptureOS API. Attaches the bearer token, understands
// the {error:{code,message,details}} contract, and never leaks raw responses.

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// The AuthProvider registers a getter so every request auto-attaches the token.
let tokenGetter: () => string | null = () => null;
export function setTokenGetter(fn: () => string | null): void {
  tokenGetter = fn;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = opts.token ?? tokenGetter();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: unknown } })
      .error ?? { code: "error", message: res.statusText };
    throw new ApiError(res.status, err.code ?? "error", err.message ?? "Request failed", err.details);
  }
  return data as T;
}

exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/lib/auth.tsx" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { apiFetch } from "./api";
import { getServerSnapshot, getSnapshot, setTokens, subscribe } from "./tokenStore";
import type { Tokens } from "./types";

// Returns false on the server + during hydration, true afterward — without setState.
const noopSubscribe = () => () => {};
function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

type AuthContextValue = {
  tokens: Tokens | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName?: string,
    orgName?: string,
  ) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const tokens = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const hydrated = useHydrated();

  const login = useCallback(async (email: string, password: string) => {
    const t = await apiFetch<Tokens>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    setTokens(t);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string, orgName?: string) => {
      const t = await apiFetch<Tokens>("/auth/register", {
        method: "POST",
        body: { email, password, fullName, orgName },
      });
      setTokens(t);
    },
    [],
  );

  const logout = useCallback(() => {
    setTokens(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      tokens,
      loading: !hydrated,
      isAuthenticated: tokens !== null,
      login,
      register,
      logout,
    }),
    [tokens, hydrated, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

exec
/bin/zsh -lc "sed -n '1,220p' apps/web/src/lib/tokenStore.ts" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
// External token store backed by localStorage, consumed via useSyncExternalStore.
// This is the React 19-idiomatic way to read browser storage without setState-in-effect
// and without hydration mismatches (getServerSnapshot returns null to match SSR).

import { setTokenGetter } from "./api";
import type { Tokens } from "./types";

const TOKEN_KEY = "captureos.tokens";
type Listener = () => void;
const listeners = new Set<Listener>();

function read(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(TOKEN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

// Stable cached snapshot (useSyncExternalStore requires reference stability).
let snapshot: Tokens | null = read();

// The api client pulls the access token synchronously from this store.
setTokenGetter(() => snapshot?.accessToken ?? null);

export function getSnapshot(): Tokens | null {
  return snapshot;
}

export function getServerSnapshot(): Tokens | null {
  return null;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setTokens(next: Tokens | null): void {
  snapshot = next;
  if (typeof window !== "undefined") {
    if (next) window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
    else window.localStorage.removeItem(TOKEN_KEY);
  }
  for (const listener of listeners) listener();
}

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/tests/test_auth.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/tests/test_org_scoping.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Org multi-tenancy: isolation (CON-5) and role enforcement (NFR-1) — the core M0 guarantee."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def _create_org(client: AsyncClient, tokens: dict, name: str) -> dict:
    resp = await client.post("/api/v1/orgs", json={"name": name}, headers=auth_headers(tokens))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_owner_can_read_own_org(client: AsyncClient) -> None:
    tokens = await register(client, "owner@example.com")
    org = await _create_org(client, tokens, "OwnerOrg")
    resp = await client.get(f"/api/v1/orgs/{org['id']}", headers=auth_headers(tokens))
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


async def test_cross_org_access_is_404_not_403(client: AsyncClient) -> None:
    """A non-member must not be able to tell the org exists (CON-5)."""
    a = await register(client, "a2@example.com")
    org = await _create_org(client, a, "AOrg")
    b = await register(client, "b2@example.com")
    resp = await client.get(f"/api/v1/orgs/{org['id']}", headers=auth_headers(b))
    assert resp.status_code == 404


async def test_unauthenticated_access_denied(client: AsyncClient) -> None:
    a = await register(client, "a3@example.com")
    org = await _create_org(client, a, "AOrg3")
    resp = await client.get(f"/api/v1/orgs/{org['id']}")
    assert resp.status_code == 401


async def test_added_member_can_read_with_their_role(client: AsyncClient) -> None:
    owner = await register(client, "own@example.com")
    org = await _create_org(client, owner, "RoleOrg")
    await register(client, "mem@example.com")
    add = await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "mem@example.com", "role": "editor"},
        headers=auth_headers(owner),
    )
    assert add.status_code == 201
    member_tokens = (
        await client.post(
            "/api/v1/auth/login", json={"email": "mem@example.com", "password": "password123"}
        )
    ).json()
    resp = await client.get(
        f"/api/v1/orgs/{org['id']}",
        headers={"Authorization": f"Bearer {member_tokens['accessToken']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


async def test_viewer_cannot_add_members(client: AsyncClient) -> None:
    owner = await register(client, "own2@example.com")
    org = await _create_org(client, owner, "RoleOrg2")
    viewer = await register(client, "view@example.com")
    await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "view@example.com", "role": "viewer"},
        headers=auth_headers(owner),
    )
    await register(client, "other@example.com")
    resp = await client.post(
        f"/api/v1/orgs/{org['id']}/members",
        json={"email": "other@example.com", "role": "viewer"},
        headers=auth_headers(viewer),
    )
    assert resp.status_code == 403


async def test_org_list_only_shows_my_orgs(client: AsyncClient) -> None:
    a = await register(client, "list_a@example.com")
    await _create_org(client, a, "MineA")
    b = await register(client, "list_b@example.com")
    await _create_org(client, b, "MineB")
    resp = await client.get("/api/v1/orgs", headers=auth_headers(a))
    assert resp.status_code == 200
    names = {o["name"] for o in resp.json()}
    assert "MineA" in names
    assert "MineB" not in names

 succeeded in 0ms:
"""Local auth flow (M0 success criterion: register/login)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, register


async def test_register_returns_tokens(client: AsyncClient) -> None:
    data = await register(client, "a@example.com", org_name="Acme")
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["tokenType"] == "bearer"


async def test_login_succeeds(client: AsyncClient) -> None:
    await register(client, "b@example.com")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "b@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


async def test_login_wrong_password_is_401(client: AsyncClient) -> None:
    await register(client, "c@example.com")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "c@example.com", "password": "nope"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_duplicate_registration_conflicts(client: AsyncClient) -> None:
    await register(client, "d@example.com")
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "d@example.com", "password": "password123"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
    tokens = await register(client, "r@example.com")
    resp = await client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


async def test_me_lists_bootstrapped_org(client: AsyncClient) -> None:
    tokens = await register(client, "e@example.com", org_name="Eorg")
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "e@example.com"
    assert any(o["name"] == "Eorg" and o["role"] == "owner" for o in body["orgs"])


async def test_me_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_short_password_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "f@example.com", "password": "short"}
    )
    assert resp.status_code == 422

exec
/bin/zsh -lc "rg -n \"record_event\\(|session_scope\\(|get_session\\(|presign_upload|presign_download|storage_uri|refresh_token|access_token|verify_password|needs_rehash|role|OrgOwner|OrgEditor|OrgViewer|localStorage|NEXT_PUBLIC|jwt_secret|decode_token|Path\\(\" apps/api apps/web" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/web/src/lib/types.ts:18:  role: string;
apps/web/src/lib/types.ts:32:  role: string | null;
apps/web/src/lib/api.ts:5:  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
apps/web/src/lib/tokenStore.ts:1:// External token store backed by localStorage, consumed via useSyncExternalStore.
apps/web/src/lib/tokenStore.ts:14:  const raw = window.localStorage.getItem(TOKEN_KEY);
apps/web/src/lib/tokenStore.ts:47:    if (next) window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
apps/web/src/lib/tokenStore.ts:48:    else window.localStorage.removeItem(TOKEN_KEY);
apps/api/captureos/providers/base.py:62:    storage_uri: str = ""
apps/api/captureos/providers/base.py:99:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
apps/api/captureos/providers/base.py:100:    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str: ...
apps/api/Dockerfile:9:# uv from the official distroless image (pinned by tag).
apps/api/tests/test_auth.py:44:async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
apps/api/tests/test_auth.py:57:    assert any(o["name"] == "Eorg" and o["role"] == "owner" for o in body["orgs"])
apps/api/captureos/providers/storage.py:25:        self._base = Path(settings.storage_local_dir).resolve()
apps/api/captureos/providers/storage.py:52:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
apps/api/captureos/providers/storage.py:58:            storage_uri=f"{_LOCAL_SCHEME}{key}",
apps/api/captureos/providers/storage.py:61:    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
apps/api/captureos/providers/storage.py:110:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
apps/api/captureos/providers/storage.py:121:            storage_uri=f"gs://{self._bucket_name}/{key}",
apps/api/captureos/providers/storage.py:124:    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
apps/api/captureos/config.py:19:_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
apps/api/captureos/config.py:91:    jwt_secret: str = "dev-only-insecure-change-me-please-32chars-min"  # noqa: S105
apps/api/captureos/config.py:176:            if "insecure" in self.jwt_secret or len(self.jwt_secret) < 32:
apps/api/tests/test_org_scoping.py:1:"""Org multi-tenancy: isolation (CON-5) and role enforcement (NFR-1) — the core M0 guarantee."""
apps/api/tests/test_org_scoping.py:21:    assert resp.json()["role"] == "owner"
apps/api/tests/test_org_scoping.py:40:async def test_added_member_can_read_with_their_role(client: AsyncClient) -> None:
apps/api/tests/test_org_scoping.py:46:        json={"email": "mem@example.com", "role": "editor"},
apps/api/tests/test_org_scoping.py:60:    assert resp.json()["role"] == "editor"
apps/api/tests/test_org_scoping.py:69:        json={"email": "view@example.com", "role": "viewer"},
apps/api/tests/test_org_scoping.py:75:        json={"email": "other@example.com", "role": "viewer"},
apps/api/captureos/schemas/org.py:23:    role: str | None = None  # the requesting user's role in this org
apps/api/captureos/schemas/org.py:31:    role: str
apps/api/captureos/schemas/org.py:36:    role: str = "viewer"
apps/api/captureos/core/deps.py:1:"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""
apps/api/captureos/core/deps.py:65:    def role(self) -> str:
apps/api/captureos/core/deps.py:66:        return self.membership.role
apps/api/captureos/core/deps.py:88:    min_role: OrgRole = OrgRole.viewer,
apps/api/captureos/core/deps.py:91:    minimum role, and returns the OrgContext. Use on every org-scoped route."""
apps/api/captureos/core/deps.py:96:        org_id: Annotated[uuid.UUID, Path()],
apps/api/captureos/core/deps.py:99:        if _ROLE_ORDER[OrgRole(ctx.membership.role)] < _ROLE_ORDER[min_role]:
apps/api/captureos/core/deps.py:100:            raise ForbiddenError(f"This action requires '{min_role.value}' role")
apps/api/captureos/core/deps.py:107:OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
apps/api/captureos/core/deps.py:108:OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]
apps/api/captureos/core/deps.py:109:OrgOwner = Annotated[OrgContext, Depends(require_org(OrgRole.owner))]
apps/api/captureos/core/security.py:23:def verify_password(plain: str, hashed: str) -> bool:
apps/api/captureos/core/security.py:30:def needs_rehash(hashed: str) -> bool:
apps/api/captureos/core/security.py:32:        return _ph.check_needs_rehash(hashed)
apps/api/captureos/core/security.py:49:    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
apps/api/captureos/core/security.py:52:def create_access_token(user_id: str | uuid.UUID, extra: dict | None = None) -> str:
apps/api/captureos/core/security.py:59:def create_refresh_token(user_id: str | uuid.UUID) -> str:
apps/api/captureos/core/security.py:64:def decode_token(token: str, *, expected_type: str | None = None) -> dict:
apps/api/captureos/core/security.py:67:        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
apps/api/captureos/api/orgs.py:9:from captureos.core.deps import CurrentUser, OrgOwner, OrgViewer, SessionDep
apps/api/captureos/api/orgs.py:23:    session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
apps/api/captureos/api/orgs.py:24:    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/orgs.py:30:        role=OrgRole.owner.value,
apps/api/captureos/api/orgs.py:38:        select(Organization, OrgMember.role)
apps/api/captureos/api/orgs.py:49:            role=role,
apps/api/captureos/api/orgs.py:52:        for org, role in result.all()
apps/api/captureos/api/orgs.py:57:async def get_org(ctx: OrgViewer) -> OrgResponse:
apps/api/captureos/api/orgs.py:64:        role=ctx.role,
apps/api/captureos/api/orgs.py:70:async def list_members(ctx: OrgViewer, session: SessionDep) -> list[OrgMemberResponse]:
apps/api/captureos/api/orgs.py:72:        select(User, OrgMember.role)
apps/api/captureos/api/orgs.py:78:        OrgMemberResponse(user_id=u.id, email=u.email, full_name=u.full_name, role=role)
apps/api/captureos/api/orgs.py:79:        for u, role in result.all()
apps/api/captureos/api/orgs.py:87:    body: InviteMemberRequest, ctx: OrgOwner, session: SessionDep
apps/api/captureos/api/orgs.py:89:    role = OrgRole(body.role).value  # validates the role string
apps/api/captureos/api/orgs.py:99:    session.add(OrgMember(org_id=ctx.org_id, user_id=target.id, role=role))
apps/api/captureos/api/orgs.py:100:    await record_event(
apps/api/captureos/api/orgs.py:105:        payload={"added_user_id": str(target.id), "role": role},
apps/api/captureos/api/orgs.py:108:        user_id=target.id, email=target.email, full_name=target.full_name, role=role
apps/api/captureos/schemas/auth.py:26:    refresh_token: str
apps/api/captureos/schemas/auth.py:30:    access_token: str
apps/api/captureos/schemas/auth.py:31:    refresh_token: str
apps/api/captureos/schemas/auth.py:49:    role: str
apps/api/captureos/providers/audit.py:58:            async with session_scope() as session:
apps/api/captureos/auth/local.py:7:from captureos.core.security import decode_token
apps/api/captureos/auth/local.py:17:        payload = decode_token(token, expected_type="access")
apps/api/tests/conftest.py:17:    for parent in Path(__file__).resolve().parents:
apps/api/captureos/models/org.py:62:    role: Mapped[str] = mapped_column(String(16), nullable=False, default=OrgRole.owner.value)
apps/web/src/app/dashboard/page.tsx:85:                  Role: {org.role} · Plan: {org.plan}
apps/api/captureos/models/documents.py:29:    storage_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
apps/api/captureos/scripts/seed.py:21:    async with session_scope() as session:
apps/api/captureos/scripts/seed.py:43:            session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
apps/api/captureos/api/auth.py:14:    create_access_token,
apps/api/captureos/api/auth.py:15:    create_refresh_token,
apps/api/captureos/api/auth.py:16:    decode_token,
apps/api/captureos/api/auth.py:18:    verify_password,
apps/api/captureos/api/auth.py:62:        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
apps/api/captureos/api/auth.py:63:        await record_event(
apps/api/captureos/api/auth.py:68:        access_token=create_access_token(user.id, extra={"email": user.email}),
apps/api/captureos/api/auth.py:69:        refresh_token=create_refresh_token(user.id),
apps/api/captureos/api/auth.py:82:        or not verify_password(body.password, user.hashed_password)
apps/api/captureos/api/auth.py:88:        access_token=create_access_token(user.id, extra={"email": user.email}),
apps/api/captureos/api/auth.py:89:        refresh_token=create_refresh_token(user.id),
apps/api/captureos/api/auth.py:96:    payload = decode_token(body.refresh_token, expected_type="refresh")
apps/api/captureos/api/auth.py:101:        access_token=create_access_token(user.id, extra={"email": user.email}),
apps/api/captureos/api/auth.py:102:        refresh_token=create_refresh_token(user.id),
apps/api/captureos/api/auth.py:114:        OrgMembershipSummary(org_id=org.id, name=org.name, role=member.role, plan=org.plan)
apps/api/captureos/db/migrate.py:12:_API_ROOT = Path(__file__).resolve().parents[2]  # apps/api
apps/api/captureos/audit/service.py:16:async def record_event(
apps/api/captureos/db/session.py:43:async def get_session() -> AsyncIterator[AsyncSession]:
apps/api/captureos/db/session.py:56:async def session_scope() -> AsyncIterator[AsyncSession]:
apps/api/migrations/versions/f28c812fca98_initial_schema.py:110:    sa.Column('storage_uri', sa.String(length=2048), nullable=True),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:129:    sa.Column('role', sa.String(length=16), nullable=False),

exec
/bin/zsh -lc "sed -n '1,320p' apps/api/tests/conftest.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Test fixtures. DDL runs on a sync engine (no event loop); the async engine is
reset per test so it lives entirely within that test's loop."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import make_url  # safe to import before captureos modules


def _configured_database_url() -> str:
    """Discover the base DATABASE_URL (explicit env, else repo-root .env), so tests
    follow whatever host/port the developer configured."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL=") and "_test" not in line:
                    return line.split("=", 1)[1].strip()
    return "postgresql+asyncpg://captureos:captureos@localhost:5433/captureos"


# --- Force test configuration BEFORE importing any captureos module ---
_url = make_url(_configured_database_url())
_dbname = _url.database or "captureos"
if not _dbname.endswith("_test"):
    _dbname = f"{_dbname}_test"
_url = _url.set(database=_dbname)
_ASYNC_URL = _url.render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = _ASYNC_URL
os.environ["DATABASE_URL_SYNC"] = _ASYNC_URL.replace("+asyncpg", "+psycopg")
os.environ.setdefault("CAPTUREOS_ENV", "ci")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDINGS_PROVIDER", "mock")
os.environ.setdefault("STORAGE_PROVIDER", "local")
os.environ.setdefault("QUEUE_PROVIDER", "local")
os.environ.setdefault("DOCPARSE_PROVIDER", "local")
os.environ.setdefault("AUDIT_SINK", "postgres")
os.environ.setdefault("AUTH_PROVIDER", "local")
os.environ.setdefault("JWT_SECRET", "test-secret-key-at-least-32-characters-long-xx")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./.data/test-blobs")

from collections.abc import AsyncIterator  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

import captureos.models  # noqa: E402, F401  (registers tables on metadata)
from captureos.db.base import Base  # noqa: E402
from captureos.db.session import get_engine, get_sessionmaker  # noqa: E402
from captureos.providers import reset_providers  # noqa: E402


def _ensure_database_exists() -> None:
    url = make_url(os.environ["DATABASE_URL_SYNC"])
    admin_conninfo = (
        f"host={url.host} port={url.port or 5432} user={url.username} "
        f"password={url.password} dbname=postgres"
    )
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')  # noqa: S608 - db name is our constant


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Create the test database + extensions + schema once (sync engine, no loop)."""
    _ensure_database_exists()
    sync_engine = create_engine(os.environ["DATABASE_URL_SYNC"], future=True)
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _isolation() -> AsyncIterator[None]:
    """Per-test: fresh async engine on this loop, truncated tables, disposed at end."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    reset_providers()

    engine = get_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield
    await engine.dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from captureos.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- helpers ----
async def register(
    client: AsyncClient, email: str, password: str = "password123", org_name: str | None = None
) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "orgName": org_name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}

exec
/bin/zsh -lc "sed -n '1,240p' apps/api/captureos/schemas/auth.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,220p' apps/api/captureos/schemas/org.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Auth request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import EmailStr, Field

from captureos.schemas.common import CamelModel


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)
    # Optionally bootstrap an organization on signup; the user becomes its owner.
    org_name: str | None = Field(default=None, max_length=255)


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(CamelModel):
    refresh_token: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - this is a token-type label, not a secret


class UserResponse(CamelModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None


class MeResponse(CamelModel):
    user: UserResponse
    orgs: list[OrgMembershipSummary]


class OrgMembershipSummary(CamelModel):
    org_id: uuid.UUID
    name: str
    role: str
    plan: str


MeResponse.model_rebuild()

 succeeded in 0ms:
"""Organization request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from captureos.schemas.common import CamelModel


class OrgCreate(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    uei: str | None = Field(default=None, max_length=32)


class OrgResponse(CamelModel):
    id: uuid.UUID
    name: str
    uei: str | None = None
    plan: str
    role: str | None = None  # the requesting user's role in this org
    created_at: datetime | None = None


class OrgMemberResponse(CamelModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None = None
    role: str


class InviteMemberRequest(CamelModel):
    email: str
    role: str = "viewer"

exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/lib/types.ts" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
// Wire types mirror the backend's camelCase responses (PRD §9).

export type Tokens = {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
};

export type User = {
  id: string;
  email: string;
  fullName: string | null;
};

export type OrgMembershipSummary = {
  orgId: string;
  name: string;
  role: string;
  plan: string;
};

export type Me = {
  user: User;
  orgs: OrgMembershipSummary[];
};

export type Org = {
  id: string;
  name: string;
  uei: string | null;
  plan: string;
  role: string | null;
  createdAt?: string;
};

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/db/base.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Declarative base, metadata naming convention, and common column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Deterministic constraint/index names → clean, reversible Alembic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrgScopedMixin:
    """Adds an indexed ``org_id`` FK (ON DELETE CASCADE). Every tenant table uses this
    so org isolation (CON-5) is uniform and queries can filter on one column."""

    @declared_attr
    def org_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(
            PGUUID(as_uuid=True),
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/billing.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,320p' apps/api/captureos/models/opportunities.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Billing & revenue (FR-BL-*) and customer feedback."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import SubscriptionStatus


class Subscription(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    product: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.active.value
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class RevenueRecord(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "revenue_records"

    product: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    charged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CustomerFeedback(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "customer_feedback"

    rating: Mapped[int | None] = mapped_column(Numeric(2, 0), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

 succeeded in 0ms:
"""Unified opportunities (gov_contract | grant | future verticals) — PRD §7.2.

A single table with a ``kind`` discriminator and a ``details`` JSONB column for
kind-specific fields (NAICS, set-aside, award ceiling, CFDA, eligibility_rules, ...).
Triage fit (FR-GC-1) is stored here; per-filing recommendations live on the filing.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import OpportunityKind


class Opportunity(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "opportunities"

    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OpportunityKind.gov_contract.value, index=True
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    sponsor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Kind-specific fields (eligibility_rules, naics, set_aside, award_ceiling, cfda, ...).
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Triage fit (FR-GC-1) — coarse pre-filing scoring from a scan.
    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    decision_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fit_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

exec
/bin/zsh -lc "sed -n '1,320p' apps/api/captureos/models/enums.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Domain enums. Stored as strings in Postgres (cheap to evolve), validated in the app.

Single source of truth for allowed values — imported by ORM models (defaults) and
Pydantic schemas (validation).
"""

from __future__ import annotations

from enum import StrEnum


class OrgPlan(StrEnum):
    free = "free"
    audit = "audit"
    sprint = "sprint"
    autopilot = "autopilot"


class OrgRole(StrEnum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


class DocumentSourceKind(StrEnum):
    upload = "upload"
    paste = "paste"
    drive_connector = "drive_connector"


class ParseStatus(StrEnum):
    pending = "pending"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


class SourceKind(StrEnum):
    sam_gov = "sam_gov"
    usaspending = "usaspending"
    grants_gov = "grants_gov"
    web = "web"
    document = "document"
    user_input = "user_input"


class EvidenceType(StrEnum):
    service = "service"
    past_performance = "past_performance"
    certification = "certification"
    fact = "fact"
    metric = "metric"


class EvidenceOrigin(StrEnum):
    inferred = "inferred"
    user_provided = "user_provided"


class OpportunityKind(StrEnum):
    gov_contract = "gov_contract"
    grant = "grant"
    # Future verticals (schema-ready, not implemented in MVP):
    permit = "permit"
    license = "license"
    certification = "certification"
    vendor_packet = "vendor_packet"
    compliance_packet = "compliance_packet"


class FilingStatus(StrEnum):
    draft = "draft"
    researching = "researching"
    evidence_review = "evidence_review"
    recommended = "recommended"
    approved = "approved"
    packaging = "packaging"
    package_review = "package_review"
    ready = "ready"
    archived = "archived"
    rejected = "rejected"


class RequirementCategory(StrEnum):
    eligibility = "eligibility"
    technical = "technical"
    past_performance = "past_performance"
    certification = "certification"
    formatting = "formatting"
    attachment = "attachment"
    other = "other"


class MatchStatus(StrEnum):
    matched = "matched"
    partial = "partial"
    missing = "missing"
    user_provided = "user_provided"


class RecommendationDecision(StrEnum):
    pursue = "pursue"
    do_not_pursue = "do_not_pursue"


class GeneratedDocType(StrEnum):
    compliance_matrix = "compliance_matrix"
    narrative = "narrative"
    capability_statement = "capability_statement"
    attachment_checklist = "attachment_checklist"
    missing_items = "missing_items"
    citation_appendix = "citation_appendix"
    proposal_outline = "proposal_outline"
    budget_checklist = "budget_checklist"
    submission_checklist = "submission_checklist"


class GeneratedDocStatus(StrEnum):
    draft = "draft"
    review = "review"
    ready = "ready"


class ApprovalTarget(StrEnum):
    recommendation = "recommendation"
    package = "package"


class ApprovalDecision(StrEnum):
    approved = "approved"
    rejected = "rejected"


class WorkflowType(StrEnum):
    company_brain = "company_brain"
    document_ingest = "document_ingest"
    opportunity_scan = "opportunity_scan"
    requirement_extraction = "requirement_extraction"
    evidence_match = "evidence_match"
    gap_resolution = "gap_resolution"
    recommendation = "recommendation"
    package_build = "package_build"


class WorkflowStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    needs_input = "needs_input"


class StepStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class AgentRunStatus(StrEnum):
    success = "success"
    retried = "retried"
    failed = "failed"


class ActorType(StrEnum):
    user = "user"
    agent = "agent"
    system = "system"


class SubscriptionStatus(StrEnum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"
    incomplete = "incomplete"


class BillingProduct(StrEnum):
    audit = "audit"
    sprint = "sprint"
    autopilot = "autopilot"

exec
/bin/zsh -lc "sed -n '1,200p' infra/db/init/01-extensions.sql" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,240p' apps/api/captureos/db/migrate.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/migrations/env.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
-- Runs once on first DB boot (docker-entrypoint-initdb.d). Idempotent.
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings (FR-DI-2/5)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4 if needed
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram search for fuzzy matching

 succeeded in 0ms:
"""Programmatic Alembic runner (used on container start when RUN_MIGRATIONS_ON_START)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from captureos.config import get_settings

_API_ROOT = Path(__file__).resolve().parents[2]  # apps/api


def _alembic_config() -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    return cfg


def apply_migrations() -> None:
    command.upgrade(_alembic_config(), "head")

 succeeded in 0ms:
"""Alembic environment. URL and metadata come from the app (single source of truth)."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importing the models package registers every table on Base.metadata.
import captureos.models  # noqa: F401
from captureos.config import get_settings
from captureos.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
target_metadata = Base.metadata


def render_item(type_: str, obj: object, autogen_context) -> str | bool:
    """Teach autogenerate to render pgvector columns with the right import."""
    if type_ == "type" and obj.__class__.__module__.startswith("pgvector"):
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        dim = getattr(obj, "dim", None)
        return f"Vector({dim})" if dim is not None else "Vector()"
    return False


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

exec
/bin/zsh -lc "sed -n '1,220p' docker-compose.yml" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
# CaptureOS local stack. `docker compose up` boots the whole system locally.
# Cloud equivalents (Cloud SQL, Cloud Run, Pub/Sub) replace these in prod via config.
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: captureos-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-captureos}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-captureos}
      POSTGRES_DB: ${POSTGRES_DB:-captureos}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-captureos} -d ${POSTGRES_DB:-captureos}"]
      interval: 5s
      timeout: 5s
      retries: 20

  api:
    build:
      context: ./apps/api
    container_name: captureos-api
    env_file: .env
    environment:
      # Inside the compose network the DB host is the service name.
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-captureos}:${POSTGRES_PASSWORD:-captureos}@db:5432/${POSTGRES_DB:-captureos}
      DATABASE_URL_SYNC: postgresql+psycopg://${POSTGRES_USER:-captureos}:${POSTGRES_PASSWORD:-captureos}@db:5432/${POSTGRES_DB:-captureos}
      RUN_MIGRATIONS_ON_START: "true"
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - ./apps/api:/app
      - blobs:/app/.data/blobs
    depends_on:
      db:
        condition: service_healthy
    command: ["uvicorn", "captureos.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  worker:
    build:
      context: ./apps/api
    container_name: captureos-worker
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-captureos}:${POSTGRES_PASSWORD:-captureos}@db:5432/${POSTGRES_DB:-captureos}
      DATABASE_URL_SYNC: postgresql+psycopg://${POSTGRES_USER:-captureos}:${POSTGRES_PASSWORD:-captureos}@db:5432/${POSTGRES_DB:-captureos}
    volumes:
      - ./apps/api:/app
      - blobs:/app/.data/blobs
    depends_on:
      db:
        condition: service_healthy
    command: ["python", "-m", "captureos.worker.main"]

  web:
    build:
      context: ./apps/web
    container_name: captureos-web
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
      NEXT_PUBLIC_AUTH_PROVIDER: local
    ports:
      - "3000:3000"
    depends_on:
      - api
    profiles: ["full"]   # `docker compose --profile full up` to include web; otherwise run `pnpm dev` locally.

volumes:
  pgdata:
  blobs:

exec
/bin/zsh -lc "rg -n \"execute\\(|text\\(|f\\\".*SELECT|f\\\".*INSERT|f\\\".*UPDATE|f\\\".*DELETE|open\\(|write_bytes|read_bytes|unlink\\(|Path\\(|localStorage|dangerouslySetInnerHTML|eval\\(|subprocess|pickle|yaml.load\" apps/api apps/web" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/web/src/lib/tokenStore.ts:1:// External token store backed by localStorage, consumed via useSyncExternalStore.
apps/web/src/lib/tokenStore.ts:14:  const raw = window.localStorage.getItem(TOKEN_KEY);
apps/web/src/lib/tokenStore.ts:47:    if (next) window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
apps/web/src/lib/tokenStore.ts:48:    else window.localStorage.removeItem(TOKEN_KEY);
apps/api/captureos/api/orgs.py:37:    result = await session.execute(
apps/api/captureos/api/orgs.py:71:    result = await session.execute(
apps/api/captureos/api/orgs.py:90:    result = await session.execute(select(User).where(User.email == body.email.lower()))
apps/api/captureos/api/orgs.py:94:    existing = await session.execute(
apps/api/captureos/db/migrate.py:12:_API_ROOT = Path(__file__).resolve().parents[2]  # apps/api
apps/api/captureos/core/deps.py:41:        result = await session.execute(
apps/api/captureos/core/deps.py:73:async def _load_org_context(org_id: uuid.UUID, user: User, session: AsyncSession) -> OrgContext:
apps/api/captureos/core/deps.py:78:    result = await session.execute(
apps/api/captureos/core/deps.py:84:    return OrgContext(user=user, organization=org, membership=membership)
apps/api/captureos/core/deps.py:96:        org_id: Annotated[uuid.UUID, Path()],
apps/api/captureos/core/deps.py:98:        ctx = await _load_org_context(org_id, user, session)
apps/api/captureos/api/health.py:25:    await session.execute(text("SELECT 1"))
apps/web/src/lib/auth.tsx:85:  const ctx = useContext(AuthContext);
apps/api/captureos/config.py:19:_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
apps/api/captureos/api/auth.py:46:    existing = await session.execute(select(User).where(User.email == body.email.lower()))
apps/api/captureos/api/auth.py:76:    result = await session.execute(select(User).where(User.email == body.email.lower()))
apps/api/captureos/api/auth.py:108:    result = await session.execute(
apps/api/captureos/providers/storage.py:25:        self._base = Path(settings.storage_local_dir).resolve()
apps/api/captureos/providers/storage.py:38:        path.write_bytes(data)
apps/api/captureos/providers/storage.py:42:        return self._path(_key_from_uri(uri)).read_bytes()
apps/api/captureos/providers/storage.py:47:            path.unlink()
apps/api/migrations/versions/f28c812fca98_initial_schema.py:24:    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
apps/api/migrations/versions/f28c812fca98_initial_schema.py:25:    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
apps/api/migrations/versions/f28c812fca98_initial_schema.py:32:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:33:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:43:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:44:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:63:    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:79:    sa.Column('services', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:80:    sa.Column('naics_guesses', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:81:    sa.Column('funding_categories', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:82:    sa.Column('target_customers', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:83:    sa.Column('certifications', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:84:    sa.Column('missing_fields', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:85:    sa.Column('user_overrides', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:89:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:90:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:102:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:103:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:118:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:119:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:131:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:132:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:146:    sa.Column('charged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:149:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:150:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:165:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:166:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:180:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:181:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:196:    sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:199:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:200:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:216:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:217:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:233:    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:240:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:241:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:257:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:258:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:275:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:276:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:294:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:295:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:314:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:315:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:331:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:332:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:344:    sa.Column('input_params', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:345:    sa.Column('partial_results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:352:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:353:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:370:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:371:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:390:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:391:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:412:    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/migrations/versions/f28c812fca98_initial_schema.py:413:    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
apps/api/captureos/scripts/seed.py:22:        result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
apps/api/captureos/scripts/seed.py:34:        result = await session.execute(
apps/api/captureos/models/workflow.py:37:        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
apps/api/captureos/models/workflow.py:40:        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
apps/api/captureos/providers/docparse.py:39:            ParsedPage(page=i + 1, text=(p.extract_text() or ""))
apps/api/captureos/models/company.py:11:_EMPTY_LIST = text("'[]'::jsonb")
apps/api/captureos/models/company.py:12:_EMPTY_OBJ = text("'{}'::jsonb")
apps/api/captureos/models/opportunities.py:41:        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
apps/api/tests/conftest.py:17:    for parent in Path(__file__).resolve().parents:
apps/api/tests/conftest.py:20:            for line in env_file.read_text().splitlines():
apps/api/tests/conftest.py:69:        exists = conn.execute(
apps/api/tests/conftest.py:73:            conn.execute(f'CREATE DATABASE "{url.database}"')  # noqa: S608 - db name is our constant
apps/api/tests/conftest.py:82:        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
apps/api/tests/conftest.py:83:        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
apps/api/tests/conftest.py:99:        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/app/dashboard/page.tsx" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/app/login/page.tsx" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Me, Org } from "@/lib/types";

export default function DashboardPage() {
  const { isAuthenticated, loading, logout } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [orgName, setOrgName] = useState("");

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<Me>("/auth/me"),
    enabled: isAuthenticated,
  });

  const createOrg = useMutation({
    mutationFn: (name: string) => apiFetch<Org>("/orgs", { method: "POST", body: { name } }),
    onSuccess: () => {
      setOrgName("");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  function onCreateOrg(e: FormEvent) {
    e.preventDefault();
    if (orgName.trim()) createOrg.mutate(orgName.trim());
  }

  if (loading || !isAuthenticated) {
    return <main className="grid min-h-screen place-items-center text-neutral-500">Loading…</main>;
  }

  const me = meQuery.data;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">CaptureOS</h1>
          <p className="text-sm text-neutral-500">
            {me ? `Signed in as ${me.user.email}` : "Loading your account…"}
          </p>
        </div>
        <button
          onClick={() => {
            logout();
            router.replace("/login");
          }}
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100"
        >
          Sign out
        </button>
      </header>

      <section className="mt-8">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Your organizations
        </h2>

        {meQuery.isLoading && <p className="mt-3 text-sm text-neutral-500">Loading…</p>}
        {meQuery.isError && (
          <p className="mt-3 text-sm text-red-600">Could not load organizations.</p>
        )}

        <ul className="mt-3 space-y-2">
          {me?.orgs.map((org) => (
            <li
              key={org.orgId}
              className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-4 py-3"
            >
              <div>
                <p className="font-medium">{org.name}</p>
                <p className="text-xs text-neutral-500">
                  Role: {org.role} · Plan: {org.plan}
                </p>
              </div>
              <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-xs text-neutral-600">
                {org.orgId.slice(0, 8)}
              </span>
            </li>
          ))}
          {me && me.orgs.length === 0 && (
            <li className="rounded-xl border border-dashed border-neutral-300 px-4 py-6 text-center text-sm text-neutral-500">
              No organizations yet. Create one below to get started.
            </li>
          )}
        </ul>

        <form onSubmit={onCreateOrg} className="mt-4 flex gap-2">
          <input
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="New organization name"
            className="flex-1 rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900"
          />
          <button
            type="submit"
            disabled={createOrg.isPending || !orgName.trim()}
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {createOrg.isPending ? "Creating…" : "Create"}
          </button>
        </form>
        {createOrg.isError && (
          <p className="mt-2 text-sm text-red-600">Could not create organization.</p>
        )}
      </section>

      <footer className="mt-12 rounded-xl border border-neutral-200 bg-white p-4 text-sm text-neutral-500">
        Foundation (M0) is live. Company Brain, opportunity scanning, and filing packages
        arrive in the next milestones.
      </footer>
    </main>
  );
}

 succeeded in 0ms:
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Mode = "login" | "register";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, fullName || undefined, orgName || undefined);
      }
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <div className="w-full max-w-sm rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold tracking-tight">CaptureOS</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {mode === "login" ? "Sign in to your account" : "Create your account"}
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          {mode === "register" && (
            <Field
              label="Full name"
              value={fullName}
              onChange={setFullName}
              placeholder="Jane Doe"
            />
          )}
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@company.com"
            required
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            required
          />
          {mode === "register" && (
            <Field
              label="Organization (optional)"
              value={orgName}
              onChange={setOrgName}
              placeholder="Acme LLC"
            />
          )}

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-50"
          >
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-center text-sm text-neutral-500 hover:text-neutral-900"
        >
          {mode === "login"
            ? "Need an account? Sign up"
            : "Already have an account? Sign in"}
        </button>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-neutral-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900"
      />
    </label>
  );
}

exec
/bin/zsh -lc "sed -n '1,260p' apps/web/src/lib/providers.tsx" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { AuthProvider } from "./auth";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false, staleTime: 10_000 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

exec
/bin/zsh -lc "sed -n '1,280p' apps/api/captureos/providers/llm.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""LLM providers: deterministic Mock (default, offline) and Gemini (prod)."""

from __future__ import annotations

import hashlib
import json

from captureos.config import Settings
from captureos.providers.base import LLMProvider, LLMResponse, ModelTier


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockLLM(LLMProvider):
    """Deterministic LLM for offline dev/test/CI. Same input → same output.

    Agents generally call their own ``mock()`` path in mock mode to produce rich,
    domain-shaped data; this provider is the generic fallback and exercises the
    LLMResponse/token-accounting contract end-to-end.
    """

    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse:
        digest = hashlib.sha256(f"{system or ''}\n{prompt}".encode()).hexdigest()[:12]
        if json_schema is not None:
            text = json.dumps({"_mock": True, "digest": digest})
        else:
            text = f"[mock:{tier.value}] deterministic response {digest}"
        model = (
            self._settings.gemini_model_pro
            if tier is ModelTier.pro
            else self._settings.gemini_model_flash
        )
        return LLMResponse(
            text=text,
            model=f"mock/{model}",
            input_tokens=_est_tokens((system or "") + prompt),
            output_tokens=_est_tokens(text),
        )


class GeminiLLM(LLMProvider):
    """Google Gemini via the google-genai SDK (installed with the `gcp` extra)."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        self._settings = settings
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only in prod images
            raise RuntimeError(
                "google-genai not installed. Install the `gcp` extra: uv sync --extra gcp"
            ) from exc
        self._genai = genai
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _model_for(self, tier: ModelTier) -> str:
        return (
            self._settings.gemini_model_pro
            if tier is ModelTier.pro
            else self._settings.gemini_model_flash
        )

    async def generate(
        self,
        prompt: str,
        *,
        tier: ModelTier = ModelTier.flash,
        system: str | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> LLMResponse:  # pragma: no cover - requires live credentials
        from google.genai import types  # type: ignore

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if json_schema else None,
            response_schema=json_schema,
        )
        model = self._model_for(tier)
        # google-genai is sync; run off the event loop.
        import anyio

        resp = await anyio.to_thread.run_sync(
            lambda: self._client.models.generate_content(
                model=model, contents=prompt, config=config
            )
        )
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "",
            model=model,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/providers/docparse.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/providers/embeddings.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Embeddings providers: deterministic Mock (default) and Gemini (prod).

Mock vectors are deterministic unit vectors derived from a hash of the text, so cosine
similarity is stable and meaningful for tests (identical text → identical vector,
similar text → not necessarily similar; good enough for plumbing + idempotency tests).
"""

from __future__ import annotations

import hashlib
import math

from captureos.config import Settings
from captureos.providers.base import EmbeddingResult, EmbeddingsProvider


class MockEmbeddings(EmbeddingsProvider):
    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self.dim = settings.embedding_dim
        self._model = settings.embedding_model

    def _vector(self, text: str) -> list[float]:
        # Expand a sha256 digest into `dim` deterministic floats, then L2-normalize.
        raw = bytearray()
        counter = 0
        while len(raw) < self.dim * 2:
            raw += hashlib.sha256(f"{counter}:{text}".encode()).digest()
            counter += 1
        vals = [
            (int.from_bytes(raw[i : i + 2], "big") / 65535.0) - 0.5
            for i in range(0, self.dim * 2, 2)
        ][: self.dim]
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._vector(t) for t in texts],
            model=f"mock/{self._model}",
            dim=self.dim,
        )


class GeminiEmbeddings(EmbeddingsProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY required when EMBEDDINGS_PROVIDER=gemini")
        self.dim = settings.embedding_dim
        self._model = settings.embedding_model
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("google-genai not installed (uv sync --extra gcp)") from exc
        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def embed(self, texts: list[str]) -> EmbeddingResult:  # pragma: no cover - live creds
        import anyio
        from google.genai import types  # type: ignore

        resp = await anyio.to_thread.run_sync(
            lambda: self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=self.dim),
            )
        )
        vectors = [list(e.values) for e in resp.embeddings]
        return EmbeddingResult(vectors=vectors, model=self._model, dim=self.dim)

 succeeded in 0ms:
"""Document parsing: LocalDocparse (pdf/docx/text, default) and DocAIDocparse (prod).

PDF/DOCX parsing uses the `docparse` extra (pypdf, python-docx). Plain text always works.
"""

from __future__ import annotations

import io

from captureos.config import Settings
from captureos.providers.base import DocparseProvider, ParsedDocument, ParsedPage


class LocalDocparse(DocparseProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def parse(self, data: bytes, *, mime_type: str | None, filename: str) -> ParsedDocument:
        lname = filename.lower()
        mt = (mime_type or "").lower()

        if "pdf" in mt or lname.endswith(".pdf"):
            return self._parse_pdf(data)
        if "word" in mt or lname.endswith((".docx", ".doc")):
            return self._parse_docx(data)
        # Fallback: treat as UTF-8 text (also handles pasted solicitation text, FR-DI-3).
        text = data.decode("utf-8", errors="replace")
        return ParsedDocument(text=text, pages=[ParsedPage(page=1, text=text)], page_count=1)

    def _parse_pdf(self, data: bytes) -> ParsedDocument:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pypdf not installed (uv sync --extra docparse)") from exc
        reader = PdfReader(io.BytesIO(data))
        pages = [
            ParsedPage(page=i + 1, text=(p.extract_text() or ""))
            for i, p in enumerate(reader.pages)
        ]
        return ParsedDocument(
            text="\n\n".join(p.text for p in pages), pages=pages, page_count=len(pages)
        )

    def _parse_docx(self, data: bytes) -> ParsedDocument:
        try:
            import docx  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("python-docx not installed (uv sync --extra docparse)") from exc
        document = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in document.paragraphs)
        return ParsedDocument(text=text, pages=[ParsedPage(page=1, text=text)], page_count=1)


class DocAIDocparse(DocparseProvider):  # pragma: no cover - requires GCP credentials
    name = "docai"

    def __init__(self, settings: Settings) -> None:
        if not settings.docai_processor_id:
            raise RuntimeError("DOCAI_PROCESSOR_ID required when DOCPARSE_PROVIDER=docai")
        self._settings = settings

    async def parse(self, data: bytes, *, mime_type: str | None, filename: str) -> ParsedDocument:
        import anyio
        from google.cloud import documentai  # type: ignore

        def _run() -> ParsedDocument:
            client = documentai.DocumentProcessorServiceClient()
            raw = documentai.RawDocument(content=data, mime_type=mime_type or "application/pdf")
            request = documentai.ProcessRequest(
                name=self._settings.docai_processor_id, raw_document=raw
            )
            result = client.process_document(request=request)
            doc = result.document
            pages = [ParsedPage(page=i + 1, text=doc.text) for i in range(len(doc.pages))]
            return ParsedDocument(text=doc.text, pages=pages, page_count=len(doc.pages))

        return await anyio.to_thread.run_sync(_run)

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/providers/queue.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Queue providers.

M0 ships the interface + a single-process in-memory ``LocalQueue`` (nothing dispatches
async work until the workflow engine lands in M2, which replaces this with a durable
DB-backed queue) and a ``PubSubQueue`` for production.
"""

from __future__ import annotations

import uuid
from collections import deque

from captureos.config import Settings
from captureos.logging import get_logger
from captureos.providers.base import QueueProvider

logger = get_logger(__name__)


class LocalQueue(QueueProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._buffer: deque[dict] = deque()

    async def publish(self, body: dict) -> str:
        message_id = str(uuid.uuid4())
        self._buffer.append({"message_id": message_id, **body})
        logger.debug("queue.publish", provider="local", message_id=message_id)
        return message_id

    def drain(self) -> list[dict]:
        items = list(self._buffer)
        self._buffer.clear()
        return items


class PubSubQueue(QueueProvider):  # pragma: no cover - requires GCP credentials
    name = "pubsub"

    def __init__(self, settings: Settings) -> None:
        if not settings.pubsub_project_id:
            raise RuntimeError("PUBSUB_PROJECT_ID required when QUEUE_PROVIDER=pubsub")
        try:
            from google.cloud import pubsub_v1  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-pubsub not installed (uv sync --extra gcp)") from exc
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(
            settings.pubsub_project_id, settings.pubsub_topic
        )

    async def publish(self, body: dict) -> str:
        import json

        import anyio

        future = self._publisher.publish(self._topic_path, json.dumps(body).encode())
        return await anyio.to_thread.run_sync(future.result)

exec
/bin/zsh -lc "rg -n \"get_secrets\\(|SecretsProvider|secrets_backend|gemini_api_key|stripe_secret_key|sam_gov_api_key|firebase_project_id|google_application_credentials\" apps/api" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/providers/base.py:126:class SecretsProvider(Protocol):
apps/api/captureos/config.py:95:    firebase_project_id: str | None = None
apps/api/captureos/config.py:96:    google_application_credentials: str | None = None
apps/api/captureos/config.py:106:    gemini_api_key: str | None = None
apps/api/captureos/config.py:138:    secrets_backend: SecretsBackendName = SecretsBackendName.env
apps/api/captureos/config.py:143:    stripe_secret_key: str | None = None
apps/api/captureos/config.py:150:    sam_gov_api_key: str | None = None
apps/api/captureos/config.py:180:            if self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id:
apps/api/captureos/config.py:182:            if self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key:
apps/api/captureos/providers/secrets.py:11:from captureos.providers.base import SecretsProvider
apps/api/captureos/providers/secrets.py:14:class EnvSecrets(SecretsProvider):
apps/api/captureos/providers/secrets.py:27:class GCPSecretManager(SecretsProvider):  # pragma: no cover - requires GCP credentials
apps/api/captureos/providers/embeddings.py:50:        if not settings.gemini_api_key:
apps/api/captureos/providers/embeddings.py:58:        self._client = genai.Client(api_key=settings.gemini_api_key)
apps/api/captureos/providers/llm.py:63:        if not settings.gemini_api_key:
apps/api/captureos/providers/llm.py:73:        self._client = genai.Client(api_key=settings.gemini_api_key)
apps/api/captureos/auth/firebase.py:21:                credentials.Certificate(settings.google_application_credentials)
apps/api/captureos/auth/firebase.py:22:                if settings.google_application_credentials
apps/api/captureos/auth/firebase.py:25:            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
apps/api/captureos/providers/__init__.py:30:    SecretsProvider,
apps/api/captureos/providers/__init__.py:47:    "SecretsProvider",
apps/api/captureos/providers/__init__.py:101:def get_secrets(settings: Settings | None = None) -> SecretsProvider:
apps/api/captureos/providers/__init__.py:103:    if s.secrets_backend is SecretsBackendName.gcp_secret_manager:

codex
I have a few likely defects already, but I’m checking the remaining models for cross-tenant FK integrity and migration drift before locking the review down.
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/evidence.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/models/__init__.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""All ORM models. Importing this package registers every table on ``Base.metadata``
(required for Alembic autogenerate and ``create_all``)."""

from captureos.db.base import Base
from captureos.models.audit import AuditEvent
from captureos.models.billing import CustomerFeedback, RevenueRecord, Subscription
from captureos.models.company import CompanyProfile
from captureos.models.documents import Document, DocumentChunk
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.filings import (
    Approval,
    EvidenceMatch,
    Filing,
    FilingRequirement,
    GeneratedDocument,
    Recommendation,
)
from captureos.models.opportunities import Opportunity
from captureos.models.org import Organization, OrgMember, User
from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep

__all__ = [
    "Base",
    "AuditEvent",
    "CustomerFeedback",
    "RevenueRecord",
    "Subscription",
    "CompanyProfile",
    "Document",
    "DocumentChunk",
    "EvidenceItem",
    "Source",
    "Approval",
    "EvidenceMatch",
    "Filing",
    "FilingRequirement",
    "GeneratedDocument",
    "Recommendation",
    "Opportunity",
    "OrgMember",
    "Organization",
    "User",
    "AgentRun",
    "WorkflowRun",
    "WorkflowStep",
]

 succeeded in 0ms:
"""Sources and the Evidence Vault (FR-CB-4, FR-DI-5, CON-2).

A ``Source`` is anything a claim can cite (a fetched URL, a document, user input).
An ``EvidenceItem`` is an atomic, sourced fact reusable across filings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from captureos.models.enums import EvidenceOrigin, EvidenceType, SourceKind


class Source(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceKind.web.value)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Cached content snapshot for auditability (FR-OD-3); a storage URI.
    snapshot_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvidenceItem(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "evidence_items"

    type: Mapped[str] = mapped_column(String(32), nullable=False, default=EvidenceType.fact.value)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Every evidence item must trace to a source (CON-2).
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceOrigin.inferred.value
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    # Optional pointer to the chunk this fact was derived from (locator resolution).
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/api/health.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "sed -n '1,260p' apps/api/captureos/worker/main.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
"""Worker entrypoint.

M0: a stub that stays alive so the compose topology is complete. M2 replaces the loop
body with durable queue consumption (claim step → run agent → record audit → advance run).
"""

from __future__ import annotations

import anyio

from captureos.logging import configure_logging, get_logger


async def run() -> None:
    configure_logging()
    logger = get_logger("worker")
    logger.info("worker.start", note="M0 stub — durable queue consumption arrives in M2")
    while True:  # noqa: ASYNC110 - idle stub loop; replaced by queue consumption in M2
        await anyio.sleep(5)  # pragma: no cover


def main() -> None:
    anyio.run(run)


if __name__ == "__main__":
    main()

 succeeded in 0ms:
"""Health/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from captureos import __version__
from captureos.config import get_settings
from captureos.core.deps import SessionDep
from captureos.schemas.common import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    settings = get_settings()
    return Health(status="ok", version=__version__, environment=settings.captureos_env.value)


@router.get("/readyz", response_model=Health)
async def readyz(session: SessionDep) -> Health:
    """Readiness: confirms the database is reachable."""
    await session.execute(text("SELECT 1"))
    settings = get_settings()
    return Health(status="ready", version=__version__, environment=settings.captureos_env.value)

exec
/bin/zsh -lc "rg -n \"ForeignKey\\(\" apps/api/captureos/models | sed -n '1,200p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/models/audit.py:32:        ForeignKey("organizations.id", ondelete="CASCADE"),
apps/api/captureos/models/documents.py:61:        ForeignKey("documents.id", ondelete="CASCADE"),
apps/api/captureos/models/org.py:52:        ForeignKey("organizations.id", ondelete="CASCADE"),
apps/api/captureos/models/org.py:58:        ForeignKey("users.id", ondelete="CASCADE"),
apps/api/captureos/models/evidence.py:27:        ForeignKey("documents.id", ondelete="SET NULL"),
apps/api/captureos/models/evidence.py:47:        ForeignKey("sources.id", ondelete="CASCADE"),
apps/api/captureos/models/evidence.py:58:        ForeignKey("document_chunks.id", ondelete="SET NULL"),
apps/api/captureos/models/opportunities.py:35:        ForeignKey("sources.id", ondelete="SET NULL"),
apps/api/captureos/models/workflow.py:26:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/workflow.py:59:        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
apps/api/captureos/models/workflow.py:81:        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:30:        ForeignKey("opportunities.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:39:        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
apps/api/captureos/models/filings.py:64:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:75:        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
apps/api/captureos/models/filings.py:89:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:95:        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:101:        ForeignKey("evidence_items.id", ondelete="SET NULL"),
apps/api/captureos/models/filings.py:120:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:142:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:168:        ForeignKey("filings.id", ondelete="CASCADE"),
apps/api/captureos/models/filings.py:176:        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True

codex
I’m doing one verification pass with the existing auth/org tests. If the local Postgres fixture isn’t available here, I’ll call that out explicitly and keep the review source-based.
exec
/bin/zsh -lc 'pytest apps/api/tests/test_auth.py apps/api/tests/test_org_scoping.py -q' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 194ms:
Traceback (most recent call last):
  File "/opt/homebrew/bin/pytest", line 7, in <module>
    sys.exit(console_main())
             ~~~~~~~~~~~~^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 201, in console_main
    code = main()
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 156, in main
    config = _prepareconfig(args, plugins)
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 342, in _prepareconfig
    config = pluginmanager.hook.pytest_cmdline_parse(
        pluginmanager=pluginmanager, args=args
    )
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/helpconfig.py", line 112, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1146, in pytest_cmdline_parse
    self.parse(args)
    ~~~~~~~~~~^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1527, in parse
    self._preparse(args, addopts=addopts)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/config/__init__.py", line 1431, in _preparse
    self.hook.pytest_load_initial_conftests(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        early_config=self, args=args, parser=self._parser
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
    ~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/warnings.py", line 129, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ~~~~^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ~~~~~~~~~^^^
  File "/opt/homebrew/lib/python3.13/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 632, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 126, in _sanitize_params
    dir = gettempdir()
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ~~~~~~~~~~~^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
                            "No usable temporary directory found in %s" %
                            dirlist)
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/t9/rtyzkh6s4pj6wmv4khhgyb840000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/anishguntreddi/Documents/hackathon']

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/storage.py | sed -n '1,120p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/audit.py | sed -n '1,140p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Audit sinks (CON-3, FR-AU-2/5).
     2	
     3	PostgresAuditSink writes append-only rows in its own transaction so audit durability is
     4	decoupled from the business transaction. BigQueryAuditSink is the production stream.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	
    11	from captureos.config import Settings
    12	from captureos.logging import get_logger
    13	from captureos.providers.base import AuditSink
    14	
    15	logger = get_logger(__name__)
    16	
    17	_UUID_FIELDS = ("org_id", "filing_id", "run_id", "step_id")
    18	_ALLOWED = {
    19	    "org_id",
    20	    "filing_id",
    21	    "run_id",
    22	    "step_id",
    23	    "actor",
    24	    "actor_id",
    25	    "action",
    26	    "source_url",
    27	    "model",
    28	    "input_tokens",
    29	    "output_tokens",
    30	    "latency_ms",
    31	    "status",
    32	    "payload",
    33	}
    34	
    35	
    36	def _coerce(event: dict) -> dict:
    37	    out: dict = {k: v for k, v in event.items() if k in _ALLOWED}
    38	    for field in _UUID_FIELDS:
    39	        val = out.get(field)
    40	        if isinstance(val, str):
    41	            out[field] = uuid.UUID(val)
    42	    out.setdefault("payload", {})
    43	    return out
    44	
    45	
    46	class PostgresAuditSink(AuditSink):
    47	    name = "postgres"
    48	
    49	    def __init__(self, settings: Settings) -> None:
    50	        self._settings = settings
    51	
    52	    async def emit(self, event: dict) -> None:
    53	        from captureos.db.session import session_scope
    54	        from captureos.models.audit import AuditEvent
    55	
    56	        data = _coerce(event)
    57	        try:
    58	            async with session_scope() as session:
    59	                session.add(AuditEvent(**data))
    60	        except Exception as exc:  # audit must never break the caller
    61	            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))
    62	
    63	
    64	class BigQueryAuditSink(AuditSink):  # pragma: no cover - requires GCP credentials
    65	    name = "bigquery"
    66	
    67	    def __init__(self, settings: Settings) -> None:
    68	        if not settings.gcp_project_id:
    69	            raise RuntimeError("GCP_PROJECT_ID required when AUDIT_SINK=bigquery")
    70	        try:
    71	            from google.cloud import bigquery  # type: ignore
    72	        except ImportError as exc:
    73	            raise RuntimeError("google-cloud-bigquery not installed (uv sync --extra gcp)") from exc
    74	        self._settings = settings
    75	        self._client = bigquery.Client(project=settings.gcp_project_id)
    76	        self._table = (
    77	            f"{settings.gcp_project_id}.{settings.bigquery_dataset}.{settings.bigquery_table}"
    78	        )
    79	
    80	    async def emit(self, event: dict) -> None:
    81	        import anyio
    82	
    83	        row = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in event.items()}
    84	        errors = await anyio.to_thread.run_sync(
    85	            lambda: self._client.insert_rows_json(self._table, [row])
    86	        )
    87	        if errors:
    88	            logger.error("audit.bigquery_insert_failed", errors=str(errors))

 succeeded in 0ms:
     1	"""Blob storage: LocalStorage (filesystem, default) and GCSStorage (prod).
     2	
     3	Security: keys are sanitized to prevent path traversal outside the base dir (NFR-2).
     4	URIs use a ``local://<key>`` or ``gs://<bucket>/<key>`` scheme.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from pathlib import Path
    10	
    11	from captureos.config import Settings
    12	from captureos.providers.base import PresignedUpload, StorageProvider, StoredBlob
    13	
    14	_LOCAL_SCHEME = "local://"
    15	
    16	
    17	def _key_from_uri(uri: str) -> str:
    18	    return uri[len(_LOCAL_SCHEME) :] if uri.startswith(_LOCAL_SCHEME) else uri
    19	
    20	
    21	class LocalStorage(StorageProvider):
    22	    name = "local"
    23	
    24	    def __init__(self, settings: Settings) -> None:
    25	        self._base = Path(settings.storage_local_dir).resolve()
    26	        self._base.mkdir(parents=True, exist_ok=True)
    27	
    28	    def _path(self, key: str) -> Path:
    29	        # Reject traversal: the resolved path must stay under the base dir.
    30	        candidate = (self._base / key.lstrip("/")).resolve()
    31	        if not str(candidate).startswith(str(self._base)):
    32	            raise ValueError(f"Illegal storage key (path traversal): {key!r}")
    33	        return candidate
    34	
    35	    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
    36	        path = self._path(key)
    37	        path.parent.mkdir(parents=True, exist_ok=True)
    38	        path.write_bytes(data)
    39	        return StoredBlob(uri=f"{_LOCAL_SCHEME}{key}", size=len(data))
    40	
    41	    async def get(self, uri: str) -> bytes:
    42	        return self._path(_key_from_uri(uri)).read_bytes()
    43	
    44	    async def delete(self, uri: str) -> None:
    45	        path = self._path(_key_from_uri(uri))
    46	        if path.exists():
    47	            path.unlink()
    48	
    49	    async def exists(self, uri: str) -> bool:
    50	        return self._path(_key_from_uri(uri)).exists()
    51	
    52	    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
    53	        # The backend hosts the upload route for local storage (added in M1).
    54	        return PresignedUpload(
    55	            url=f"/api/v1/blobs/{key}",
    56	            method="PUT",
    57	            headers={"content-type": content_type} if content_type else {},
    58	            storage_uri=f"{_LOCAL_SCHEME}{key}",
    59	        )
    60	
    61	    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
    62	        return f"/api/v1/blobs/{_key_from_uri(uri)}"
    63	
    64	
    65	class GCSStorage(StorageProvider):  # pragma: no cover - requires GCP credentials
    66	    name = "gcs"
    67	
    68	    def __init__(self, settings: Settings) -> None:
    69	        if not settings.gcs_bucket:
    70	            raise RuntimeError("GCS_BUCKET required when STORAGE_PROVIDER=gcs")
    71	        try:
    72	            from google.cloud import storage  # type: ignore
    73	        except ImportError as exc:
    74	            raise RuntimeError("google-cloud-storage not installed (uv sync --extra gcp)") from exc
    75	        self._bucket_name = settings.gcs_bucket
    76	        self._client = storage.Client()
    77	        self._bucket = self._client.bucket(settings.gcs_bucket)
    78	
    79	    def _key_from_uri(self, uri: str) -> str:
    80	        prefix = f"gs://{self._bucket_name}/"
    81	        return uri[len(prefix) :] if uri.startswith(prefix) else uri
    82	
    83	    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
    84	        import anyio
    85	
    86	        blob = self._bucket.blob(key)
    87	        await anyio.to_thread.run_sync(
    88	            lambda: blob.upload_from_string(data, content_type=content_type)
    89	        )
    90	        return StoredBlob(uri=f"gs://{self._bucket_name}/{key}", size=len(data))
    91	
    92	    async def get(self, uri: str) -> bytes:
    93	        import anyio
    94	
    95	        blob = self._bucket.blob(self._key_from_uri(uri))
    96	        return await anyio.to_thread.run_sync(blob.download_as_bytes)
    97	
    98	    async def delete(self, uri: str) -> None:
    99	        import anyio
   100	
   101	        blob = self._bucket.blob(self._key_from_uri(uri))
   102	        await anyio.to_thread.run_sync(blob.delete)
   103	
   104	    async def exists(self, uri: str) -> bool:
   105	        import anyio
   106	
   107	        blob = self._bucket.blob(self._key_from_uri(uri))
   108	        return await anyio.to_thread.run_sync(blob.exists)
   109	
   110	    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
   111	        from datetime import timedelta
   112	
   113	        blob = self._bucket.blob(key)
   114	        url = blob.generate_signed_url(
   115	            version="v4", expiration=timedelta(minutes=15), method="PUT", content_type=content_type
   116	        )
   117	        return PresignedUpload(
   118	            url=url,
   119	            method="PUT",
   120	            headers={"content-type": content_type} if content_type else {},

exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/orgs.py | sed -n '1,140p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Organization routes. ``GET /orgs/{org_id}`` is the M0 org-scoping acceptance test."""
     2	
     3	from __future__ import annotations
     4	
     5	from fastapi import APIRouter, status
     6	from sqlalchemy import select
     7	
     8	from captureos.audit import record_event
     9	from captureos.core.deps import CurrentUser, OrgOwner, OrgViewer, SessionDep
    10	from captureos.core.errors import ConflictError, NotFoundError
    11	from captureos.models.enums import ActorType, OrgRole
    12	from captureos.models.org import Organization, OrgMember, User
    13	from captureos.schemas.org import InviteMemberRequest, OrgCreate, OrgMemberResponse, OrgResponse
    14	
    15	router = APIRouter(prefix="/orgs", tags=["orgs"])
    16	
    17	
    18	@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
    19	async def create_org(body: OrgCreate, user: CurrentUser, session: SessionDep) -> OrgResponse:
    20	    org = Organization(name=body.name, uei=body.uei)
    21	    session.add(org)
    22	    await session.flush()
    23	    session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
    24	    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
    25	    return OrgResponse(
    26	        id=org.id,
    27	        name=org.name,
    28	        uei=org.uei,
    29	        plan=org.plan,
    30	        role=OrgRole.owner.value,
    31	        created_at=org.created_at,
    32	    )
    33	
    34	
    35	@router.get("", response_model=list[OrgResponse])
    36	async def list_orgs(user: CurrentUser, session: SessionDep) -> list[OrgResponse]:
    37	    result = await session.execute(
    38	        select(Organization, OrgMember.role)
    39	        .join(OrgMember, OrgMember.org_id == Organization.id)
    40	        .where(OrgMember.user_id == user.id)
    41	        .order_by(Organization.created_at)
    42	    )
    43	    return [
    44	        OrgResponse(
    45	            id=org.id,
    46	            name=org.name,
    47	            uei=org.uei,
    48	            plan=org.plan,
    49	            role=role,
    50	            created_at=org.created_at,
    51	        )
    52	        for org, role in result.all()
    53	    ]
    54	
    55	
    56	@router.get("/{org_id}", response_model=OrgResponse)
    57	async def get_org(ctx: OrgViewer) -> OrgResponse:
    58	    org = ctx.organization
    59	    return OrgResponse(
    60	        id=org.id,
    61	        name=org.name,
    62	        uei=org.uei,
    63	        plan=org.plan,
    64	        role=ctx.role,
    65	        created_at=org.created_at,
    66	    )
    67	
    68	
    69	@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
    70	async def list_members(ctx: OrgViewer, session: SessionDep) -> list[OrgMemberResponse]:
    71	    result = await session.execute(
    72	        select(User, OrgMember.role)
    73	        .join(OrgMember, OrgMember.user_id == User.id)
    74	        .where(OrgMember.org_id == ctx.org_id)
    75	        .order_by(OrgMember.created_at)
    76	    )
    77	    return [
    78	        OrgMemberResponse(user_id=u.id, email=u.email, full_name=u.full_name, role=role)
    79	        for u, role in result.all()
    80	    ]
    81	
    82	
    83	@router.post(
    84	    "/{org_id}/members", response_model=OrgMemberResponse, status_code=status.HTTP_201_CREATED
    85	)
    86	async def add_member(
    87	    body: InviteMemberRequest, ctx: OrgOwner, session: SessionDep
    88	) -> OrgMemberResponse:
    89	    role = OrgRole(body.role).value  # validates the role string
    90	    result = await session.execute(select(User).where(User.email == body.email.lower()))
    91	    target = result.scalar_one_or_none()
    92	    if target is None:
    93	        raise NotFoundError("No user with that email exists")
    94	    existing = await session.execute(
    95	        select(OrgMember).where(OrgMember.org_id == ctx.org_id, OrgMember.user_id == target.id)
    96	    )
    97	    if existing.scalar_one_or_none() is not None:
    98	        raise ConflictError("User is already a member of this organization")
    99	    session.add(OrgMember(org_id=ctx.org_id, user_id=target.id, role=role))
   100	    await record_event(
   101	        "org.member_added",
   102	        org_id=ctx.org_id,
   103	        actor=ActorType.user,
   104	        actor_id=str(ctx.user.id),
   105	        payload={"added_user_id": str(target.id), "role": role},
   106	    )
   107	    return OrgMemberResponse(
   108	        user_id=target.id, email=target.email, full_name=target.full_name, role=role
   109	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/api/auth.py | sed -n '1,160p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Authentication routes (local provider). Firebase clients authenticate via the
     2	Firebase SDK and skip register/login here."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	
     8	from fastapi import APIRouter, status
     9	from sqlalchemy import select
    10	
    11	from captureos.audit import record_event
    12	from captureos.config import AuthProviderName, get_settings
    13	from captureos.core.deps import CurrentUser, SessionDep
    14	from captureos.core.errors import AuthError, ConflictError
    15	from captureos.core.security import (
    16	    create_access_token,
    17	    create_refresh_token,
    18	    decode_token,
    19	    dummy_verify,
    20	    hash_password,
    21	    verify_password,
    22	)
    23	from captureos.models.enums import ActorType, OrgRole
    24	from captureos.models.org import Organization, OrgMember, User
    25	from captureos.schemas.auth import (
    26	    LoginRequest,
    27	    MeResponse,
    28	    OrgMembershipSummary,
    29	    RefreshRequest,
    30	    RegisterRequest,
    31	    TokenResponse,
    32	    UserResponse,
    33	)
    34	
    35	router = APIRouter(prefix="/auth", tags=["auth"])
    36	
    37	
    38	def _ensure_local() -> None:
    39	    if get_settings().auth_provider is not AuthProviderName.local:
    40	        raise AuthError(
    41	            "Local registration/login is disabled; this deployment uses an external auth provider",
    42	            code="auth_provider_external",
    43	        )
    44	
    45	
    46	@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
    47	async def register(body: RegisterRequest, session: SessionDep) -> TokenResponse:
    48	    _ensure_local()
    49	    existing = await session.execute(select(User).where(User.email == body.email.lower()))
    50	    if existing.scalar_one_or_none() is not None:
    51	        raise ConflictError("An account with this email already exists")
    52	
    53	    user = User(
    54	        email=body.email.lower(),
    55	        hashed_password=hash_password(body.password),
    56	        full_name=body.full_name,
    57	    )
    58	    session.add(user)
    59	    await session.flush()
    60	
    61	    if body.org_name:
    62	        org = Organization(name=body.org_name)
    63	        session.add(org)
    64	        await session.flush()
    65	        session.add(OrgMember(org_id=org.id, user_id=user.id, role=OrgRole.owner.value))
    66	        await record_event(
    67	            "org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id)
    68	        )
    69	
    70	    await record_event("auth.register", actor=ActorType.user, actor_id=str(user.id))
    71	    return TokenResponse(
    72	        access_token=create_access_token(user.id, extra={"email": user.email}),
    73	        refresh_token=create_refresh_token(user.id),
    74	    )
    75	
    76	
    77	@router.post("/login", response_model=TokenResponse)
    78	async def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    79	    _ensure_local()
    80	    result = await session.execute(select(User).where(User.email == body.email.lower()))
    81	    user = result.scalar_one_or_none()
    82	    # Equalize timing on the user-missing path so response latency doesn't reveal whether
    83	    # an email is registered (anti-enumeration). Same error message in all failure cases.
    84	    if user is None or not user.hashed_password:
    85	        dummy_verify(body.password)
    86	        raise AuthError("Invalid email or password")
    87	    if not verify_password(body.password, user.hashed_password):
    88	        raise AuthError("Invalid email or password")
    89	    if not user.is_active:
    90	        raise AuthError("Account is inactive")
    91	    await record_event("auth.login", actor=ActorType.user, actor_id=str(user.id))
    92	    return TokenResponse(
    93	        access_token=create_access_token(user.id, extra={"email": user.email}),
    94	        refresh_token=create_refresh_token(user.id),
    95	    )
    96	
    97	
    98	@router.post("/refresh", response_model=TokenResponse)
    99	async def refresh(body: RefreshRequest, session: SessionDep) -> TokenResponse:
   100	    _ensure_local()
   101	    payload = decode_token(body.refresh_token, expected_type="refresh")
   102	    try:
   103	        user_id = uuid.UUID(str(payload["sub"]))
   104	    except (ValueError, KeyError) as exc:
   105	        raise AuthError("Invalid token subject") from exc
   106	    user = await session.get(User, user_id)
   107	    if user is None or not user.is_active:
   108	        raise AuthError("User not found or inactive")
   109	    return TokenResponse(
   110	        access_token=create_access_token(user.id, extra={"email": user.email}),
   111	        refresh_token=create_refresh_token(user.id),
   112	    )
   113	
   114	
   115	@router.get("/me", response_model=MeResponse)
   116	async def me(user: CurrentUser, session: SessionDep) -> MeResponse:
   117	    result = await session.execute(
   118	        select(OrgMember, Organization)
   119	        .join(Organization, Organization.id == OrgMember.org_id)
   120	        .where(OrgMember.user_id == user.id)
   121	    )
   122	    orgs = [
   123	        OrgMembershipSummary(org_id=org.id, name=org.name, role=member.role, plan=org.plan)
   124	        for member, org in result.all()
   125	    ]
   126	    return MeResponse(
   127	        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name),
   128	        orgs=orgs,
   129	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/core/security.py | sed -n '1,140p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Password hashing (Argon2) and JWT issuance/verification for local auth."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from datetime import UTC, datetime, timedelta
     7	from typing import Any
     8	
     9	import jwt
    10	from argon2 import PasswordHasher
    11	from argon2.exceptions import VerifyMismatchError
    12	
    13	from captureos.config import get_settings
    14	from captureos.core.errors import AuthError
    15	
    16	_ph = PasswordHasher()
    17	
    18	
    19	def hash_password(plain: str) -> str:
    20	    return _ph.hash(plain)
    21	
    22	
    23	def verify_password(plain: str, hashed: str) -> bool:
    24	    try:
    25	        return _ph.verify(hashed, plain)
    26	    except VerifyMismatchError:
    27	        return False
    28	    except Exception:
    29	        # Malformed/legacy hash → treat as a failed verification rather than erroring.
    30	        return False
    31	
    32	
    33	# Precomputed hash used to spend comparable CPU on the "user not found" login path,
    34	# so response timing doesn't reveal whether an email is registered (anti-enumeration).
    35	_DUMMY_HASH = _ph.hash("captureos-timing-equalization-constant")  # noqa: S106
    36	
    37	
    38	def dummy_verify(plain: str) -> None:
    39	    """Run an Argon2 verification and discard the result (constant-ish timing)."""
    40	    try:
    41	        _ph.verify(_DUMMY_HASH, plain)
    42	    except Exception:
    43	        pass
    44	
    45	
    46	def needs_rehash(hashed: str) -> bool:
    47	    try:
    48	        return _ph.check_needs_rehash(hashed)
    49	    except Exception:
    50	        return False
    51	
    52	
    53	def _create_token(subject: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    54	    settings = get_settings()
    55	    now = datetime.now(UTC)
    56	    payload: dict[str, Any] = {
    57	        "sub": subject,
    58	        "type": token_type,
    59	        "iat": int(now.timestamp()),
    60	        "exp": int((now + ttl).timestamp()),
    61	        "jti": str(uuid.uuid4()),
    62	    }
    63	    if extra:
    64	        payload.update(extra)
    65	    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    66	
    67	
    68	def create_access_token(user_id: str | uuid.UUID, extra: dict | None = None) -> str:
    69	    settings = get_settings()
    70	    return _create_token(
    71	        str(user_id), "access", timedelta(minutes=settings.jwt_access_ttl_minutes), extra
    72	    )
    73	
    74	
    75	def create_refresh_token(user_id: str | uuid.UUID) -> str:
    76	    settings = get_settings()
    77	    return _create_token(str(user_id), "refresh", timedelta(days=settings.jwt_refresh_ttl_days))
    78	
    79	
    80	def decode_token(token: str, *, expected_type: str | None = None) -> dict:
    81	    settings = get_settings()
    82	    try:
    83	        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    84	    except jwt.ExpiredSignatureError as exc:
    85	        raise AuthError("Token has expired", code="token_expired") from exc
    86	    except jwt.PyJWTError as exc:
    87	        raise AuthError("Invalid token") from exc
    88	    if expected_type and payload.get("type") != expected_type:
    89	        raise AuthError(f"Expected a {expected_type} token")
    90	    return payload

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/embeddings.py | sed -n '40,100p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/llm.py | sed -n '50,120p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    40	            vectors=[self._vector(t) for t in texts],
    41	            model=f"mock/{self._model}",
    42	            dim=self.dim,
    43	        )
    44	
    45	
    46	class GeminiEmbeddings(EmbeddingsProvider):
    47	    name = "gemini"
    48	
    49	    def __init__(self, settings: Settings) -> None:
    50	        if not settings.gemini_api_key:
    51	            raise RuntimeError("GEMINI_API_KEY required when EMBEDDINGS_PROVIDER=gemini")
    52	        self.dim = settings.embedding_dim
    53	        self._model = settings.embedding_model
    54	        try:
    55	            from google import genai  # type: ignore
    56	        except ImportError as exc:  # pragma: no cover
    57	            raise RuntimeError("google-genai not installed (uv sync --extra gcp)") from exc
    58	        self._client = genai.Client(api_key=settings.gemini_api_key)
    59	
    60	    async def embed(self, texts: list[str]) -> EmbeddingResult:  # pragma: no cover - live creds
    61	        import anyio
    62	        from google.genai import types  # type: ignore
    63	
    64	        resp = await anyio.to_thread.run_sync(
    65	            lambda: self._client.models.embed_content(
    66	                model=self._model,
    67	                contents=texts,
    68	                config=types.EmbedContentConfig(output_dimensionality=self.dim),
    69	            )
    70	        )
    71	        vectors = [list(e.values) for e in resp.embeddings]
    72	        return EmbeddingResult(vectors=vectors, model=self._model, dim=self.dim)

 succeeded in 0ms:
    50	            text=text,
    51	            model=f"mock/{model}",
    52	            input_tokens=_est_tokens((system or "") + prompt),
    53	            output_tokens=_est_tokens(text),
    54	        )
    55	
    56	
    57	class GeminiLLM(LLMProvider):
    58	    """Google Gemini via the google-genai SDK (installed with the `gcp` extra)."""
    59	
    60	    name = "gemini"
    61	
    62	    def __init__(self, settings: Settings) -> None:
    63	        if not settings.gemini_api_key:
    64	            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
    65	        self._settings = settings
    66	        try:
    67	            from google import genai  # type: ignore
    68	        except ImportError as exc:  # pragma: no cover - exercised only in prod images
    69	            raise RuntimeError(
    70	                "google-genai not installed. Install the `gcp` extra: uv sync --extra gcp"
    71	            ) from exc
    72	        self._genai = genai
    73	        self._client = genai.Client(api_key=settings.gemini_api_key)
    74	
    75	    def _model_for(self, tier: ModelTier) -> str:
    76	        return (
    77	            self._settings.gemini_model_pro
    78	            if tier is ModelTier.pro
    79	            else self._settings.gemini_model_flash
    80	        )
    81	
    82	    async def generate(
    83	        self,
    84	        prompt: str,
    85	        *,
    86	        tier: ModelTier = ModelTier.flash,
    87	        system: str | None = None,
    88	        json_schema: dict | None = None,
    89	        temperature: float = 0.2,
    90	        max_output_tokens: int = 4096,
    91	    ) -> LLMResponse:  # pragma: no cover - requires live credentials
    92	        from google.genai import types  # type: ignore
    93	
    94	        config = types.GenerateContentConfig(
    95	            system_instruction=system,
    96	            temperature=temperature,
    97	            max_output_tokens=max_output_tokens,
    98	            response_mime_type="application/json" if json_schema else None,
    99	            response_schema=json_schema,
   100	        )
   101	        model = self._model_for(tier)
   102	        # google-genai is sync; run off the event loop.
   103	        import anyio
   104	
   105	        resp = await anyio.to_thread.run_sync(
   106	            lambda: self._client.models.generate_content(
   107	                model=model, contents=prompt, config=config
   108	            )
   109	        )
   110	        usage = getattr(resp, "usage_metadata", None)
   111	        return LLMResponse(
   112	            text=resp.text or "",
   113	            model=model,
   114	            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
   115	            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
   116	        )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/auth/firebase.py | sed -n '1,120p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Firebase auth provider. Verifies Firebase ID tokens (prod; `gcp` extra)."""
     2	
     3	from __future__ import annotations
     4	
     5	from captureos.auth.base import AuthPrincipal, AuthProvider
     6	from captureos.config import Settings
     7	from captureos.core.errors import AuthError
     8	
     9	
    10	class FirebaseAuthProvider(AuthProvider):  # pragma: no cover - requires Firebase config
    11	    name = "firebase"
    12	
    13	    def __init__(self, settings: Settings) -> None:
    14	        try:
    15	            import firebase_admin  # type: ignore
    16	            from firebase_admin import credentials
    17	        except ImportError as exc:
    18	            raise RuntimeError("firebase-admin not installed (uv sync --extra gcp)") from exc
    19	        if not firebase_admin._apps:
    20	            cred = (
    21	                credentials.Certificate(settings.google_application_credentials)
    22	                if settings.google_application_credentials
    23	                else credentials.ApplicationDefault()
    24	            )
    25	            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
    26	        self._settings = settings
    27	
    28	    async def verify_token(self, token: str) -> AuthPrincipal:
    29	        import anyio
    30	        from firebase_admin import auth as fb_auth  # type: ignore
    31	
    32	        try:
    33	            decoded = await anyio.to_thread.run_sync(lambda: fb_auth.verify_id_token(token))
    34	        except Exception as exc:
    35	            raise AuthError("Invalid Firebase token") from exc
    36	        return AuthPrincipal(subject=decoded["uid"], email=decoded.get("email"), is_local=False)

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/__init__.py | sed -n '90,120p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    90	
    91	
    92	@lru_cache
    93	def get_docparse(settings: Settings | None = None) -> DocparseProvider:
    94	    s = settings or get_settings()
    95	    if s.docparse_provider is DocparseProviderName.docai:
    96	        return DocAIDocparse(s)
    97	    return LocalDocparse(s)
    98	
    99	
   100	@lru_cache
   101	def get_secrets(settings: Settings | None = None) -> SecretsProvider:
   102	    s = settings or get_settings()
   103	    if s.secrets_backend is SecretsBackendName.gcp_secret_manager:
   104	        return GCPSecretManager(s)
   105	    return EnvSecrets(s)
   106	
   107	
   108	@lru_cache
   109	def get_audit_sink(settings: Settings | None = None) -> AuditSink:
   110	    s = settings or get_settings()
   111	    if s.audit_sink is AuditSinkName.bigquery:
   112	        return BigQueryAuditSink(s)
   113	    return PostgresAuditSink(s)
   114	
   115	
   116	def reset_providers() -> None:
   117	    """Clear cached providers (used by tests that swap config)."""
   118	    for fn in (
   119	        get_llm,
   120	        get_embeddings,

exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/evidence.py | sed -n '18,80p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/documents.py | sed -n '40,90p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/workflow.py | sed -n '18,90p'" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/filings.py | sed -n '20,110p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    40	    chunks: Mapped[list[DocumentChunk]] = relationship(
    41	        back_populates="document", cascade="all, delete-orphan"
    42	    )
    43	
    44	
    45	class DocumentChunk(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    46	    __tablename__ = "document_chunks"
    47	    __table_args__ = (
    48	        UniqueConstraint("document_id", "ordinal"),
    49	        # IVF/HNSW index added in M1 once data exists; cosine distance for retrieval.
    50	        Index(
    51	            "ix_document_chunks_embedding",
    52	            "embedding",
    53	            postgresql_using="hnsw",
    54	            postgresql_with={"m": 16, "ef_construction": 64},
    55	            postgresql_ops={"embedding": "vector_cosine_ops"},
    56	        ),
    57	    )
    58	
    59	    document_id: Mapped[uuid.UUID] = mapped_column(
    60	        PGUUID(as_uuid=True),
    61	        ForeignKey("documents.id", ondelete="CASCADE"),
    62	        nullable=False,
    63	        index=True,
    64	    )
    65	    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    66	    text: Mapped[str] = mapped_column(Text, nullable=False)
    67	    # Page/section reference so citations resolve to a source (FR-DI-5).
    68	    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    69	    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    70	
    71	    document: Mapped[Document] = relationship(back_populates="chunks")

 succeeded in 0ms:
    18	
    19	
    20	class Source(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    21	    __tablename__ = "sources"
    22	
    23	    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=SourceKind.web.value)
    24	    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    25	    document_id: Mapped[uuid.UUID | None] = mapped_column(
    26	        PGUUID(as_uuid=True),
    27	        ForeignKey("documents.id", ondelete="SET NULL"),
    28	        nullable=True,
    29	        index=True,
    30	    )
    31	    # Cached content snapshot for auditability (FR-OD-3); a storage URI.
    32	    snapshot_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    33	    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    34	    retrieved_at: Mapped[datetime] = mapped_column(
    35	        DateTime(timezone=True), nullable=False, server_default=func.now()
    36	    )
    37	
    38	
    39	class EvidenceItem(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    40	    __tablename__ = "evidence_items"
    41	
    42	    type: Mapped[str] = mapped_column(String(32), nullable=False, default=EvidenceType.fact.value)
    43	    content: Mapped[str] = mapped_column(Text, nullable=False)
    44	    # Every evidence item must trace to a source (CON-2).
    45	    source_id: Mapped[uuid.UUID] = mapped_column(
    46	        PGUUID(as_uuid=True),
    47	        ForeignKey("sources.id", ondelete="CASCADE"),
    48	        nullable=False,
    49	        index=True,
    50	    )
    51	    origin: Mapped[str] = mapped_column(
    52	        String(16), nullable=False, default=EvidenceOrigin.inferred.value
    53	    )
    54	    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    55	    # Optional pointer to the chunk this fact was derived from (locator resolution).
    56	    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
    57	        PGUUID(as_uuid=True),
    58	        ForeignKey("document_chunks.id", ondelete="SET NULL"),
    59	        nullable=True,
    60	        index=True,
    61	    )

 succeeded in 0ms:
    18	from captureos.models.enums import AgentRunStatus, StepStatus, WorkflowStatus, WorkflowType
    19	
    20	
    21	class WorkflowRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    22	    __tablename__ = "workflow_runs"
    23	
    24	    filing_id: Mapped[uuid.UUID | None] = mapped_column(
    25	        PGUUID(as_uuid=True),
    26	        ForeignKey("filings.id", ondelete="CASCADE"),
    27	        nullable=True,
    28	        index=True,
    29	    )
    30	    type: Mapped[str] = mapped_column(
    31	        String(32), nullable=False, default=WorkflowType.company_brain.value
    32	    )
    33	    status: Mapped[str] = mapped_column(
    34	        String(16), nullable=False, default=WorkflowStatus.queued.value, index=True
    35	    )
    36	    input_params: Mapped[dict] = mapped_column(
    37	        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    38	    )
    39	    partial_results: Mapped[dict] = mapped_column(
    40	        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    41	    )
    42	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    43	    time_saved_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    44	    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    45	    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    46	
    47	    steps: Mapped[list[WorkflowStep]] = relationship(
    48	        back_populates="run", cascade="all, delete-orphan", order_by="WorkflowStep.ordinal"
    49	    )
    50	
    51	
    52	class WorkflowStep(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    53	    __tablename__ = "workflow_steps"
    54	    # Idempotency: a step name is unique within a run (FR-RE §10.5, idempotent re-delivery).
    55	    __table_args__ = (UniqueConstraint("run_id", "name"),)
    56	
    57	    run_id: Mapped[uuid.UUID] = mapped_column(
    58	        PGUUID(as_uuid=True),
    59	        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
    60	        nullable=False,
    61	        index=True,
    62	    )
    63	    name: Mapped[str] = mapped_column(String(128), nullable=False)
    64	    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    65	    status: Mapped[str] = mapped_column(
    66	        String(16), nullable=False, default=StepStatus.pending.value
    67	    )
    68	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    69	
    70	    run: Mapped[WorkflowRun] = relationship(back_populates="steps")
    71	    agent_runs: Mapped[list[AgentRun]] = relationship(
    72	        back_populates="step", cascade="all, delete-orphan"
    73	    )
    74	
    75	
    76	class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    77	    __tablename__ = "agent_runs"
    78	
    79	    step_id: Mapped[uuid.UUID] = mapped_column(
    80	        PGUUID(as_uuid=True),
    81	        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
    82	        nullable=False,
    83	        index=True,
    84	    )
    85	    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    86	    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    87	    input: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    88	    output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    89	    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    90	    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

 succeeded in 0ms:
    20	    RecommendationDecision,
    21	    RequirementCategory,
    22	)
    23	
    24	
    25	class Filing(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    26	    __tablename__ = "filings"
    27	
    28	    opportunity_id: Mapped[uuid.UUID] = mapped_column(
    29	        PGUUID(as_uuid=True),
    30	        ForeignKey("opportunities.id", ondelete="CASCADE"),
    31	        nullable=False,
    32	        index=True,
    33	    )
    34	    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    35	    status: Mapped[str] = mapped_column(
    36	        String(32), nullable=False, default=FilingStatus.draft.value, index=True
    37	    )
    38	    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
    39	        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    40	    )
    41	
    42	    requirements: Mapped[list[FilingRequirement]] = relationship(
    43	        back_populates="filing", cascade="all, delete-orphan"
    44	    )
    45	    evidence_matches: Mapped[list[EvidenceMatch]] = relationship(
    46	        back_populates="filing", cascade="all, delete-orphan"
    47	    )
    48	    recommendation: Mapped[Recommendation | None] = relationship(
    49	        back_populates="filing", cascade="all, delete-orphan", uselist=False
    50	    )
    51	    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
    52	        back_populates="filing", cascade="all, delete-orphan"
    53	    )
    54	    approvals: Mapped[list[Approval]] = relationship(
    55	        back_populates="filing", cascade="all, delete-orphan"
    56	    )
    57	
    58	
    59	class FilingRequirement(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    60	    __tablename__ = "filing_requirements"
    61	
    62	    filing_id: Mapped[uuid.UUID] = mapped_column(
    63	        PGUUID(as_uuid=True),
    64	        ForeignKey("filings.id", ondelete="CASCADE"),
    65	        nullable=False,
    66	        index=True,
    67	    )
    68	    text: Mapped[str] = mapped_column(Text, nullable=False)
    69	    category: Mapped[str] = mapped_column(
    70	        String(32), nullable=False, default=RequirementCategory.other.value
    71	    )
    72	    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    73	    # Citation back to the solicitation (CON-2).
    74	    source_id: Mapped[uuid.UUID | None] = mapped_column(
    75	        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    76	    )
    77	    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    78	    # Flagged-for-review when extraction confidence is low / schema-retry exhausted (FR-RE-2).
    79	    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    80	
    81	    filing: Mapped[Filing] = relationship(back_populates="requirements")
    82	
    83	
    84	class EvidenceMatch(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    85	    __tablename__ = "evidence_matches"
    86	
    87	    filing_id: Mapped[uuid.UUID] = mapped_column(
    88	        PGUUID(as_uuid=True),
    89	        ForeignKey("filings.id", ondelete="CASCADE"),
    90	        nullable=False,
    91	        index=True,
    92	    )
    93	    requirement_id: Mapped[uuid.UUID] = mapped_column(
    94	        PGUUID(as_uuid=True),
    95	        ForeignKey("filing_requirements.id", ondelete="CASCADE"),
    96	        nullable=False,
    97	        index=True,
    98	    )
    99	    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(
   100	        PGUUID(as_uuid=True),
   101	        ForeignKey("evidence_items.id", ondelete="SET NULL"),
   102	        nullable=True,
   103	    )
   104	    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0)
   105	    status: Mapped[str] = mapped_column(
   106	        String(16), nullable=False, default=MatchStatus.missing.value, index=True
   107	    )
   108	    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
   109	
   110	    filing: Mapped[Filing] = relationship(back_populates="evidence_matches")

exec
/bin/zsh -lc "nl -ba apps/api/migrations/versions/f28c812fca98_initial_schema.py | sed -n '170,430p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
   170	    op.create_index(op.f('ix_subscriptions_external_id'), 'subscriptions', ['external_id'], unique=False)
   171	    op.create_index(op.f('ix_subscriptions_org_id'), 'subscriptions', ['org_id'], unique=False)
   172	    op.create_table('document_chunks',
   173	    sa.Column('document_id', sa.UUID(), nullable=False),
   174	    sa.Column('ordinal', sa.Integer(), nullable=False),
   175	    sa.Column('text', sa.Text(), nullable=False),
   176	    sa.Column('locator', sa.String(length=255), nullable=True),
   177	    sa.Column('embedding', Vector(768), nullable=True),
   178	    sa.Column('id', sa.UUID(), nullable=False),
   179	    sa.Column('org_id', sa.UUID(), nullable=False),
   180	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   181	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   182	    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_chunks_document_id_documents'), ondelete='CASCADE'),
   183	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_document_chunks_org_id_organizations'), ondelete='CASCADE'),
   184	    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks')),
   185	    sa.UniqueConstraint('document_id', 'ordinal', name=op.f('uq_document_chunks_document_id'))
   186	    )
   187	    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
   188	    op.create_index('ix_document_chunks_embedding', 'document_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
   189	    op.create_index(op.f('ix_document_chunks_org_id'), 'document_chunks', ['org_id'], unique=False)
   190	    op.create_table('sources',
   191	    sa.Column('kind', sa.String(length=32), nullable=False),
   192	    sa.Column('url', sa.String(length=2048), nullable=True),
   193	    sa.Column('document_id', sa.UUID(), nullable=True),
   194	    sa.Column('snapshot_uri', sa.String(length=2048), nullable=True),
   195	    sa.Column('title', sa.String(length=512), nullable=True),
   196	    sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   197	    sa.Column('id', sa.UUID(), nullable=False),
   198	    sa.Column('org_id', sa.UUID(), nullable=False),
   199	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   200	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   201	    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_sources_document_id_documents'), ondelete='SET NULL'),
   202	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_sources_org_id_organizations'), ondelete='CASCADE'),
   203	    sa.PrimaryKeyConstraint('id', name=op.f('pk_sources'))
   204	    )
   205	    op.create_index(op.f('ix_sources_document_id'), 'sources', ['document_id'], unique=False)
   206	    op.create_index(op.f('ix_sources_org_id'), 'sources', ['org_id'], unique=False)
   207	    op.create_table('evidence_items',
   208	    sa.Column('type', sa.String(length=32), nullable=False),
   209	    sa.Column('content', sa.Text(), nullable=False),
   210	    sa.Column('source_id', sa.UUID(), nullable=False),
   211	    sa.Column('origin', sa.String(length=16), nullable=False),
   212	    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
   213	    sa.Column('document_chunk_id', sa.UUID(), nullable=True),
   214	    sa.Column('id', sa.UUID(), nullable=False),
   215	    sa.Column('org_id', sa.UUID(), nullable=False),
   216	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   217	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   218	    sa.ForeignKeyConstraint(['document_chunk_id'], ['document_chunks.id'], name=op.f('fk_evidence_items_document_chunk_id_document_chunks'), ondelete='SET NULL'),
   219	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_items_org_id_organizations'), ondelete='CASCADE'),
   220	    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_evidence_items_source_id_sources'), ondelete='CASCADE'),
   221	    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_items'))
   222	    )
   223	    op.create_index(op.f('ix_evidence_items_document_chunk_id'), 'evidence_items', ['document_chunk_id'], unique=False)
   224	    op.create_index(op.f('ix_evidence_items_org_id'), 'evidence_items', ['org_id'], unique=False)
   225	    op.create_index(op.f('ix_evidence_items_source_id'), 'evidence_items', ['source_id'], unique=False)
   226	    op.create_table('opportunities',
   227	    sa.Column('kind', sa.String(length=32), nullable=False),
   228	    sa.Column('title', sa.String(length=1024), nullable=False),
   229	    sa.Column('sponsor', sa.String(length=512), nullable=True),
   230	    sa.Column('external_id', sa.String(length=255), nullable=True),
   231	    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
   232	    sa.Column('source_id', sa.UUID(), nullable=True),
   233	    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
   234	    sa.Column('raw_text', sa.Text(), nullable=True),
   235	    sa.Column('fit_score', sa.Numeric(precision=5, scale=2), nullable=True),
   236	    sa.Column('decision_hint', sa.String(length=32), nullable=True),
   237	    sa.Column('fit_rationale', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
   238	    sa.Column('id', sa.UUID(), nullable=False),
   239	    sa.Column('org_id', sa.UUID(), nullable=False),
   240	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   241	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   242	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_opportunities_org_id_organizations'), ondelete='CASCADE'),
   243	    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_opportunities_source_id_sources'), ondelete='SET NULL'),
   244	    sa.PrimaryKeyConstraint('id', name=op.f('pk_opportunities'))
   245	    )
   246	    op.create_index(op.f('ix_opportunities_external_id'), 'opportunities', ['external_id'], unique=False)
   247	    op.create_index(op.f('ix_opportunities_kind'), 'opportunities', ['kind'], unique=False)
   248	    op.create_index(op.f('ix_opportunities_org_id'), 'opportunities', ['org_id'], unique=False)
   249	    op.create_index(op.f('ix_opportunities_source_id'), 'opportunities', ['source_id'], unique=False)
   250	    op.create_table('filings',
   251	    sa.Column('opportunity_id', sa.UUID(), nullable=False),
   252	    sa.Column('kind', sa.String(length=32), nullable=False),
   253	    sa.Column('status', sa.String(length=32), nullable=False),
   254	    sa.Column('owner_user_id', sa.UUID(), nullable=True),
   255	    sa.Column('id', sa.UUID(), nullable=False),
   256	    sa.Column('org_id', sa.UUID(), nullable=False),
   257	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   258	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   259	    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], name=op.f('fk_filings_opportunity_id_opportunities'), ondelete='CASCADE'),
   260	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filings_org_id_organizations'), ondelete='CASCADE'),
   261	    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], name=op.f('fk_filings_owner_user_id_users'), ondelete='SET NULL'),
   262	    sa.PrimaryKeyConstraint('id', name=op.f('pk_filings'))
   263	    )
   264	    op.create_index(op.f('ix_filings_opportunity_id'), 'filings', ['opportunity_id'], unique=False)
   265	    op.create_index(op.f('ix_filings_org_id'), 'filings', ['org_id'], unique=False)
   266	    op.create_index(op.f('ix_filings_status'), 'filings', ['status'], unique=False)
   267	    op.create_table('approvals',
   268	    sa.Column('filing_id', sa.UUID(), nullable=False),
   269	    sa.Column('target', sa.String(length=16), nullable=False),
   270	    sa.Column('approver_user_id', sa.UUID(), nullable=True),
   271	    sa.Column('decision', sa.String(length=16), nullable=False),
   272	    sa.Column('notes', sa.Text(), nullable=True),
   273	    sa.Column('id', sa.UUID(), nullable=False),
   274	    sa.Column('org_id', sa.UUID(), nullable=False),
   275	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   276	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   277	    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], name=op.f('fk_approvals_approver_user_id_users'), ondelete='SET NULL'),
   278	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_approvals_filing_id_filings'), ondelete='CASCADE'),
   279	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_approvals_org_id_organizations'), ondelete='CASCADE'),
   280	    sa.PrimaryKeyConstraint('id', name=op.f('pk_approvals'))
   281	    )
   282	    op.create_index(op.f('ix_approvals_filing_id'), 'approvals', ['filing_id'], unique=False)
   283	    op.create_index(op.f('ix_approvals_org_id'), 'approvals', ['org_id'], unique=False)
   284	    op.create_table('filing_requirements',
   285	    sa.Column('filing_id', sa.UUID(), nullable=False),
   286	    sa.Column('text', sa.Text(), nullable=False),
   287	    sa.Column('category', sa.String(length=32), nullable=False),
   288	    sa.Column('mandatory', sa.Boolean(), nullable=False),
   289	    sa.Column('source_id', sa.UUID(), nullable=True),
   290	    sa.Column('locator', sa.String(length=255), nullable=True),
   291	    sa.Column('needs_review', sa.Boolean(), nullable=False),
   292	    sa.Column('id', sa.UUID(), nullable=False),
   293	    sa.Column('org_id', sa.UUID(), nullable=False),
   294	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   295	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   296	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_filing_requirements_filing_id_filings'), ondelete='CASCADE'),
   297	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_filing_requirements_org_id_organizations'), ondelete='CASCADE'),
   298	    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_filing_requirements_source_id_sources'), ondelete='SET NULL'),
   299	    sa.PrimaryKeyConstraint('id', name=op.f('pk_filing_requirements'))
   300	    )
   301	    op.create_index(op.f('ix_filing_requirements_filing_id'), 'filing_requirements', ['filing_id'], unique=False)
   302	    op.create_index(op.f('ix_filing_requirements_org_id'), 'filing_requirements', ['org_id'], unique=False)
   303	    op.create_table('generated_documents',
   304	    sa.Column('filing_id', sa.UUID(), nullable=False),
   305	    sa.Column('type', sa.String(length=32), nullable=False),
   306	    sa.Column('version', sa.Integer(), nullable=False),
   307	    sa.Column('content_md', sa.Text(), nullable=False),
   308	    sa.Column('export_uri', sa.String(length=2048), nullable=True),
   309	    sa.Column('status', sa.String(length=16), nullable=False),
   310	    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
   311	    sa.Column('citation_validated', sa.Boolean(), nullable=False),
   312	    sa.Column('id', sa.UUID(), nullable=False),
   313	    sa.Column('org_id', sa.UUID(), nullable=False),
   314	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   315	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   316	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_generated_documents_filing_id_filings'), ondelete='CASCADE'),
   317	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_generated_documents_org_id_organizations'), ondelete='CASCADE'),
   318	    sa.PrimaryKeyConstraint('id', name=op.f('pk_generated_documents')),
   319	    sa.UniqueConstraint('filing_id', 'type', 'version', name=op.f('uq_generated_documents_filing_id'))
   320	    )
   321	    op.create_index(op.f('ix_generated_documents_filing_id'), 'generated_documents', ['filing_id'], unique=False)
   322	    op.create_index(op.f('ix_generated_documents_org_id'), 'generated_documents', ['org_id'], unique=False)
   323	    op.create_table('recommendations',
   324	    sa.Column('filing_id', sa.UUID(), nullable=False),
   325	    sa.Column('decision', sa.String(length=16), nullable=False),
   326	    sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=False),
   327	    sa.Column('rationale', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
   328	    sa.Column('approved', sa.Boolean(), nullable=False),
   329	    sa.Column('id', sa.UUID(), nullable=False),
   330	    sa.Column('org_id', sa.UUID(), nullable=False),
   331	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   332	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   333	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_recommendations_filing_id_filings'), ondelete='CASCADE'),
   334	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_recommendations_org_id_organizations'), ondelete='CASCADE'),
   335	    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendations')),
   336	    sa.UniqueConstraint('filing_id', name=op.f('uq_recommendations_filing_id'))
   337	    )
   338	    op.create_index(op.f('ix_recommendations_filing_id'), 'recommendations', ['filing_id'], unique=False)
   339	    op.create_index(op.f('ix_recommendations_org_id'), 'recommendations', ['org_id'], unique=False)
   340	    op.create_table('workflow_runs',
   341	    sa.Column('filing_id', sa.UUID(), nullable=True),
   342	    sa.Column('type', sa.String(length=32), nullable=False),
   343	    sa.Column('status', sa.String(length=16), nullable=False),
   344	    sa.Column('input_params', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
   345	    sa.Column('partial_results', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
   346	    sa.Column('error', sa.Text(), nullable=True),
   347	    sa.Column('time_saved_minutes', sa.Integer(), nullable=True),
   348	    sa.Column('total_input_tokens', sa.Integer(), nullable=False),
   349	    sa.Column('total_output_tokens', sa.Integer(), nullable=False),
   350	    sa.Column('id', sa.UUID(), nullable=False),
   351	    sa.Column('org_id', sa.UUID(), nullable=False),
   352	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   353	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   354	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_workflow_runs_filing_id_filings'), ondelete='CASCADE'),
   355	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_runs_org_id_organizations'), ondelete='CASCADE'),
   356	    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_runs'))
   357	    )
   358	    op.create_index(op.f('ix_workflow_runs_filing_id'), 'workflow_runs', ['filing_id'], unique=False)
   359	    op.create_index(op.f('ix_workflow_runs_org_id'), 'workflow_runs', ['org_id'], unique=False)
   360	    op.create_index(op.f('ix_workflow_runs_status'), 'workflow_runs', ['status'], unique=False)
   361	    op.create_table('evidence_matches',
   362	    sa.Column('filing_id', sa.UUID(), nullable=False),
   363	    sa.Column('requirement_id', sa.UUID(), nullable=False),
   364	    sa.Column('evidence_item_id', sa.UUID(), nullable=True),
   365	    sa.Column('score', sa.Numeric(precision=5, scale=4), nullable=False),
   366	    sa.Column('status', sa.String(length=16), nullable=False),
   367	    sa.Column('rationale', sa.Text(), nullable=True),
   368	    sa.Column('id', sa.UUID(), nullable=False),
   369	    sa.Column('org_id', sa.UUID(), nullable=False),
   370	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   371	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   372	    sa.ForeignKeyConstraint(['evidence_item_id'], ['evidence_items.id'], name=op.f('fk_evidence_matches_evidence_item_id_evidence_items'), ondelete='SET NULL'),
   373	    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_evidence_matches_filing_id_filings'), ondelete='CASCADE'),
   374	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_matches_org_id_organizations'), ondelete='CASCADE'),
   375	    sa.ForeignKeyConstraint(['requirement_id'], ['filing_requirements.id'], name=op.f('fk_evidence_matches_requirement_id_filing_requirements'), ondelete='CASCADE'),
   376	    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_matches'))
   377	    )
   378	    op.create_index(op.f('ix_evidence_matches_filing_id'), 'evidence_matches', ['filing_id'], unique=False)
   379	    op.create_index(op.f('ix_evidence_matches_org_id'), 'evidence_matches', ['org_id'], unique=False)
   380	    op.create_index(op.f('ix_evidence_matches_requirement_id'), 'evidence_matches', ['requirement_id'], unique=False)
   381	    op.create_index(op.f('ix_evidence_matches_status'), 'evidence_matches', ['status'], unique=False)
   382	    op.create_table('workflow_steps',
   383	    sa.Column('run_id', sa.UUID(), nullable=False),
   384	    sa.Column('name', sa.String(length=128), nullable=False),
   385	    sa.Column('ordinal', sa.Integer(), nullable=False),
   386	    sa.Column('status', sa.String(length=16), nullable=False),
   387	    sa.Column('error', sa.Text(), nullable=True),
   388	    sa.Column('id', sa.UUID(), nullable=False),
   389	    sa.Column('org_id', sa.UUID(), nullable=False),
   390	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   391	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   392	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_steps_org_id_organizations'), ondelete='CASCADE'),
   393	    sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], name=op.f('fk_workflow_steps_run_id_workflow_runs'), ondelete='CASCADE'),
   394	    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_steps')),
   395	    sa.UniqueConstraint('run_id', 'name', name=op.f('uq_workflow_steps_run_id'))
   396	    )
   397	    op.create_index(op.f('ix_workflow_steps_org_id'), 'workflow_steps', ['org_id'], unique=False)
   398	    op.create_index(op.f('ix_workflow_steps_run_id'), 'workflow_steps', ['run_id'], unique=False)
   399	    op.create_table('agent_runs',
   400	    sa.Column('step_id', sa.UUID(), nullable=False),
   401	    sa.Column('agent_name', sa.String(length=128), nullable=False),
   402	    sa.Column('model', sa.String(length=128), nullable=True),
   403	    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
   404	    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
   405	    sa.Column('input_tokens', sa.Integer(), nullable=False),
   406	    sa.Column('output_tokens', sa.Integer(), nullable=False),
   407	    sa.Column('latency_ms', sa.Integer(), nullable=False),
   408	    sa.Column('status', sa.String(length=16), nullable=False),
   409	    sa.Column('error', sa.Text(), nullable=True),
   410	    sa.Column('id', sa.UUID(), nullable=False),
   411	    sa.Column('org_id', sa.UUID(), nullable=False),
   412	    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   413	    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
   414	    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_agent_runs_org_id_organizations'), ondelete='CASCADE'),
   415	    sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], name=op.f('fk_agent_runs_step_id_workflow_steps'), ondelete='CASCADE'),
   416	    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs'))
   417	    )
   418	    op.create_index(op.f('ix_agent_runs_org_id'), 'agent_runs', ['org_id'], unique=False)
   419	    op.create_index(op.f('ix_agent_runs_step_id'), 'agent_runs', ['step_id'], unique=False)
   420	    # ### end Alembic commands ###
   421	
   422	
   423	def downgrade() -> None:
   424	    # ### commands auto generated by Alembic - please adjust! ###
   425	    op.drop_index(op.f('ix_agent_runs_step_id'), table_name='agent_runs')
   426	    op.drop_index(op.f('ix_agent_runs_org_id'), table_name='agent_runs')
   427	    op.drop_table('agent_runs')
   428	    op.drop_index(op.f('ix_workflow_steps_run_id'), table_name='workflow_steps')
   429	    op.drop_index(op.f('ix_workflow_steps_org_id'), table_name='workflow_steps')
   430	    op.drop_table('workflow_steps')

exec
/bin/zsh -lc "nl -ba apps/web/src/lib/tokenStore.ts | sed -n '1,120p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	// External token store backed by localStorage, consumed via useSyncExternalStore.
     2	// This is the React 19-idiomatic way to read browser storage without setState-in-effect
     3	// and without hydration mismatches (getServerSnapshot returns null to match SSR).
     4	
     5	import { setTokenGetter } from "./api";
     6	import type { Tokens } from "./types";
     7	
     8	const TOKEN_KEY = "captureos.tokens";
     9	type Listener = () => void;
    10	const listeners = new Set<Listener>();
    11	
    12	function read(): Tokens | null {
    13	  if (typeof window === "undefined") return null;
    14	  const raw = window.localStorage.getItem(TOKEN_KEY);
    15	  if (!raw) return null;
    16	  try {
    17	    return JSON.parse(raw) as Tokens;
    18	  } catch {
    19	    return null;
    20	  }
    21	}
    22	
    23	// Stable cached snapshot (useSyncExternalStore requires reference stability).
    24	let snapshot: Tokens | null = read();
    25	
    26	// The api client pulls the access token synchronously from this store.
    27	setTokenGetter(() => snapshot?.accessToken ?? null);
    28	
    29	export function getSnapshot(): Tokens | null {
    30	  return snapshot;
    31	}
    32	
    33	export function getServerSnapshot(): Tokens | null {
    34	  return null;
    35	}
    36	
    37	export function subscribe(listener: Listener): () => void {
    38	  listeners.add(listener);
    39	  return () => {
    40	    listeners.delete(listener);
    41	  };
    42	}
    43	
    44	export function setTokens(next: Tokens | null): void {
    45	  snapshot = next;
    46	  if (typeof window !== "undefined") {
    47	    if (next) window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
    48	    else window.localStorage.removeItem(TOKEN_KEY);
    49	  }
    50	  for (const listener of listeners) listener();
    51	}

codex
There’s a larger runtime defect in the auth path than expected, so I’m validating it against the audit service signature before I finalize severity and verdict.
exec
/bin/zsh -lc "nl -ba apps/api/captureos/audit/service.py | sed -n '1,120p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Thin facade over the configured audit sink. Build an event and persist it.
     2	
     3	This is the single choke point routes/agents call to satisfy CON-3, so the audit
     4	schema stays consistent regardless of sink (Postgres vs BigQuery).
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	from typing import Any
    11	
    12	from captureos.models.enums import ActorType
    13	from captureos.providers import get_audit_sink
    14	
    15	
    16	async def record_event(
    17	    action: str,
    18	    *,
    19	    org_id: str | uuid.UUID | None = None,
    20	    actor: ActorType | str = ActorType.system,
    21	    actor_id: str | None = None,
    22	    filing_id: str | uuid.UUID | None = None,
    23	    run_id: str | uuid.UUID | None = None,
    24	    step_id: str | uuid.UUID | None = None,
    25	    source_url: str | None = None,
    26	    model: str | None = None,
    27	    input_tokens: int | None = None,
    28	    output_tokens: int | None = None,
    29	    latency_ms: int | None = None,
    30	    status: str | None = None,
    31	    payload: dict[str, Any] | None = None,
    32	) -> None:
    33	    event: dict[str, Any] = {
    34	        "action": action,
    35	        "org_id": str(org_id) if org_id else None,
    36	        "actor": str(actor),
    37	        "actor_id": actor_id,
    38	        "filing_id": str(filing_id) if filing_id else None,
    39	        "run_id": str(run_id) if run_id else None,
    40	        "step_id": str(step_id) if step_id else None,
    41	        "source_url": source_url,
    42	        "model": model,
    43	        "input_tokens": input_tokens,
    44	        "output_tokens": output_tokens,
    45	        "latency_ms": latency_ms,
    46	        "status": status,
    47	        "payload": payload or {},
    48	    }
    49	    await get_audit_sink().emit(event)

exec
/bin/zsh -lc "rg -n \"record_event\\(\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/audit/service.py:16:async def record_event(
apps/api/captureos/api/orgs.py:24:    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/orgs.py:100:    await record_event(
apps/api/captureos/api/auth.py:66:        await record_event(
apps/api/captureos/api/auth.py:70:    await record_event("auth.register", actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/auth.py:91:    await record_event("auth.login", actor=ActorType.user, actor_id=str(user.id))

exec
/bin/zsh -lc "nl -ba apps/api/captureos/db/base.py | sed -n '40,70p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    40	    updated_at: Mapped[datetime] = mapped_column(
    41	        DateTime(timezone=True),
    42	        server_default=func.now(),
    43	        onupdate=func.now(),
    44	        nullable=False,
    45	    )
    46	
    47	
    48	class OrgScopedMixin:
    49	    """Adds an indexed ``org_id`` FK (ON DELETE CASCADE). Every tenant table uses this
    50	    so org isolation (CON-5) is uniform and queries can filter on one column."""
    51	
    52	    @declared_attr
    53	    def org_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
    54	        return mapped_column(
    55	            PGUUID(as_uuid=True),
    56	            ForeignKey("organizations.id", ondelete="CASCADE"),
    57	            nullable=False,
    58	            index=True,
    59	        )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/db/session.py | sed -n '35,70p'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
    35	def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    36	    return async_sessionmaker(
    37	        bind=get_engine(),
    38	        expire_on_commit=False,
    39	        autoflush=False,
    40	    )
    41	
    42	
    43	async def get_session() -> AsyncIterator[AsyncSession]:
    44	    """FastAPI dependency. Commits on success, rolls back on error."""
    45	    sessionmaker = get_sessionmaker()
    46	    async with sessionmaker() as session:
    47	        try:
    48	            yield session
    49	            await session.commit()
    50	        except Exception:
    51	            await session.rollback()
    52	            raise
    53	
    54	
    55	@asynccontextmanager
    56	async def session_scope() -> AsyncIterator[AsyncSession]:
    57	    """Context manager for non-request code (workers, scripts, seeds)."""
    58	    sessionmaker = get_sessionmaker()
    59	    async with sessionmaker() as session:
    60	        try:
    61	            yield session
    62	            await session.commit()
    63	        except Exception:
    64	            await session.rollback()
    65	            raise

codex
1. [providers/storage.py:30](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:30) `high`  
The LocalStorage traversal guard is wrong. It uses `str(candidate).startswith(str(self._base))`, which is a string-prefix check, not an ancestry check. With a base like `/data/blobs`, a key like `../blobs_evil/secret` resolves to `/data/blobs_evil/secret` and still passes. That makes `put/get/delete/exists` capable of reading, overwriting, or deleting files outside the blob root once any caller can control the key.  
Fix: resolve the path and validate it structurally with `candidate.relative_to(self._base)` or `candidate.is_relative_to(self._base)`; reject absolute paths and any key that escapes the base.

2. [models/filings.py:28](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/filings.py:28), [models/documents.py:59](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/documents.py:59), [models/evidence.py:25](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/evidence.py:25), [models/workflow.py:24](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/workflow.py:24), mirrored in [f28c812fca98_initial_schema.py:182](/Users/anishguntreddi/Documents/hackathon/apps/api/migrations/versions/f28c812fca98_initial_schema.py:182) and [f28c812fca98_initial_schema.py:259](/Users/anishguntreddi/Documents/hackathon/apps/api/migrations/versions/f28c812fca98_initial_schema.py:259) `high`  
The schema does not enforce tenant-consistent foreign keys. Child tables carry their own `org_id`, but their foreign keys point only at parent `id`. That allows invalid cross-tenant graphs like `filings.org_id = A` referencing `opportunities.id` from org B, or `document_chunks.org_id = A` referencing a document in org B. I did not find a direct bypass in the current `/orgs` routes, but the foundation schema itself does not satisfy `CON-5`; one missed check in later phases becomes a real tenant break.  
Fix: add `UNIQUE (org_id, id)` on every org-scoped parent table and convert child references to composite FKs like `(org_id, opportunity_id) -> opportunities(org_id, id)`.

3. [api/auth.py:70](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:70), [api/auth.py:91](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:91), [db/base.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/db/base.py:53), [providers/audit.py:57](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:57) `high`  
`auth.register` and `auth.login` emit audit events without `org_id`, but the Postgres audit schema requires `org_id NOT NULL` via `OrgScopedMixin`. In the default `AUDIT_SINK=postgres` path, those inserts fail and are swallowed, so required auth audit events are silently lost.  
Fix: either model global auth events explicitly with schema support, or emit org-scoped auth events only when an org context exists. In either case, stop treating required audit writes as best-effort.

4. [providers/audit.py:58](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:58), [db/session.py:43](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/db/session.py:43), with call sites at [api/orgs.py:24](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/orgs.py:24), [api/orgs.py:100](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/orgs.py:100), and [api/auth.py:66](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:66) `medium`  
The audit sink opens and commits its own session before the request transaction commits. `get_session()` only commits after the handler returns, so if the outer transaction later rolls back, the audit row still says the action happened. That creates phantom `org.created` / `org.member_added` events and breaks audit integrity.  
Fix: write audit/outbox rows in the same transaction as the business change, then publish them after commit.

5. [providers/__init__.py:100](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/__init__.py:100), [providers/llm.py:62](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/llm.py:62), [providers/embeddings.py:49](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/embeddings.py:49), [auth/firebase.py:20](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/auth/firebase.py:20) `medium`  
The `SecretsProvider` abstraction exists but the code paths that actually need secrets bypass it and read directly from `Settings`/env. Setting `SECRETS_BACKEND=gcp_secret_manager` does not move Gemini or Firebase secret material out of env/files, so `CON-4` is not actually implemented.  
Fix: resolve secret material through `get_secrets()` in provider constructors and keep only secret identifiers in config.

6. [core/security.py:28](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/core/security.py:28) `low`  
`verify_password()` catches every unexpected exception and returns `False`. A malformed Argon2 hash or backend failure is therefore masked as “wrong password”, which hides auth subsystem failures and corrupted credential data.  
Fix: catch only expected mismatch/invalid-hash exceptions; log and fail closed on anything unexpected.

**VERDICT**  
M0 is not sound to build on yet. I did not find a direct cross-org bypass in the current `require_org` / `/orgs` route logic, and access-vs-refresh token separation itself looks fine, but the foundation still has must-fix defects:

- Fix the LocalStorage traversal bug.
- Enforce tenant-consistent composite foreign keys across org-scoped tables.
- Repair the audit path: auth events are currently dropped, and successful audit rows can be written for rolled-back business actions.
- Wire real providers through the secret manager abstraction.

Verification note: this was source review only. I could not run `pytest` here because the sandbox has no usable writable temp directory, so pytest fails during startup before tests execute.
tokens used
139,731
1. [providers/storage.py:30](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:30) `high`  
The LocalStorage traversal guard is wrong. It uses `str(candidate).startswith(str(self._base))`, which is a string-prefix check, not an ancestry check. With a base like `/data/blobs`, a key like `../blobs_evil/secret` resolves to `/data/blobs_evil/secret` and still passes. That makes `put/get/delete/exists` capable of reading, overwriting, or deleting files outside the blob root once any caller can control the key.  
Fix: resolve the path and validate it structurally with `candidate.relative_to(self._base)` or `candidate.is_relative_to(self._base)`; reject absolute paths and any key that escapes the base.

2. [models/filings.py:28](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/filings.py:28), [models/documents.py:59](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/documents.py:59), [models/evidence.py:25](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/evidence.py:25), [models/workflow.py:24](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/models/workflow.py:24), mirrored in [f28c812fca98_initial_schema.py:182](/Users/anishguntreddi/Documents/hackathon/apps/api/migrations/versions/f28c812fca98_initial_schema.py:182) and [f28c812fca98_initial_schema.py:259](/Users/anishguntreddi/Documents/hackathon/apps/api/migrations/versions/f28c812fca98_initial_schema.py:259) `high`  
The schema does not enforce tenant-consistent foreign keys. Child tables carry their own `org_id`, but their foreign keys point only at parent `id`. That allows invalid cross-tenant graphs like `filings.org_id = A` referencing `opportunities.id` from org B, or `document_chunks.org_id = A` referencing a document in org B. I did not find a direct bypass in the current `/orgs` routes, but the foundation schema itself does not satisfy `CON-5`; one missed check in later phases becomes a real tenant break.  
Fix: add `UNIQUE (org_id, id)` on every org-scoped parent table and convert child references to composite FKs like `(org_id, opportunity_id) -> opportunities(org_id, id)`.

3. [api/auth.py:70](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:70), [api/auth.py:91](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:91), [db/base.py:53](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/db/base.py:53), [providers/audit.py:57](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:57) `high`  
`auth.register` and `auth.login` emit audit events without `org_id`, but the Postgres audit schema requires `org_id NOT NULL` via `OrgScopedMixin`. In the default `AUDIT_SINK=postgres` path, those inserts fail and are swallowed, so required auth audit events are silently lost.  
Fix: either model global auth events explicitly with schema support, or emit org-scoped auth events only when an org context exists. In either case, stop treating required audit writes as best-effort.

4. [providers/audit.py:58](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:58), [db/session.py:43](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/db/session.py:43), with call sites at [api/orgs.py:24](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/orgs.py:24), [api/orgs.py:100](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/orgs.py:100), and [api/auth.py:66](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/auth.py:66) `medium`  
The audit sink opens and commits its own session before the request transaction commits. `get_session()` only commits after the handler returns, so if the outer transaction later rolls back, the audit row still says the action happened. That creates phantom `org.created` / `org.member_added` events and breaks audit integrity.  
Fix: write audit/outbox rows in the same transaction as the business change, then publish them after commit.

5. [providers/__init__.py:100](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/__init__.py:100), [providers/llm.py:62](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/llm.py:62), [providers/embeddings.py:49](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/embeddings.py:49), [auth/firebase.py:20](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/auth/firebase.py:20) `medium`  
The `SecretsProvider` abstraction exists but the code paths that actually need secrets bypass it and read directly from `Settings`/env. Setting `SECRETS_BACKEND=gcp_secret_manager` does not move Gemini or Firebase secret material out of env/files, so `CON-4` is not actually implemented.  
Fix: resolve secret material through `get_secrets()` in provider constructors and keep only secret identifiers in config.

6. [core/security.py:28](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/core/security.py:28) `low`  
`verify_password()` catches every unexpected exception and returns `False`. A malformed Argon2 hash or backend failure is therefore masked as “wrong password”, which hides auth subsystem failures and corrupted credential data.  
Fix: catch only expected mismatch/invalid-hash exceptions; log and fail closed on anything unexpected.

**VERDICT**  
M0 is not sound to build on yet. I did not find a direct cross-org bypass in the current `require_org` / `/orgs` route logic, and access-vs-refresh token separation itself looks fine, but the foundation still has must-fix defects:

- Fix the LocalStorage traversal bug.
- Enforce tenant-consistent composite foreign keys across org-scoped tables.
- Repair the audit path: auth events are currently dropped, and successful audit rows can be written for rolled-back business actions.
- Wire real providers through the secret manager abstraction.

Verification note: this was source review only. I could not run `pytest` here because the sandbox has no usable writable temp directory, so pytest fails during startup before tests execute.
CODEX_EXIT=0

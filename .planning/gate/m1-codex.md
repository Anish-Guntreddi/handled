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
session id: 019ee16e-b179-7fd2-b864-05431cb54d26
--------
user
Independent review of CaptureOS Phase M1 (Company Brain + ingestion). Spec:
captureos-engineering-prd.md (FR-CB-*, FR-DI-*, CON-2/3/5). Review the NEW code since the
M0 gate: captureos/agents/ (base.py, company_brain.py), captureos/workflows/ (engine.py,
pipelines.py, dispatch.py), captureos/ingestion/ (chunking, service, website), captureos/
services/ (company_brain, documents), and api/ (company_profile, documents, workflows).

Find REAL defects only, with file:line + severity + fix. Prioritize:
1. SSRF: fetch_website_text fetches a user-supplied URL server-side — can it reach
   localhost/169.254.169.254/internal hosts or non-http schemes?
2. Resource/DoS: blob upload reads the full body into memory with no size cap.
3. CON-2: is every materialized evidence_item sourced? Any unsourced claim path?
4. CON-5: org isolation on documents/blobs/workflow-runs and the agent_run/audit rows.
5. Correctness: content-hash dedupe (FR-DI-6), schema-retry (FR-RE-2 / §10.5), the
   commit-then-dispatch handoff, override preservation on rebuild (FR-CB-6).
6. Any silent failure or swallowed exception that hides a real error.
End with a VERDICT and the must-fix list.
codex
Reviewing the M1 delta against the PRD and the specified risk areas. I’m starting by locating the M0 baseline, reading the spec sections, and diffing the named paths so the review stays constrained to the new code.
exec
/bin/zsh -lc 'pwd && git status --short && git tag --list && git branch --all --no-color' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
/Users/anishguntreddi/Documents/hackathon
 M apps/api/captureos/api/router.py
 M apps/api/captureos/main.py
 M apps/api/captureos/models/audit.py
 M apps/api/migrations/versions/f28c812fca98_initial_schema.py
 M apps/api/pyproject.toml
 M apps/api/tests/conftest.py
 M apps/api/tests/test_security.py
 M apps/api/uv.lock
 M apps/web/src/app/dashboard/page.tsx
 M apps/web/src/lib/api.ts
 M apps/web/src/lib/types.ts
?? .planning/gate/m1-codex-prompt.txt
?? .planning/gate/m1-codex.md
?? apps/api/captureos/agents/
?? apps/api/captureos/api/company_profile.py
?? apps/api/captureos/api/documents.py
?? apps/api/captureos/api/workflows.py
?? apps/api/captureos/ingestion/
?? apps/api/captureos/schemas/company.py
?? apps/api/captureos/schemas/document.py
?? apps/api/captureos/schemas/workflow.py
?? apps/api/captureos/services/
?? apps/api/captureos/workflows/
?? apps/api/tests/test_company_brain.py
?? apps/api/tests/test_ingestion.py
?? apps/web/src/app/orgs/
* main

exec
/bin/zsh -lc "rg -n \"FR-CB-|FR-DI-|CON-2|CON-3|CON-5|FR-RE-2|10\\.5|FR-CB-6|FR-DI-6\" captureos-engineering-prd.md" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
103:### 5.1 Company Brain (`FR-CB-*`)
105:- **FR-CB-1** — Accept inputs: company name (required), website URL, industry, location, optional UEI, optional uploaded documents, optional free-text description.
106:- **FR-CB-2** — Ingest the website URL (fetch + parse primary pages) and produce structured profile fields: services, target customers, NAICS guesses (with confidence), funding/grant categories, certifications detected vs. likely-missing, and past-performance evidence found.
107:- **FR-CB-3** — Produce a **capability-statement draft** from the profile and a **missing-information checklist** listing fields that could not be populated.
108:- **FR-CB-4** — Persist each derived fact as an `evidence_item` with a `source` reference (which page/document it came from).
109:- **FR-CB-5** — Allow the user to edit/confirm/override any profile field; user overrides are themselves stored as `user_provided` evidence and take precedence over inferred values.
110:- **FR-CB-6** — The profile must be regenerable/refreshable on demand without destroying user overrides.
112:### 5.2 Document ingestion & RAG (`FR-DI-*`)
114:- **FR-DI-1** — Accept uploads (PDF, DOCX, common image formats); store the binary in Cloud Storage; create a `documents` row.
115:- **FR-DI-2** — Extract text/structure using Document AI (with a plain-text fallback extractor for simple files); chunk into `document_chunks`; embed each chunk and store the vector for retrieval.
116:- **FR-DI-3** — Support pasting raw solicitation text (no file) and treat it as an ingestable document.
117:- **FR-DI-4** — Support an **optional Google Drive folder connection**; for MVP a *simulated connector* (user provides a folder export or selected files) is acceptable, behind the same internal interface as a future real connector.
118:- **FR-DI-5** — Retrieval (RAG) must return chunks with their `document_id` + locator so downstream citations resolve to a source.
119:- **FR-DI-6** — Ingestion is idempotent: re-uploading the same file does not duplicate chunks/evidence (dedupe by content hash).
143:- **FR-RE-2** — Extraction output must be schema-validated (Pydantic); malformed model output triggers a bounded retry (see §10.5), then a flagged-for-review state rather than a silent failure.
192:- **CON-2** — No claim-bearing output (profile fact, recommendation rationale, narrative sentence) ships without a resolvable citation to a `source` or `evidence_item`.
193:- **CON-3** — Every agent action that touches data or an external source is logged to the audit trail.
195:- **CON-5** — All data access is org-scoped; one org can never read another org's data.
331:Conventions: every table has `id uuid pk`, `org_id uuid` (except global `users`), `created_at`, `updated_at`. All non-`users` queries are filtered by `org_id` (`CON-5`).
366:| content_hash | text | dedupe (`FR-DI-6`) |
399:| source_id | uuid | fk → sources (`CON-2`) |
436:| source_id | uuid | fk (`CON-2`) |
554:  body: { field overrides }      # stored as user_provided evidence (FR-CB-5)
654:All errors return `{ error: { code, message, details? } }`. Async failures are reflected in the workflow run (`status=failed`, plus a step-level error and an audit event), never as a silent empty result (`FR-RE-2`).
662:Each agent is a Python module with a **typed Pydantic input and output contract**, invoked by a workflow step. Agents call Gemini with a structured prompt and must return schema-valid JSON (validated on receipt). Agents are **stateless** — all state lives in the workflow/DB. The workflow engine (not the agents) decides sequencing, retries, and human gates. This makes every step observable and satisfies `CON-3`.
672:| 5 | **Requirement Extraction** | Extract structured requirements. | solicitation text/docs | filing_requirements[] | Gemini Pro | malformed JSON, long docs | schema-retry (§10.5); chunk + merge |
709:Every agent that emits a claim must attach, per claim, `{ source_id, locator }` (or `{ evidence_item_id }`). The Audit & Citation agent rejects any output containing a claim without a resolvable reference; the affected `generated_document` cannot reach `status=ready` (`CON-2`, `FR-PB-2`).
711:### 10.5 Retry & failure semantics
713:- **Schema-retry**: if an agent's output fails Pydantic validation, re-prompt up to N=2 times with the validation error appended; on final failure, set step `failed`, run `failed` (or `needs_input` if user-resolvable), and emit an audit event. Never return a silently empty result (`FR-RE-2`).
722:- **NFR-1 Multi-tenancy & authz** — every data access is org-scoped; role checks (`owner`/`editor`/`viewer`) on mutating routes (`CON-5`).
730:- **NFR-9 Compliance/legal** — `CON-1` (no auto-submission), `CON-2` (sourced claims), `CON-3` (audit trail) are product-level legal protections, not optional.
763:| Engineering | Citation coverage of shipped claims | 100% (`CON-2` is enforced) |
775:| LLM hallucination / fabricated citations | Trust + legal exposure | Enforced citation contract (`CON-2`); Audit/Citation agent blocks unsourced claims; conservative match statuses |

exec
/bin/zsh -lc "rg --files captureos api | rg \"(agents/(base|company_brain)\\.py|workflows/(engine|pipelines|dispatch)\\.py|ingestion/(chunking|service|website).*\\.py|services/(company_brain|documents).*\\.py|api/(company_profile|documents|workflows).*\\.py)"'$"' in /Users/anishguntreddi/Documents/hackathon
 exited 1 in 0ms:
rg: captureos: No such file or directory (os error 2)
rg: api: No such file or directory (os error 2)

codex
The repo root is `apps/api`, not `captureos/` at top level. I have the PRD anchors and the target codepaths; next I’m mapping the exact files and the baseline branch state before reading for defects.
exec
/bin/zsh -lc 'git log --oneline --decorate --graph --max-count=30 --all' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
* 1e48a2e (HEAD -> main) M0 gate: security hardening + phase verification (codex + audit + qa)
* b42a61b M0 Foundation: monorepo, full schema, auth, org multi-tenancy, providers, web

exec
/bin/zsh -lc "rg --files apps/api/captureos apps/api/tests | rg \"(agents/(base|company_brain)\\.py|workflows/(engine|pipelines|dispatch)\\.py|ingestion/(chunking|service|website).*\\.py|services/(company_brain|documents).*\\.py|api/(company_profile|documents|workflows).*\\.py|tests/test_(company_brain|ingestion)\\.py)"'$"' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/tests/test_ingestion.py
apps/api/tests/test_company_brain.py
apps/api/captureos/services/documents.py
apps/api/captureos/services/company_brain.py
apps/api/captureos/agents/base.py
apps/api/captureos/agents/company_brain.py
apps/api/captureos/workflows/pipelines.py
apps/api/captureos/workflows/engine.py
apps/api/captureos/workflows/dispatch.py
apps/api/captureos/api/workflows.py
apps/api/captureos/api/documents.py
apps/api/captureos/api/company_profile.py
apps/api/captureos/ingestion/website.py
apps/api/captureos/ingestion/chunking.py
apps/api/captureos/ingestion/service.py

exec
/bin/zsh -lc 'find apps/api/captureos -maxdepth 3 -type f | sort' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/__init__.py
apps/api/captureos/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/__pycache__/config.cpython-313.pyc
apps/api/captureos/__pycache__/logging.cpython-313.pyc
apps/api/captureos/__pycache__/main.cpython-313.pyc
apps/api/captureos/agents/__init__.py
apps/api/captureos/agents/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/agents/__pycache__/base.cpython-313.pyc
apps/api/captureos/agents/__pycache__/company_brain.cpython-313.pyc
apps/api/captureos/agents/base.py
apps/api/captureos/agents/company_brain.py
apps/api/captureos/api/__init__.py
apps/api/captureos/api/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/api/__pycache__/auth.cpython-313.pyc
apps/api/captureos/api/__pycache__/company_profile.cpython-313.pyc
apps/api/captureos/api/__pycache__/documents.cpython-313.pyc
apps/api/captureos/api/__pycache__/health.cpython-313.pyc
apps/api/captureos/api/__pycache__/orgs.cpython-313.pyc
apps/api/captureos/api/__pycache__/router.cpython-313.pyc
apps/api/captureos/api/__pycache__/workflows.cpython-313.pyc
apps/api/captureos/api/auth.py
apps/api/captureos/api/company_profile.py
apps/api/captureos/api/documents.py
apps/api/captureos/api/health.py
apps/api/captureos/api/orgs.py
apps/api/captureos/api/router.py
apps/api/captureos/api/workflows.py
apps/api/captureos/audit/__init__.py
apps/api/captureos/audit/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/audit/__pycache__/service.cpython-313.pyc
apps/api/captureos/audit/service.py
apps/api/captureos/auth/__init__.py
apps/api/captureos/auth/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/auth/__pycache__/base.cpython-313.pyc
apps/api/captureos/auth/__pycache__/local.cpython-313.pyc
apps/api/captureos/auth/base.py
apps/api/captureos/auth/firebase.py
apps/api/captureos/auth/local.py
apps/api/captureos/config.py
apps/api/captureos/core/__init__.py
apps/api/captureos/core/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/core/__pycache__/deps.cpython-313.pyc
apps/api/captureos/core/__pycache__/errors.cpython-313.pyc
apps/api/captureos/core/__pycache__/security.cpython-313.pyc
apps/api/captureos/core/deps.py
apps/api/captureos/core/errors.py
apps/api/captureos/core/security.py
apps/api/captureos/db/__init__.py
apps/api/captureos/db/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/db/__pycache__/base.cpython-313.pyc
apps/api/captureos/db/__pycache__/session.cpython-313.pyc
apps/api/captureos/db/base.py
apps/api/captureos/db/migrate.py
apps/api/captureos/db/session.py
apps/api/captureos/ingestion/__init__.py
apps/api/captureos/ingestion/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/ingestion/__pycache__/chunking.cpython-313.pyc
apps/api/captureos/ingestion/__pycache__/service.cpython-313.pyc
apps/api/captureos/ingestion/__pycache__/website.cpython-313.pyc
apps/api/captureos/ingestion/chunking.py
apps/api/captureos/ingestion/service.py
apps/api/captureos/ingestion/website.py
apps/api/captureos/logging.py
apps/api/captureos/main.py
apps/api/captureos/models/__init__.py
apps/api/captureos/models/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/models/__pycache__/audit.cpython-313.pyc
apps/api/captureos/models/__pycache__/billing.cpython-313.pyc
apps/api/captureos/models/__pycache__/company.cpython-313.pyc
apps/api/captureos/models/__pycache__/documents.cpython-313.pyc
apps/api/captureos/models/__pycache__/enums.cpython-313.pyc
apps/api/captureos/models/__pycache__/evidence.cpython-313.pyc
apps/api/captureos/models/__pycache__/filings.cpython-313.pyc
apps/api/captureos/models/__pycache__/opportunities.cpython-313.pyc
apps/api/captureos/models/__pycache__/org.cpython-313.pyc
apps/api/captureos/models/__pycache__/workflow.cpython-313.pyc
apps/api/captureos/models/audit.py
apps/api/captureos/models/billing.py
apps/api/captureos/models/company.py
apps/api/captureos/models/documents.py
apps/api/captureos/models/enums.py
apps/api/captureos/models/evidence.py
apps/api/captureos/models/filings.py
apps/api/captureos/models/opportunities.py
apps/api/captureos/models/org.py
apps/api/captureos/models/workflow.py
apps/api/captureos/providers/__init__.py
apps/api/captureos/providers/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/providers/__pycache__/audit.cpython-313.pyc
apps/api/captureos/providers/__pycache__/base.cpython-313.pyc
apps/api/captureos/providers/__pycache__/docparse.cpython-313.pyc
apps/api/captureos/providers/__pycache__/embeddings.cpython-313.pyc
apps/api/captureos/providers/__pycache__/llm.cpython-313.pyc
apps/api/captureos/providers/__pycache__/queue.cpython-313.pyc
apps/api/captureos/providers/__pycache__/secrets.cpython-313.pyc
apps/api/captureos/providers/__pycache__/storage.cpython-313.pyc
apps/api/captureos/providers/audit.py
apps/api/captureos/providers/base.py
apps/api/captureos/providers/docparse.py
apps/api/captureos/providers/embeddings.py
apps/api/captureos/providers/llm.py
apps/api/captureos/providers/queue.py
apps/api/captureos/providers/secrets.py
apps/api/captureos/providers/storage.py
apps/api/captureos/schemas/__init__.py
apps/api/captureos/schemas/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/auth.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/common.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/company.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/document.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/org.cpython-313.pyc
apps/api/captureos/schemas/__pycache__/workflow.cpython-313.pyc
apps/api/captureos/schemas/auth.py
apps/api/captureos/schemas/common.py
apps/api/captureos/schemas/company.py
apps/api/captureos/schemas/document.py
apps/api/captureos/schemas/org.py
apps/api/captureos/schemas/workflow.py
apps/api/captureos/scripts/__init__.py
apps/api/captureos/scripts/seed.py
apps/api/captureos/services/__init__.py
apps/api/captureos/services/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/services/__pycache__/company_brain.cpython-313.pyc
apps/api/captureos/services/__pycache__/documents.cpython-313.pyc
apps/api/captureos/services/company_brain.py
apps/api/captureos/services/documents.py
apps/api/captureos/worker/__init__.py
apps/api/captureos/worker/main.py
apps/api/captureos/workflows/__init__.py
apps/api/captureos/workflows/__pycache__/__init__.cpython-313.pyc
apps/api/captureos/workflows/__pycache__/dispatch.cpython-313.pyc
apps/api/captureos/workflows/__pycache__/engine.cpython-313.pyc
apps/api/captureos/workflows/__pycache__/pipelines.cpython-313.pyc
apps/api/captureos/workflows/dispatch.py
apps/api/captureos/workflows/engine.py
apps/api/captureos/workflows/pipelines.py

codex
I found the baseline: `1e48a2e` is the M0 gate commit, and the Phase M1 code is currently uncommitted on top of it. I’m pulling the exact diffs for the targeted modules and the adjacent schema/model pieces needed to validate org scoping, evidence sourcing, and workflow/audit persistence.
exec
/bin/zsh -lc 'git diff --name-status 1e48a2e -- apps/api/captureos/agents apps/api/captureos/workflows apps/api/captureos/ingestion apps/api/captureos/services apps/api/captureos/api apps/api/captureos/models apps/api/captureos/schemas apps/api/tests' in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc 'git diff --stat 1e48a2e -- apps/api/captureos/agents apps/api/captureos/workflows apps/api/captureos/ingestion apps/api/captureos/services apps/api/captureos/api apps/api/captureos/models apps/api/captureos/schemas apps/api/tests' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
 apps/api/captureos/api/router.py   |  6 +++++-
 apps/api/captureos/models/audit.py | 13 +++++++------
 apps/api/tests/conftest.py         |  9 +++++++--
 apps/api/tests/test_security.py    |  6 ++++--
 4 files changed, 23 insertions(+), 11 deletions(-)

 succeeded in 0ms:
M	apps/api/captureos/api/router.py
M	apps/api/captureos/models/audit.py
M	apps/api/tests/conftest.py
M	apps/api/tests/test_security.py

exec
/bin/zsh -lc 'git diff --unified=20 1e48a2e -- apps/api/captureos/models/audit.py apps/api/captureos/models/workflow.py apps/api/captureos/models/documents.py apps/api/captureos/models/evidence.py apps/api/captureos/models/company.py apps/api/captureos/schemas/company.py apps/api/captureos/schemas/document.py apps/api/captureos/schemas/workflow.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
diff --git a/apps/api/captureos/models/audit.py b/apps/api/captureos/models/audit.py
index 0c5edcc..065429f 100644
--- a/apps/api/captureos/models/audit.py
+++ b/apps/api/captureos/models/audit.py
@@ -1,54 +1,55 @@
 """Postgres mirror of the append-only audit event stream (PRD §8.4, FR-AU-2).
 
 In production the authoritative stream is BigQuery; this table powers the in-app
 dashboard and CSV/JSON export, and is the default sink in local/dev (AUDIT_SINK=postgres).
 Rows are append-only — never updated or deleted (CON-3).
 """
 
 from __future__ import annotations
 
 import uuid
 from datetime import datetime
 
-from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
+from sqlalchemy import DateTime, Index, Integer, String, func
 from sqlalchemy.dialects.postgresql import JSONB
 from sqlalchemy.dialects.postgresql import UUID as PGUUID
 from sqlalchemy.orm import Mapped, mapped_column
 
 from captureos.db.base import Base, UUIDPKMixin
 from captureos.models.enums import ActorType
 
 
 class AuditEvent(UUIDPKMixin, Base):
     __tablename__ = "audit_events"
     __table_args__ = (
         Index("ix_audit_events_org_occurred", "org_id", "occurred_at"),
         Index("ix_audit_events_run", "run_id"),
     )
 
-    # Nullable: system/auth events (login, register) have no org context (CON-3, FR-AU-2).
+    # Nullable + NO FK on purpose: the audit stream is append-only and decoupled (matches
+    # the BigQuery design, PRD §8.4). It is written in its own transaction and must not be
+    # constrained by referential integrity to rows that may still be uncommitted in the
+    # caller's transaction, nor cascade-deleted when an org is removed (it's a legal record).
+    # System/auth events (login, register) also legitimately have no org (CON-3, FR-AU-2).
     org_id: Mapped[uuid.UUID | None] = mapped_column(
-        PGUUID(as_uuid=True),
-        ForeignKey("organizations.id", ondelete="CASCADE"),
-        nullable=True,
-        index=True,
+        PGUUID(as_uuid=True), nullable=True, index=True
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
/bin/zsh -lc 'wc -l apps/api/captureos/agents/base.py apps/api/captureos/agents/company_brain.py apps/api/captureos/workflows/engine.py apps/api/captureos/workflows/pipelines.py apps/api/captureos/workflows/dispatch.py apps/api/captureos/ingestion/chunking.py apps/api/captureos/ingestion/service.py apps/api/captureos/ingestion/website.py apps/api/captureos/services/company_brain.py apps/api/captureos/services/documents.py apps/api/captureos/api/company_profile.py apps/api/captureos/api/documents.py apps/api/captureos/api/workflows.py apps/api/captureos/api/router.py apps/api/captureos/models/audit.py apps/api/captureos/models/workflow.py apps/api/captureos/models/documents.py apps/api/captureos/models/evidence.py apps/api/captureos/models/company.py apps/api/captureos/schemas/company.py apps/api/captureos/schemas/document.py apps/api/captureos/schemas/workflow.py apps/api/tests/test_company_brain.py apps/api/tests/test_ingestion.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     167 apps/api/captureos/agents/base.py
     253 apps/api/captureos/agents/company_brain.py
     137 apps/api/captureos/workflows/engine.py
      45 apps/api/captureos/workflows/pipelines.py
      36 apps/api/captureos/workflows/dispatch.py
      62 apps/api/captureos/ingestion/chunking.py
     104 apps/api/captureos/ingestion/service.py
      99 apps/api/captureos/ingestion/website.py
     184 apps/api/captureos/services/company_brain.py
      44 apps/api/captureos/services/documents.py
     150 apps/api/captureos/api/company_profile.py
     211 apps/api/captureos/api/documents.py
      44 apps/api/captureos/api/workflows.py
      16 apps/api/captureos/api/router.py
      55 apps/api/captureos/models/audit.py
      97 apps/api/captureos/models/workflow.py
      71 apps/api/captureos/models/documents.py
      61 apps/api/captureos/models/evidence.py
      52 apps/api/captureos/models/company.py
      51 apps/api/captureos/schemas/company.py
      40 apps/api/captureos/schemas/document.py
      26 apps/api/captureos/schemas/workflow.py
      83 apps/api/tests/test_company_brain.py
      93 apps/api/tests/test_ingestion.py
    2181 total

codex
I’ve narrowed it to about 2.2k lines across the touched modules. I’m reading the SSRF/upload/workflow paths first because those are the highest-likelihood must-fix areas, then I’ll trace evidence/org-scope invariants through the service and API layers.
exec
/bin/zsh -lc "nl -ba apps/api/captureos/workflows/engine.py && printf '\\n---\\n' && nl -ba apps/api/captureos/workflows/pipelines.py && printf '\\n---\\n' && nl -ba apps/api/captureos/workflows/dispatch.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/ingestion/website.py && printf '\\n---\\n' && nl -ba apps/api/captureos/api/documents.py && printf '\\n---\\n' && nl -ba apps/api/captureos/services/documents.py && printf '\\n---\\n' && nl -ba apps/api/captureos/ingestion/service.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Pipeline executor. Runs an ordered list of named steps for a workflow_run, recording
     2	each step's status, the agent runs inside it, and audit events (CON-3, NFR-8).
     3	
     4	Failures are always visible: a failed step marks the run ``failed`` (or ``needs_input``
     5	when a step raises ``NeedsInput``) with the error recorded — never a silent empty result.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	from collections.abc import Awaitable, Callable
    11	from dataclasses import dataclass
    12	
    13	from sqlalchemy import select
    14	from sqlalchemy.ext.asyncio import AsyncSession
    15	
    16	from captureos.agents.base import AgentContext
    17	from captureos.audit import record_event
    18	from captureos.logging import get_logger
    19	from captureos.models.enums import StepStatus, WorkflowStatus
    20	from captureos.models.workflow import WorkflowRun, WorkflowStep
    21	
    22	logger = get_logger(__name__)
    23	
    24	
    25	class NeedsInput(Exception):
    26	    """A step raises this to pause the run pending user input (e.g. a missing document)."""
    27	
    28	
    29	@dataclass(slots=True)
    30	class StepContext:
    31	    session: AsyncSession
    32	    run: WorkflowRun
    33	    step: WorkflowStep
    34	
    35	    @property
    36	    def org_id(self):
    37	        return self.run.org_id
    38	
    39	    @property
    40	    def params(self) -> dict:
    41	        return self.run.input_params or {}
    42	
    43	    def merge_results(self, **values) -> None:
    44	        """Accumulate partial results so the client can poll them as steps complete."""
    45	        current = dict(self.run.partial_results or {})
    46	        current.update(values)
    47	        self.run.partial_results = current
    48	
    49	    def agent_context(self) -> AgentContext:
    50	        return AgentContext(
    51	            session=self.session,
    52	            org_id=self.run.org_id,
    53	            run_id=self.run.id,
    54	            step_id=self.step.id,
    55	            filing_id=self.run.filing_id,
    56	        )
    57	
    58	
    59	StepFn = Callable[[StepContext], Awaitable[None]]
    60	
    61	
    62	async def _get_or_create_step(
    63	    session: AsyncSession, run: WorkflowRun, name: str, ordinal: int
    64	) -> WorkflowStep:
    65	    existing = await session.execute(
    66	        select(WorkflowStep).where(WorkflowStep.run_id == run.id, WorkflowStep.name == name)
    67	    )
    68	    step = existing.scalar_one_or_none()
    69	    if step is None:
    70	        step = WorkflowStep(
    71	            org_id=run.org_id,
    72	            run_id=run.id,
    73	            name=name,
    74	            ordinal=ordinal,
    75	            status=StepStatus.pending.value,
    76	        )
    77	        session.add(step)
    78	        await session.flush()
    79	    return step
    80	
    81	
    82	async def run_pipeline(
    83	    session: AsyncSession,
    84	    run: WorkflowRun,
    85	    steps: list[tuple[str, StepFn]],
    86	    *,
    87	    time_saved_minutes: int | None = None,
    88	) -> None:
    89	    run.status = WorkflowStatus.running.value
    90	    await session.flush()
    91	    await record_event(
    92	        "workflow.started", org_id=run.org_id, run_id=run.id, payload={"type": run.type}
    93	    )
    94	
    95	    for ordinal, (name, fn) in enumerate(steps):
    96	        step = await _get_or_create_step(session, run, name, ordinal)
    97	        if step.status == StepStatus.done.value:
    98	            continue  # idempotent: already completed (re-delivery / resume)
    99	
   100	        step.status = StepStatus.running.value
   101	        await session.flush()
   102	        try:
   103	            await fn(StepContext(session=session, run=run, step=step))
   104	        except NeedsInput as ni:
   105	            step.status = StepStatus.skipped.value
   106	            run.status = WorkflowStatus.needs_input.value
   107	            run.error = str(ni)
   108	            await session.flush()
   109	            await record_event(
   110	                "workflow.needs_input", org_id=run.org_id, run_id=run.id, status="needs_input"
   111	            )
   112	            return
   113	        except Exception as exc:  # noqa: BLE001 - failure must be captured, not propagated
   114	            step.status = StepStatus.failed.value
   115	            step.error = str(exc)
   116	            run.status = WorkflowStatus.failed.value
   117	            run.error = str(exc)
   118	            await session.flush()
   119	            await record_event(
   120	                "workflow.failed",
   121	                org_id=run.org_id,
   122	                run_id=run.id,
   123	                step_id=step.id,
   124	                status="failed",
   125	                payload={"error": str(exc), "step": name},
   126	            )
   127	            logger.error("workflow.step_failed", run_id=str(run.id), step=name, error=str(exc))
   128	            return
   129	
   130	        step.status = StepStatus.done.value
   131	        await session.flush()
   132	
   133	    run.status = WorkflowStatus.succeeded.value
   134	    if time_saved_minutes is not None:
   135	        run.time_saved_minutes = time_saved_minutes
   136	    await session.flush()
   137	    await record_event("workflow.succeeded", org_id=run.org_id, run_id=run.id, status="succeeded")

---
     1	"""Pipeline registry: maps a workflow type to its ordered steps. Steps in a pipeline
     2	share local state via closures (avoids leaking working data into client-visible results)."""
     3	
     4	from __future__ import annotations
     5	
     6	from captureos.models.enums import WorkflowType
     7	from captureos.models.workflow import WorkflowRun
     8	from captureos.services.company_brain import gather_company_sources, run_company_brain
     9	from captureos.services.documents import run_document_ingest
    10	from captureos.workflows.engine import StepContext, StepFn
    11	
    12	# Time-saved heuristic per workflow type, in minutes (FR-AU-3). Tunable.
    13	TIME_SAVED: dict[str, int] = {
    14	    WorkflowType.company_brain.value: 60,
    15	    WorkflowType.document_ingest.value: 10,
    16	}
    17	
    18	
    19	def _company_brain_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    20	    state: dict = {}
    21	
    22	    async def gather(ctx: StepContext) -> None:
    23	        state.update(await gather_company_sources(ctx))
    24	
    25	    async def build(ctx: StepContext) -> None:
    26	        await run_company_brain(ctx, state)
    27	
    28	    return [("gather_sources", gather), ("build_profile", build)]
    29	
    30	
    31	def _document_ingest_pipeline(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    32	    return [("ingest", run_document_ingest)]
    33	
    34	
    35	_PIPELINES = {
    36	    WorkflowType.company_brain.value: _company_brain_pipeline,
    37	    WorkflowType.document_ingest.value: _document_ingest_pipeline,
    38	}
    39	
    40	
    41	def build_steps(run: WorkflowRun) -> list[tuple[str, StepFn]]:
    42	    builder = _PIPELINES.get(run.type)
    43	    if builder is None:
    44	        raise ValueError(f"No pipeline registered for workflow type {run.type!r}")
    45	    return builder(run)

---
     1	"""Workflow dispatch. M1 executes via FastAPI BackgroundTasks (in-process); M2 replaces
     2	this with a durable queue publish + worker consumption (same pipeline code)."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	
     8	from fastapi import BackgroundTasks
     9	
    10	from captureos.db.session import session_scope
    11	from captureos.logging import get_logger
    12	from captureos.models.workflow import WorkflowRun
    13	from captureos.workflows.engine import run_pipeline
    14	from captureos.workflows.pipelines import TIME_SAVED, build_steps
    15	
    16	logger = get_logger(__name__)
    17	
    18	
    19	async def execute_workflow_run(run_id: uuid.UUID) -> None:
    20	    """Run a workflow_run to completion in its own session."""
    21	    async with session_scope() as session:
    22	        run = await session.get(WorkflowRun, run_id)
    23	        if run is None:
    24	            logger.error("workflow.run_missing", run_id=str(run_id))
    25	            return
    26	        try:
    27	            steps = build_steps(run)
    28	        except ValueError as exc:
    29	            run.status = "failed"
    30	            run.error = str(exc)
    31	            return
    32	        await run_pipeline(session, run, steps, time_saved_minutes=TIME_SAVED.get(run.type))
    33	
    34	
    35	def schedule_workflow(background_tasks: BackgroundTasks, run_id: uuid.UUID) -> None:
    36	    background_tasks.add_task(execute_workflow_run, run_id)

 succeeded in 0ms:
     1	"""Best-effort website fetcher (FR-CB-2). Stdlib HTML→text so there is no heavy parser
     2	dependency. Network failures degrade gracefully to empty text (the source URL still stands
     3	as a citation target)."""
     4	
     5	from __future__ import annotations
     6	
     7	import contextlib
     8	import ipaddress
     9	import socket
    10	from html.parser import HTMLParser
    11	from urllib.parse import urlparse
    12	
    13	import anyio
    14	import httpx
    15	
    16	from captureos.logging import get_logger
    17	
    18	logger = get_logger(__name__)
    19	
    20	
    21	async def _is_safe_public_url(url: str) -> bool:
    22	    """SSRF guard: only http(s) to a public IP. Blocks localhost, link-local
    23	    (169.254.169.254 metadata), private, and reserved ranges. Residual DNS-rebinding
    24	    risk remains without IP pinning, which httpx does not expose simply (NFR-2)."""
    25	    parsed = urlparse(url)
    26	    if parsed.scheme not in ("http", "https") or not parsed.hostname:
    27	        return False
    28	    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    29	    try:
    30	        infos = await anyio.to_thread.run_sync(
    31	            lambda: socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    32	        )
    33	    except Exception:  # noqa: BLE001 - DNS failure → treat as unreachable, degrade gracefully
    34	        return False
    35	    for info in infos:
    36	        ip = ipaddress.ip_address(info[4][0])
    37	        if (
    38	            ip.is_private
    39	            or ip.is_loopback
    40	            or ip.is_link_local
    41	            or ip.is_reserved
    42	            or ip.is_multicast
    43	            or ip.is_unspecified
    44	        ):
    45	            return False
    46	    return True
    47	
    48	_SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
    49	
    50	
    51	class _TextExtractor(HTMLParser):
    52	    def __init__(self) -> None:
    53	        super().__init__()
    54	        self._skip = 0
    55	        self.parts: list[str] = []
    56	
    57	    def handle_starttag(self, tag: str, attrs: list) -> None:
    58	        if tag in _SKIP_TAGS:
    59	            self._skip += 1
    60	
    61	    def handle_endtag(self, tag: str) -> None:
    62	        if tag in _SKIP_TAGS and self._skip > 0:
    63	            self._skip -= 1
    64	
    65	    def handle_data(self, data: str) -> None:
    66	        if self._skip == 0:
    67	            text = data.strip()
    68	            if text:
    69	                self.parts.append(text)
    70	
    71	
    72	def html_to_text(html: str) -> str:
    73	    parser = _TextExtractor()
    74	    with contextlib.suppress(Exception):  # malformed HTML should not crash ingestion
    75	        parser.feed(html)
    76	    return "\n".join(parser.parts)
    77	
    78	
    79	async def fetch_website_text(
    80	    url: str,
    81	    *,
    82	    max_chars: int = 20_000,
    83	    timeout: float = 10.0,  # noqa: ASYNC109 - httpx uses its own timeout, not asyncio.timeout
    84	) -> str:
    85	    if not await _is_safe_public_url(url):
    86	        logger.info("website.blocked_url", url=url, reason="ssrf_guard")
    87	        return ""
    88	    try:
    89	        async with httpx.AsyncClient(
    90	            follow_redirects=True,
    91	            timeout=timeout,
    92	            headers={"User-Agent": "CaptureOS/0.1 (+https://captureos.app)"},
    93	        ) as client:
    94	            resp = await client.get(url)
    95	            resp.raise_for_status()
    96	            return html_to_text(resp.text)[:max_chars]
    97	    except Exception as exc:  # noqa: BLE001 - graceful degradation (NFR-7/8)
    98	        logger.info("website.fetch_failed", url=url, error=str(exc))
    99	        return ""

---
     1	"""Document routes (PRD §9.2): initiate-upload, upload sink, ingest, paste, list/get.
     2	
     3	Uploads are org-scoped: the storage key is always prefixed with the caller's org id, and
     4	the blob routes only ever touch keys under that prefix (CON-5 + path-traversal defense)."""
     5	
     6	from __future__ import annotations
     7	
     8	import uuid
     9	
    10	from fastapi import APIRouter, BackgroundTasks, Request, Response, status
    11	from sqlalchemy import func, select
    12	
    13	from captureos.audit import record_event
    14	from captureos.config import StorageProviderName, get_settings
    15	from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
    16	from captureos.core.errors import AppError, NotFoundError
    17	from captureos.models.documents import Document, DocumentChunk
    18	from captureos.models.enums import ActorType, DocumentSourceKind, ParseStatus, WorkflowType
    19	from captureos.models.workflow import WorkflowRun
    20	from captureos.providers import get_storage
    21	from captureos.schemas.document import (
    22	    DocumentResponse,
    23	    IngestRequest,
    24	    InitiateUploadRequest,
    25	    InitiateUploadResponse,
    26	    PasteRequest,
    27	)
    28	from captureos.schemas.workflow import WorkflowRunCreated
    29	from captureos.workflows.dispatch import schedule_workflow
    30	
    31	router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
    32	blobs_router = APIRouter(prefix="/orgs/{org_id}/blobs", tags=["documents"])
    33	
    34	_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap to prevent memory-exhaustion DoS
    35	
    36	
    37	async def _chunk_count(session: SessionDep, document_id: uuid.UUID) -> int:
    38	    return (
    39	        await session.execute(
    40	            select(func.count())
    41	            .select_from(DocumentChunk)
    42	            .where(DocumentChunk.document_id == document_id)
    43	        )
    44	    ).scalar_one()
    45	
    46	
    47	def _doc_response(doc: Document, chunk_count: int) -> DocumentResponse:
    48	    return DocumentResponse(
    49	        id=doc.id,
    50	        filename=doc.filename,
    51	        mime_type=doc.mime_type,
    52	        source_kind=doc.source_kind,
    53	        parse_status=doc.parse_status,
    54	        chunk_count=chunk_count,
    55	        page_count=doc.page_count,
    56	    )
    57	
    58	
    59	async def _get_doc_or_404(
    60	    session: SessionDep, org_id: uuid.UUID, document_id: uuid.UUID
    61	) -> Document:
    62	    doc = (
    63	        await session.execute(
    64	            select(Document).where(Document.id == document_id, Document.org_id == org_id)
    65	        )
    66	    ).scalar_one_or_none()
    67	    if doc is None:
    68	        raise NotFoundError("Document not found")
    69	    return doc
    70	
    71	
    72	@router.post(":initiate-upload", response_model=InitiateUploadResponse)
    73	async def initiate_upload(
    74	    body: InitiateUploadRequest, ctx: OrgEditor, session: SessionDep
    75	) -> InitiateUploadResponse:
    76	    doc_id = uuid.uuid4()
    77	    rel_key = f"{doc_id}/{body.filename}"
    78	    full_key = f"{ctx.org_id}/{rel_key}"
    79	    presigned = get_storage().presign_upload(full_key, content_type=body.mime_type)
    80	
    81	    doc = Document(
    82	        id=doc_id,
    83	        org_id=ctx.org_id,
    84	        filename=body.filename,
    85	        mime_type=body.mime_type,
    86	        content_hash=f"pending:{doc_id}",  # real hash assigned at ingest
    87	        source_kind=DocumentSourceKind.upload.value,
    88	        parse_status=ParseStatus.pending.value,
    89	        storage_uri=presigned.storage_uri,
    90	    )
    91	    session.add(doc)
    92	    await session.flush()
    93	
    94	    # Local storage uploads go through our org-scoped route; GCS uses the signed URL.
    95	    if get_settings().storage_provider is StorageProviderName.local:
    96	        upload_url = f"/api/v1/orgs/{ctx.org_id}/blobs/{rel_key}"
    97	    else:
    98	        upload_url = presigned.url
    99	
   100	    await record_event(
   101	        "document.upload_initiated",
   102	        org_id=ctx.org_id,
   103	        actor=ActorType.user,
   104	        actor_id=str(ctx.user.id),
   105	        payload={"document_id": str(doc_id), "filename": body.filename},
   106	    )
   107	    return InitiateUploadResponse(
   108	        document_id=doc_id,
   109	        upload_url=upload_url,
   110	        method=presigned.method,
   111	        storage_uri=presigned.storage_uri,
   112	    )
   113	
   114	
   115	@blobs_router.put("/{rel_key:path}")
   116	async def put_blob(request: Request, ctx: OrgEditor, rel_key: str) -> dict:
   117	    data = await request.body()
   118	    # Key is always re-prefixed with the caller's org id; LocalStorage rejects traversal.
   119	    key = f"{ctx.org_id}/{rel_key}"
   120	    blob = await get_storage().put(key, data, content_type=request.headers.get("content-type"))
   121	    return {"ok": True, "size": blob.size, "storageUri": blob.uri}
   122	
   123	
   124	@blobs_router.get("/{rel_key:path}")
   125	async def get_blob(ctx: OrgViewer, rel_key: str) -> Response:
   126	    storage = get_storage()
   127	    uri = f"local://{ctx.org_id}/{rel_key}"
   128	    if not await storage.exists(uri):
   129	        raise NotFoundError("Blob not found")
   130	    data = await storage.get(uri)
   131	    return Response(content=data, media_type="application/octet-stream")
   132	
   133	
   134	@router.post(
   135	    "/{document_id}:ingest", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED
   136	)
   137	async def ingest_document(
   138	    body: IngestRequest,
   139	    ctx: OrgEditor,
   140	    session: SessionDep,
   141	    background_tasks: BackgroundTasks,
   142	    document_id: uuid.UUID,
   143	) -> WorkflowRunCreated:
   144	    await _get_doc_or_404(session, ctx.org_id, document_id)
   145	    params: dict = {"document_id": str(document_id)}
   146	    if body.raw_text is not None:
   147	        params["raw_text"] = body.raw_text
   148	    run = WorkflowRun(
   149	        org_id=ctx.org_id,
   150	        type=WorkflowType.document_ingest.value,
   151	        status="queued",
   152	        input_params=params,
   153	    )
   154	    session.add(run)
   155	    await session.commit()  # durably persist before dispatching to the worker
   156	    schedule_workflow(background_tasks, run.id)
   157	    return WorkflowRunCreated(workflow_run_id=run.id)
   158	
   159	
   160	@router.post(":paste", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
   161	async def paste_document(
   162	    body: PasteRequest, ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks
   163	) -> WorkflowRunCreated:
   164	    """Ingest pasted solicitation text with no file upload (FR-DI-3)."""
   165	    doc_id = uuid.uuid4()
   166	    doc = Document(
   167	        id=doc_id,
   168	        org_id=ctx.org_id,
   169	        filename=body.filename,
   170	        mime_type="text/plain",
   171	        content_hash=f"pending:{doc_id}",
   172	        source_kind=DocumentSourceKind.paste.value,
   173	        parse_status=ParseStatus.pending.value,
   174	    )
   175	    session.add(doc)
   176	    await session.flush()
   177	    run = WorkflowRun(
   178	        org_id=ctx.org_id,
   179	        type=WorkflowType.document_ingest.value,
   180	        status="queued",
   181	        input_params={"document_id": str(doc_id), "raw_text": body.raw_text},
   182	    )
   183	    session.add(run)
   184	    await session.commit()  # commit doc + run before dispatching to the worker
   185	    schedule_workflow(background_tasks, run.id)
   186	    return WorkflowRunCreated(workflow_run_id=run.id)
   187	
   188	
   189	@router.get("", response_model=list[DocumentResponse])
   190	async def list_documents(ctx: OrgViewer, session: SessionDep) -> list[DocumentResponse]:
   191	    docs = (
   192	        (
   193	            await session.execute(
   194	                select(Document)
   195	                .where(Document.org_id == ctx.org_id)
   196	                .order_by(Document.created_at.desc())
   197	            )
   198	        )
   199	        .scalars()
   200	        .all()
   201	    )
   202	    out: list[DocumentResponse] = []
   203	    for doc in docs:
   204	        out.append(_doc_response(doc, await _chunk_count(session, doc.id)))
   205	    return out
   206	
   207	
   208	@router.get("/{document_id}", response_model=DocumentResponse)
   209	async def get_document(
   210	    ctx: OrgViewer, session: SessionDep, document_id: uuid.UUID
   211	) -> DocumentResponse:
   212	    doc = await _get_doc_or_404(session, ctx.org_id, document_id)
   213	    return _doc_response(doc, await _chunk_count(session, doc.id))

---
     1	"""Document ingestion workflow step (FR-DI-1/2/3): load the blob (or pasted text),
     2	run the ingest pipeline, and record chunk counts."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	
     8	from sqlalchemy import select
     9	
    10	from captureos.ingestion.service import ingest_content
    11	from captureos.models.documents import Document
    12	from captureos.providers import get_storage
    13	from captureos.workflows.engine import StepContext
    14	
    15	
    16	async def run_document_ingest(ctx: StepContext) -> None:
    17	    session = ctx.session
    18	    org_id = ctx.org_id
    19	    params = ctx.params
    20	
    21	    document_id = uuid.UUID(str(params["document_id"]))
    22	    document = (
    23	        await session.execute(
    24	            select(Document).where(Document.id == document_id, Document.org_id == org_id)
    25	        )
    26	    ).scalar_one_or_none()
    27	    if document is None:
    28	        raise ValueError(f"Document {document_id} not found in org")
    29	
    30	    raw_text = params.get("raw_text")
    31	    if raw_text is not None:
    32	        result = await ingest_content(session, org_id, document=document, raw_text=raw_text)
    33	    else:
    34	        if not document.storage_uri:
    35	            raise ValueError("Document has no uploaded content and no pasted text")
    36	        data = await get_storage().get(document.storage_uri)
    37	        result = await ingest_content(session, org_id, document=document, data=data)
    38	
    39	    ctx.merge_results(
    40	        documentId=str(document.id),
    41	        chunkCount=result.chunk_count,
    42	        deduped=result.deduped,
    43	        parseStatus=document.parse_status,
    44	    )

---
     1	"""Ingest content into a Document: parse → chunk → embed → persist, with content-hash
     2	dedupe (FR-DI-6) and a backing Source so chunks are citable (FR-DI-5, CON-2)."""
     3	
     4	from __future__ import annotations
     5	
     6	import hashlib
     7	import uuid
     8	from dataclasses import dataclass
     9	
    10	from sqlalchemy import select
    11	from sqlalchemy.ext.asyncio import AsyncSession
    12	
    13	from captureos.ingestion.chunking import chunk_document
    14	from captureos.logging import get_logger
    15	from captureos.models.documents import Document, DocumentChunk
    16	from captureos.models.enums import ParseStatus, SourceKind
    17	from captureos.models.evidence import Source
    18	from captureos.providers import get_docparse, get_embeddings
    19	from captureos.providers.base import ParsedDocument, ParsedPage
    20	
    21	logger = get_logger(__name__)
    22	
    23	
    24	@dataclass(slots=True)
    25	class IngestResult:
    26	    document: Document
    27	    deduped: bool
    28	    chunk_count: int
    29	    source_id: uuid.UUID | None
    30	
    31	
    32	async def ingest_content(
    33	    session: AsyncSession,
    34	    org_id: uuid.UUID,
    35	    *,
    36	    document: Document,
    37	    data: bytes | None = None,
    38	    raw_text: str | None = None,
    39	) -> IngestResult:
    40	    if raw_text is not None:
    41	        content = raw_text.encode("utf-8")
    42	        parsed = ParsedDocument(
    43	            text=raw_text, pages=[ParsedPage(page=1, text=raw_text)], page_count=1
    44	        )
    45	    elif data is not None:
    46	        content = data
    47	        parsed = await get_docparse().parse(
    48	            content, mime_type=document.mime_type, filename=document.filename
    49	        )
    50	    else:
    51	        raise ValueError("ingest_content requires either data or raw_text")
    52	
    53	    real_hash = hashlib.sha256(content).hexdigest()
    54	
    55	    # Idempotency: identical content already ingested for this org → don't duplicate chunks.
    56	    dup = (
    57	        await session.execute(
    58	            select(Document).where(
    59	                Document.org_id == org_id,
    60	                Document.content_hash == real_hash,
    61	                Document.parse_status == ParseStatus.parsed.value,
    62	                Document.id != document.id,
    63	            )
    64	        )
    65	    ).scalar_one_or_none()
    66	    if dup is not None:
    67	        document.parse_status = ParseStatus.parsed.value
    68	        document.page_count = parsed.page_count
    69	        logger.info("ingest.deduped", document_id=str(document.id), existing=str(dup.id))
    70	        return IngestResult(document=document, deduped=True, chunk_count=0, source_id=None)
    71	
    72	    document.content_hash = real_hash
    73	    document.page_count = parsed.page_count
    74	
    75	    # A Source row makes the document's chunks citable.
    76	    source = Source(
    77	        org_id=org_id,
    78	        kind=SourceKind.document.value,
    79	        document_id=document.id,
    80	        title=document.filename,
    81	        snapshot_uri=document.storage_uri,
    82	    )
    83	    session.add(source)
    84	
    85	    chunks = chunk_document(parsed)
    86	    if chunks:
    87	        embedding = await get_embeddings().embed([c.text for c in chunks])
    88	        for i, chunk in enumerate(chunks):
    89	            session.add(
    90	                DocumentChunk(
    91	                    org_id=org_id,
    92	                    document_id=document.id,
    93	                    ordinal=chunk.ordinal,
    94	                    text=chunk.text,
    95	                    locator=chunk.locator,
    96	                    embedding=embedding.vectors[i],
    97	                )
    98	            )
    99	
   100	    document.parse_status = ParseStatus.parsed.value
   101	    await session.flush()
   102	    return IngestResult(
   103	        document=document, deduped=False, chunk_count=len(chunks), source_id=source.id
   104	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/agents/base.py && printf '\\n---\\n' && nl -ba apps/api/captureos/agents/company_brain.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/services/company_brain.py && printf '\\n---\\n' && nl -ba apps/api/captureos/api/company_profile.py && printf '\\n---\\n' && nl -ba apps/api/captureos/api/workflows.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Agent base class (PRD §10.1, §10.5).
     2	
     3	Every agent declares a Pydantic output model and implements either ``mock_output`` (used
     4	when LLM_PROVIDER=mock — deterministic, offline) or ``build_prompt`` (used with Gemini,
     5	which is asked for schema-valid JSON and retried on validation failure). Either path
     6	records an ``agent_run`` row + an audit event with model/tokens/latency (CON-3, FR-AU-1),
     7	and bounded schema-retry guarantees we never silently return malformed output (FR-RE-2).
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	import time
    13	import uuid
    14	from dataclasses import dataclass
    15	from typing import Any
    16	
    17	from pydantic import BaseModel, ValidationError
    18	from sqlalchemy.ext.asyncio import AsyncSession
    19	
    20	from captureos.audit import record_event
    21	from captureos.config import LLMProviderName, get_settings
    22	from captureos.logging import get_logger
    23	from captureos.models.enums import ActorType, AgentRunStatus
    24	from captureos.models.workflow import AgentRun
    25	from captureos.providers import ModelTier, get_llm
    26	from captureos.providers.base import LLMResponse
    27	
    28	logger = get_logger(__name__)
    29	
    30	_MAX_FIELD_CHARS = 2000  # cap large strings in agent_run.input/output (NFR-3 PII restraint)
    31	
    32	
    33	class AgentError(Exception):
    34	    """Raised when an agent cannot produce schema-valid output after retries."""
    35	
    36	
    37	@dataclass(slots=True)
    38	class AgentContext:
    39	    """Carries the DB session and workflow position an agent needs to record itself."""
    40	
    41	    session: AsyncSession
    42	    org_id: uuid.UUID
    43	    run_id: uuid.UUID | None = None
    44	    step_id: uuid.UUID | None = None
    45	    filing_id: uuid.UUID | None = None
    46	
    47	
    48	def _truncate(value: Any) -> Any:
    49	    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
    50	        return value[:_MAX_FIELD_CHARS] + f"…[+{len(value) - _MAX_FIELD_CHARS} chars]"
    51	    if isinstance(value, dict):
    52	        return {k: _truncate(v) for k, v in value.items()}
    53	    if isinstance(value, list):
    54	        return [_truncate(v) for v in value]
    55	    return value
    56	
    57	
    58	def _jsonable(model: BaseModel | None) -> dict:
    59	    if model is None:
    60	        return {}
    61	    return _truncate(model.model_dump(mode="json"))
    62	
    63	
    64	class Agent[InputT: BaseModel, OutputT: BaseModel]:
    65	    name: str
    66	    tier: ModelTier = ModelTier.flash
    67	    output_model: type[OutputT]
    68	    system_prompt: str = ""
    69	
    70	    # --- subclasses implement at least one path ---
    71	    def build_prompt(self, data: InputT) -> str:
    72	        raise NotImplementedError
    73	
    74	    async def mock_output(self, ctx: AgentContext, data: InputT) -> OutputT:
    75	        raise NotImplementedError
    76	
    77	    async def run(self, ctx: AgentContext, data: InputT) -> OutputT:
    78	        settings = get_settings()
    79	        started = time.perf_counter()
    80	        llm_resp: LLMResponse | None = None
    81	        try:
    82	            if settings.llm_provider is LLMProviderName.mock:
    83	                output = await self.mock_output(ctx, data)
    84	            else:
    85	                output, llm_resp = await self._invoke_llm(ctx, data)
    86	        except Exception as exc:
    87	            await self._record(ctx, data, None, llm_resp, started, AgentRunStatus.failed, str(exc))
    88	            logger.error("agent.failed", agent=self.name, error=str(exc))
    89	            raise
    90	        await self._record(ctx, data, output, llm_resp, started, AgentRunStatus.success)
    91	        return output
    92	
    93	    async def _invoke_llm(self, ctx: AgentContext, data: InputT) -> tuple[OutputT, LLMResponse]:
    94	        settings = get_settings()
    95	        llm = get_llm()
    96	        schema = self.output_model.model_json_schema()
    97	        base_prompt = self.build_prompt(data)
    98	        prompt = base_prompt
    99	        last_error: Exception | None = None
   100	
   101	        for attempt in range(settings.llm_max_retries + 1):
   102	            resp = await llm.generate(
   103	                prompt, tier=self.tier, system=self.system_prompt, json_schema=schema
   104	            )
   105	            try:
   106	                return self.output_model.model_validate_json(resp.text), resp
   107	            except ValidationError as err:
   108	                last_error = err
   109	                logger.warning("agent.schema_retry", agent=self.name, attempt=attempt)
   110	                # Re-prompt with the validation error appended (§10.5).
   111	                prompt = (
   112	                    f"{base_prompt}\n\nYour previous response did not match the required schema:\n"
   113	                    f"{err}\n\nReturn ONLY valid JSON matching the schema. No prose."
   114	                )
   115	        raise AgentError(
   116	            f"{self.name}: output failed schema validation after "
   117	            f"{settings.llm_max_retries + 1} attempts: {last_error}"
   118	        )
   119	
   120	    async def _record(
   121	        self,
   122	        ctx: AgentContext,
   123	        data: InputT,
   124	        output: OutputT | None,
   125	        llm_resp: LLMResponse | None,
   126	        started: float,
   127	        status: AgentRunStatus,
   128	        error: str | None = None,
   129	    ) -> None:
   130	        latency_ms = int((time.perf_counter() - started) * 1000)
   131	        model = llm_resp.model if llm_resp else "mock"
   132	        in_tok = llm_resp.input_tokens if llm_resp else 0
   133	        out_tok = llm_resp.output_tokens if llm_resp else 0
   134	
   135	        if ctx.step_id is not None:
   136	            ctx.session.add(
   137	                AgentRun(
   138	                    org_id=ctx.org_id,
   139	                    step_id=ctx.step_id,
   140	                    agent_name=self.name,
   141	                    model=model,
   142	                    input=_jsonable(data),
   143	                    output=_jsonable(output),
   144	                    input_tokens=in_tok,
   145	                    output_tokens=out_tok,
   146	                    latency_ms=latency_ms,
   147	                    status=status.value,
   148	                    error=error,
   149	                )
   150	            )
   151	            await ctx.session.flush()
   152	
   153	        await record_event(
   154	            f"agent.{self.name}",
   155	            org_id=ctx.org_id,
   156	            actor=ActorType.agent,
   157	            actor_id=self.name,
   158	            run_id=ctx.run_id,
   159	            step_id=ctx.step_id,
   160	            filing_id=ctx.filing_id,
   161	            model=model,
   162	            input_tokens=in_tok,
   163	            output_tokens=out_tok,
   164	            latency_ms=latency_ms,
   165	            status=status.value,
   166	            payload={"error": error} if error else {},
   167	        )

---
     1	"""Company Brain agent (PRD agent #2, FR-CB-2/3).
     2	
     3	Builds a structured company profile from minimal input. Mock mode derives a deterministic,
     4	demo-quality profile via lightweight keyword heuristics; Gemini mode grounds it in the
     5	fetched website/document text. Emits grounded ``evidence`` claims (each tagged with its
     6	source kind) so the service can materialize sourced evidence_items (CON-2).
     7	"""
     8	
     9	from __future__ import annotations
    10	
    11	import hashlib
    12	
    13	from pydantic import BaseModel, Field
    14	
    15	from captureos.agents.base import Agent, AgentContext
    16	from captureos.providers import ModelTier
    17	
    18	
    19	# ---- I/O contract ----
    20	class CompanyBrainInput(BaseModel):
    21	    name: str
    22	    website_url: str | None = None
    23	    industry: str | None = None
    24	    location: str | None = None
    25	    description: str | None = None
    26	    # Text excerpts from ingested website/docs that ground the profile.
    27	    document_excerpts: list[str] = Field(default_factory=list)
    28	    has_website: bool = False
    29	    has_documents: bool = False
    30	
    31	
    32	class ServiceItem(BaseModel):
    33	    name: str
    34	    description: str
    35	
    36	
    37	class NaicsGuess(BaseModel):
    38	    code: str
    39	    label: str
    40	    confidence: float
    41	
    42	
    43	class CertItem(BaseModel):
    44	    name: str
    45	    status: str  # detected / missing / unknown
    46	
    47	
    48	class EvidenceClaim(BaseModel):
    49	    type: str  # service / past_performance / certification / fact / metric
    50	    content: str
    51	    source_kind: str  # web / user_input / document
    52	    confidence: float = 0.7
    53	
    54	
    55	class CompanyBrainOutput(BaseModel):
    56	    services: list[ServiceItem]
    57	    naics_guesses: list[NaicsGuess]
    58	    funding_categories: list[str]
    59	    target_customers: list[str]
    60	    certifications: list[CertItem]
    61	    capability_statement: str
    62	    missing_fields: list[str]
    63	    evidence: list[EvidenceClaim]
    64	
    65	
    66	# Lightweight industry → NAICS map for deterministic offline guesses.
    67	_NAICS_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    68	    (
    69	        ("software", "saas", "app", "platform", "developer"),
    70	        "541511",
    71	        "Custom Computer Programming Services",
    72	    ),
    73	    (
    74	        ("it ", "information technology", "cyber", "cloud", "data"),
    75	        "541512",
    76	        "Computer Systems Design Services",
    77	    ),
    78	    (
    79	        ("construction", "contractor", "building", "renovation"),
    80	        "236220",
    81	        "Commercial & Institutional Building Construction",
    82	    ),
    83	    (
    84	        ("consult", "advisory", "strategy"),
    85	        "541611",
    86	        "Administrative Management & General Management Consulting",
    87	    ),
    88	    (
    89	        ("research", "lab", "biotech", "science"),
    90	        "541715",
    91	        "Research & Development in Physical, Engineering & Life Sciences",
    92	    ),
    93	    (("market", "advertis", "media", "design"), "541810", "Advertising Agencies"),
    94	    (("logistics", "transport", "supply", "warehouse"), "493110", "General Warehousing & Storage"),
    95	    (("health", "clinic", "medical", "care"), "621111", "Offices of Physicians"),
    96	    (("staffing", "recruit", "talent", "hr"), "561311", "Employment Placement Agencies"),
    97	    (("clean", "janitor", "facilit"), "561720", "Janitorial Services"),
    98	]
    99	
   100	_CERT_KEYWORDS: dict[str, str] = {
   101	    "8(a)": "8(a)",
   102	    "wosb": "Woman-Owned Small Business (WOSB)",
   103	    "woman-owned": "Woman-Owned Small Business (WOSB)",
   104	    "hubzone": "HUBZone",
   105	    "sdvosb": "Service-Disabled Veteran-Owned Small Business (SDVOSB)",
   106	    "veteran": "Veteran-Owned Small Business (VOSB)",
   107	    "iso 9001": "ISO 9001",
   108	    "iso 27001": "ISO 27001",
   109	    "soc 2": "SOC 2",
   110	    "minority-owned": "Minority Business Enterprise (MBE)",
   111	}
   112	
   113	_COMMON_FUNDING = ["SBIR/STTR", "Economic development grants", "State small-business grants"]
   114	
   115	
   116	class CompanyBrainAgent(Agent[CompanyBrainInput, CompanyBrainOutput]):
   117	    name = "company_brain"
   118	    tier = ModelTier.pro
   119	    output_model = CompanyBrainOutput
   120	    system_prompt = (
   121	        "You are a government-contracting and grants analyst. Build a precise, conservative "
   122	        "company profile from the provided inputs. Only state facts grounded in the supplied "
   123	        "website/document text; mark anything uncertain as missing. Return strict JSON."
   124	    )
   125	
   126	    def build_prompt(self, data: CompanyBrainInput) -> str:
   127	        excerpts = "\n\n".join(data.document_excerpts[:20]) or "(no website/document text provided)"
   128	        return (
   129	            f"Company name: {data.name}\n"
   130	            f"Website: {data.website_url or '(none)'}\n"
   131	            f"Industry: {data.industry or '(unknown)'}\n"
   132	            f"Location: {data.location or '(unknown)'}\n"
   133	            f"Self-description: {data.description or '(none)'}\n\n"
   134	            f"Source text (website/docs):\n{excerpts}\n\n"
   135	            "Produce: services, naics_guesses (with confidence 0-1), funding_categories, "
   136	            "target_customers, certifications (status detected/missing/unknown), a 120-180 word "
   137	            "capability_statement, missing_fields (what you couldn't determine), and an evidence "
   138	            "list where each claim cites source_kind (web|user_input|document)."
   139	        )
   140	
   141	    async def mock_output(self, ctx: AgentContext, data: CompanyBrainInput) -> CompanyBrainOutput:
   142	        haystack = " ".join(
   143	            filter(None, [data.name, data.industry, data.description, *data.document_excerpts])
   144	        ).lower()
   145	        source_kind = (
   146	            "web" if data.has_website else ("document" if data.has_documents else "user_input")
   147	        )
   148	
   149	        # NAICS by keyword, deterministic.
   150	        naics: list[NaicsGuess] = []
   151	        for keywords, code, label in _NAICS_KEYWORDS:
   152	            if any(k.strip() in haystack for k in keywords):
   153	                naics.append(NaicsGuess(code=code, label=label, confidence=0.78))
   154	        if not naics:
   155	            naics.append(
   156	                NaicsGuess(
   157	                    code="541990",
   158	                    label="All Other Professional, Scientific & Technical Services",
   159	                    confidence=0.4,
   160	                )
   161	            )
   162	        naics = naics[:3]
   163	
   164	        # Services: from description sentences, else generic by NAICS.
   165	        services: list[ServiceItem] = []
   166	        if data.description:
   167	            for frag in [
   168	                s.strip()
   169	                for s in data.description.replace(";", ".").split(".")
   170	                if len(s.strip()) > 8
   171	            ][:3]:
   172	                services.append(ServiceItem(name=frag[:60], description=frag))
   173	        if not services:
   174	            services.append(
   175	                ServiceItem(name=naics[0].label, description=f"{naics[0].label} for {data.name}.")
   176	            )
   177	
   178	        # Certifications detected from text.
   179	        certs: list[CertItem] = []
   180	        for needle, label in _CERT_KEYWORDS.items():
   181	            if needle in haystack:
   182	                certs.append(CertItem(name=label, status="detected"))
   183	        for likely in ("Small Business (SAM.gov) registration", "8(a)"):
   184	            if not any(c.name.startswith(likely[:8]) for c in certs):
   185	                certs.append(CertItem(name=likely, status="unknown"))
   186	
   187	        # Evidence: grounded claims with a source.
   188	        evidence: list[EvidenceClaim] = []
   189	        for svc in services:
   190	            evidence.append(
   191	                EvidenceClaim(
   192	                    type="service",
   193	                    content=f"Provides: {svc.description}",
   194	                    source_kind=source_kind,
   195	                    confidence=0.7,
   196	                )
   197	            )
   198	        for cert in certs:
   199	            if cert.status == "detected":
   200	                evidence.append(
   201	                    EvidenceClaim(
   202	                        type="certification",
   203	                        content=f"Holds {cert.name}",
   204	                        source_kind=source_kind,
   205	                        confidence=0.8,
   206	                    )
   207	                )
   208	        if data.location:
   209	            evidence.append(
   210	                EvidenceClaim(
   211	                    type="fact",
   212	                    content=f"Based in {data.location}",
   213	                    source_kind="user_input",
   214	                    confidence=0.9,
   215	                )
   216	            )
   217	
   218	        # Missing-information checklist (FR-CB-3).
   219	        missing: list[str] = []
   220	        if not data.website_url and not data.has_documents:
   221	            missing.append("Website or documents to ground the profile")
   222	        if not data.location:
   223	            missing.append("Primary business location")
   224	        missing.extend(
   225	            [
   226	                "UEI / SAM.gov registration status",
   227	                "Past-performance references (prior contracts/grants)",
   228	                "NAICS codes confirmation",
   229	                "Certifications proof (8(a)/WOSB/HUBZone/etc.)",
   230	            ]
   231	        )
   232	
   233	        digest = hashlib.sha256(data.name.encode()).hexdigest()[:6]
   234	        capability = (
   235	            f"{data.name} is a {data.industry or naics[0].label.lower()} company"
   236	            f"{(' based in ' + data.location) if data.location else ''}. "
   237	            f"It delivers {', '.join(s.name for s in services[:3])}. "
   238	            f"Primary NAICS alignment: {naics[0].code} ({naics[0].label}). "
   239	            "The company is preparing to pursue government contracts and grants and is building "
   240	            "its capability statement, past-performance record, and certification posture. "
   241	            f"[profile:{digest}]"
   242	        )
   243	
   244	        return CompanyBrainOutput(
   245	            services=services,
   246	            naics_guesses=naics,
   247	            funding_categories=_COMMON_FUNDING,
   248	            target_customers=["Federal agencies", "State & local government", "Prime contractors"],
   249	            certifications=certs,
   250	            capability_statement=capability,
   251	            missing_fields=missing,
   252	            evidence=evidence,
   253	        )

 succeeded in 0ms:
     1	"""Company Brain orchestration (FR-CB-*): gather sources → run agent → persist profile +
     2	sourced evidence, preserving user overrides."""
     3	
     4	from __future__ import annotations
     5	
     6	import uuid
     7	
     8	from sqlalchemy import select
     9	from sqlalchemy.ext.asyncio import AsyncSession
    10	
    11	from captureos.agents.company_brain import CompanyBrainAgent, CompanyBrainInput, CompanyBrainOutput
    12	from captureos.ingestion.website import fetch_website_text
    13	from captureos.models.company import CompanyProfile
    14	from captureos.models.documents import Document, DocumentChunk
    15	from captureos.models.enums import EvidenceOrigin, SourceKind
    16	from captureos.models.evidence import EvidenceItem, Source
    17	from captureos.workflows.engine import StepContext
    18	
    19	_MAX_DOC_EXCERPTS = 15
    20	
    21	# Profile fields the agent populates (also the keys honored by user overrides, FR-CB-5).
    22	_AGENT_FIELDS = (
    23	    "services",
    24	    "naics_guesses",
    25	    "funding_categories",
    26	    "target_customers",
    27	    "certifications",
    28	    "capability_statement",
    29	)
    30	
    31	
    32	async def gather_company_sources(ctx: StepContext) -> dict:
    33	    """Create the citable sources and collect grounding text excerpts."""
    34	    session = ctx.session
    35	    org_id = ctx.org_id
    36	    params = ctx.params
    37	
    38	    source_ids: dict[str, uuid.UUID] = {}
    39	
    40	    # Always have a user_input source so every derived fact can cite something (CON-2).
    41	    user_source = Source(
    42	        org_id=org_id, kind=SourceKind.user_input.value, title="Owner-provided profile inputs"
    43	    )
    44	    session.add(user_source)
    45	    await session.flush()
    46	    source_ids["user_input"] = user_source.id
    47	
    48	    excerpts: list[str] = []
    49	
    50	    website_url = params.get("website_url")
    51	    if website_url:
    52	        text = await fetch_website_text(website_url)
    53	        web_source = Source(
    54	            org_id=org_id, kind=SourceKind.web.value, url=website_url, title=website_url
    55	        )
    56	        session.add(web_source)
    57	        await session.flush()
    58	        source_ids["web"] = web_source.id
    59	        if text:
    60	            excerpts.append(text)
    61	
    62	    # Pull text from the org's already-ingested documents (most recent chunks).
    63	    chunk_rows = (
    64	        (
    65	            await session.execute(
    66	                select(DocumentChunk.text)
    67	                .join(Document, Document.id == DocumentChunk.document_id)
    68	                .where(DocumentChunk.org_id == org_id)
    69	                .order_by(DocumentChunk.created_at.desc())
    70	                .limit(_MAX_DOC_EXCERPTS)
    71	            )
    72	        )
    73	        .scalars()
    74	        .all()
    75	    )
    76	    if chunk_rows:
    77	        excerpts.extend(chunk_rows)
    78	        doc_source = (
    79	            (
    80	                await session.execute(
    81	                    select(Source)
    82	                    .where(Source.org_id == org_id, Source.kind == SourceKind.document.value)
    83	                    .order_by(Source.created_at.desc())
    84	                )
    85	            )
    86	            .scalars()
    87	            .first()
    88	        )
    89	        if doc_source is not None:
    90	            source_ids["document"] = doc_source.id
    91	
    92	    ctx.merge_results(sourcesCreated=len(source_ids), excerptsCollected=len(excerpts))
    93	    return {
    94	        "source_ids": source_ids,
    95	        "excerpts": excerpts,
    96	        "has_website": bool(website_url),
    97	        "has_documents": bool(chunk_rows),
    98	    }
    99	
   100	
   101	def _apply_profile(profile: CompanyProfile, output: CompanyBrainOutput, params: dict) -> None:
   102	    overrides = profile.user_overrides or {}
   103	
   104	    def set_field(field: str, value) -> None:
   105	        if field not in overrides:
   106	            setattr(profile, field, value)
   107	
   108	    set_field("website_url", params.get("website_url") or profile.website_url)
   109	    set_field("industry", params.get("industry") or profile.industry)
   110	    set_field("location", params.get("location") or profile.location)
   111	    set_field("description", params.get("description") or profile.description)
   112	    set_field("services", [s.model_dump() for s in output.services])
   113	    set_field("naics_guesses", [n.model_dump() for n in output.naics_guesses])
   114	    set_field("funding_categories", output.funding_categories)
   115	    set_field("target_customers", output.target_customers)
   116	    set_field("certifications", [c.model_dump() for c in output.certifications])
   117	    set_field("capability_statement", output.capability_statement)
   118	    # The missing-info checklist always reflects the latest run.
   119	    profile.missing_fields = output.missing_fields
   120	
   121	
   122	async def run_company_brain(ctx: StepContext, gathered: dict) -> None:
   123	    session: AsyncSession = ctx.session
   124	    org_id = ctx.org_id
   125	    params = ctx.params
   126	    source_ids: dict[str, uuid.UUID] = gathered["source_ids"]
   127	
   128	    agent_input = CompanyBrainInput(
   129	        name=params.get("name", "Unknown Company"),
   130	        website_url=params.get("website_url"),
   131	        industry=params.get("industry"),
   132	        location=params.get("location"),
   133	        description=params.get("description"),
   134	        document_excerpts=gathered["excerpts"],
   135	        has_website=gathered["has_website"],
   136	        has_documents=gathered["has_documents"],
   137	    )
   138	    output = await CompanyBrainAgent().run(ctx.agent_context(), agent_input)
   139	
   140	    # Upsert the profile, preserving user overrides (FR-CB-5/6).
   141	    profile = (
   142	        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == org_id))
   143	    ).scalar_one_or_none()
   144	    if profile is None:
   145	        profile = CompanyProfile(org_id=org_id)
   146	        session.add(profile)
   147	    _apply_profile(profile, output, params)
   148	    await session.flush()
   149	
   150	    # Replace inferred evidence from prior runs (keep user_provided), then materialize new.
   151	    existing = (
   152	        (
   153	            await session.execute(
   154	                select(EvidenceItem).where(
   155	                    EvidenceItem.org_id == org_id,
   156	                    EvidenceItem.origin == EvidenceOrigin.inferred.value,
   157	                )
   158	            )
   159	        )
   160	        .scalars()
   161	        .all()
   162	    )
   163	    for item in existing:
   164	        await session.delete(item)
   165	
   166	    fallback = source_ids["user_input"]
   167	    for claim in output.evidence:
   168	        session.add(
   169	            EvidenceItem(
   170	                org_id=org_id,
   171	                type=claim.type,
   172	                content=claim.content,
   173	                source_id=source_ids.get(claim.source_kind, fallback),  # CON-2: always sourced
   174	                origin=EvidenceOrigin.inferred.value,
   175	                confidence=claim.confidence,
   176	            )
   177	        )
   178	    await session.flush()
   179	    ctx.merge_results(
   180	        profileBuilt=True,
   181	        servicesCount=len(output.services),
   182	        evidenceCount=len(output.evidence),
   183	        missingFieldsCount=len(output.missing_fields),
   184	    )

---
     1	"""Company Brain routes (PRD §9.1). Build is async (202 + workflowRunId); overrides are
     2	persisted as user_provided evidence and win over inferred values (FR-CB-5)."""
     3	
     4	from __future__ import annotations
     5	
     6	from fastapi import APIRouter, BackgroundTasks, status
     7	from sqlalchemy import func, select
     8	
     9	from captureos.audit import record_event
    10	from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
    11	from captureos.core.errors import NotFoundError
    12	from captureos.models.company import CompanyProfile
    13	from captureos.models.enums import (
    14	    ActorType,
    15	    EvidenceOrigin,
    16	    EvidenceType,
    17	    SourceKind,
    18	    WorkflowType,
    19	)
    20	from captureos.models.evidence import EvidenceItem, Source
    21	from captureos.models.workflow import WorkflowRun
    22	from captureos.schemas.company import BuildProfileRequest, CompanyProfileResponse, ProfilePatch
    23	from captureos.schemas.workflow import WorkflowRunCreated
    24	from captureos.workflows.dispatch import schedule_workflow
    25	
    26	router = APIRouter(prefix="/orgs/{org_id}/company-profile", tags=["company-brain"])
    27	
    28	
    29	def _to_response(profile: CompanyProfile, evidence_count: int) -> CompanyProfileResponse:
    30	    return CompanyProfileResponse(
    31	        org_id=profile.org_id,
    32	        website_url=profile.website_url,
    33	        industry=profile.industry,
    34	        location=profile.location,
    35	        description=profile.description,
    36	        services=profile.services,
    37	        naics_guesses=profile.naics_guesses,
    38	        funding_categories=profile.funding_categories,
    39	        target_customers=profile.target_customers,
    40	        certifications=profile.certifications,
    41	        capability_statement=profile.capability_statement,
    42	        missing_fields=profile.missing_fields,
    43	        evidence_count=evidence_count,
    44	    )
    45	
    46	
    47	async def _evidence_count(session: SessionDep, org_id) -> int:
    48	    return (
    49	        await session.execute(
    50	            select(func.count()).select_from(EvidenceItem).where(EvidenceItem.org_id == org_id)
    51	        )
    52	    ).scalar_one()
    53	
    54	
    55	@router.post(":build", response_model=WorkflowRunCreated, status_code=status.HTTP_202_ACCEPTED)
    56	async def build_profile(
    57	    body: BuildProfileRequest,
    58	    ctx: OrgEditor,
    59	    session: SessionDep,
    60	    background_tasks: BackgroundTasks,
    61	) -> WorkflowRunCreated:
    62	    run = WorkflowRun(
    63	        org_id=ctx.org_id,
    64	        type=WorkflowType.company_brain.value,
    65	        status="queued",
    66	        input_params=body.model_dump(mode="json"),
    67	    )
    68	    session.add(run)
    69	    # Commit-then-dispatch: the worker reads the run in its own session, so it must be
    70	    # durably committed before we hand it off (FastAPI keeps the request session open
    71	    # through background tasks). This is also exactly what M2's real queue requires.
    72	    await session.commit()
    73	    schedule_workflow(background_tasks, run.id)
    74	    await record_event(
    75	        "company_brain.build_requested",
    76	        org_id=ctx.org_id,
    77	        run_id=run.id,
    78	        actor=ActorType.user,
    79	        actor_id=str(ctx.user.id),
    80	    )
    81	    return WorkflowRunCreated(workflow_run_id=run.id)
    82	
    83	
    84	@router.get("", response_model=CompanyProfileResponse)
    85	async def get_profile(ctx: OrgViewer, session: SessionDep) -> CompanyProfileResponse:
    86	    profile = (
    87	        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
    88	    ).scalar_one_or_none()
    89	    if profile is None:
    90	        raise NotFoundError("Company profile has not been built yet")
    91	    return _to_response(profile, await _evidence_count(session, ctx.org_id))
    92	
    93	
    94	@router.patch("", response_model=CompanyProfileResponse)
    95	async def patch_profile(
    96	    body: ProfilePatch, ctx: OrgEditor, session: SessionDep
    97	) -> CompanyProfileResponse:
    98	    profile = (
    99	        await session.execute(select(CompanyProfile).where(CompanyProfile.org_id == ctx.org_id))
   100	    ).scalar_one_or_none()
   101	    if profile is None:
   102	        raise NotFoundError("Company profile has not been built yet")
   103	
   104	    data = body.model_dump(exclude_unset=True)
   105	    if data:
   106	        user_source = (
   107	            (
   108	                await session.execute(
   109	                    select(Source)
   110	                    .where(Source.org_id == ctx.org_id, Source.kind == SourceKind.user_input.value)
   111	                    .order_by(Source.created_at)
   112	                )
   113	            )
   114	            .scalars()
   115	            .first()
   116	        )
   117	        if user_source is None:
   118	            user_source = Source(
   119	                org_id=ctx.org_id,
   120	                kind=SourceKind.user_input.value,
   121	                title="Owner-provided profile inputs",
   122	            )
   123	            session.add(user_source)
   124	            await session.flush()
   125	
   126	        overrides = dict(profile.user_overrides or {})
   127	        for field, value in data.items():
   128	            setattr(profile, field, value)
   129	            overrides[field] = True
   130	            session.add(
   131	                EvidenceItem(
   132	                    org_id=ctx.org_id,
   133	                    type=EvidenceType.fact.value,
   134	                    content=f"{field} (user override): {value}"[:1000],
   135	                    source_id=user_source.id,
   136	                    origin=EvidenceOrigin.user_provided.value,
   137	                    confidence=1.0,
   138	                )
   139	            )
   140	        profile.user_overrides = overrides
   141	        await session.flush()
   142	        await record_event(
   143	            "company_profile.overridden",
   144	            org_id=ctx.org_id,
   145	            actor=ActorType.user,
   146	            actor_id=str(ctx.user.id),
   147	            payload={"fields": list(data.keys())},
   148	        )
   149	
   150	    return _to_response(profile, await _evidence_count(session, ctx.org_id))

---
     1	"""Workflow-run polling (PRD §9.4)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from fastapi import APIRouter
     8	from sqlalchemy import select
     9	
    10	from captureos.core.deps import OrgViewer, SessionDep
    11	from captureos.core.errors import NotFoundError
    12	from captureos.models.workflow import WorkflowRun, WorkflowStep
    13	from captureos.schemas.workflow import WorkflowRunResponse, WorkflowStepResponse
    14	
    15	router = APIRouter(prefix="/orgs/{org_id}/workflow-runs", tags=["workflows"])
    16	
    17	
    18	@router.get("/{run_id}", response_model=WorkflowRunResponse)
    19	async def get_workflow_run(
    20	    ctx: OrgViewer, session: SessionDep, run_id: uuid.UUID
    21	) -> WorkflowRunResponse:
    22	    run = await session.get(WorkflowRun, run_id)
    23	    if run is None or run.org_id != ctx.org_id:  # CON-5
    24	        raise NotFoundError("Workflow run not found")
    25	    steps = (
    26	        (
    27	            await session.execute(
    28	                select(WorkflowStep)
    29	                .where(WorkflowStep.run_id == run.id)
    30	                .order_by(WorkflowStep.ordinal)
    31	            )
    32	        )
    33	        .scalars()
    34	        .all()
    35	    )
    36	    return WorkflowRunResponse(
    37	        id=run.id,
    38	        type=run.type,
    39	        status=run.status,
    40	        steps=[WorkflowStepResponse(name=s.name, status=s.status) for s in steps],
    41	        partial_results=run.partial_results or {},
    42	        time_saved_minutes=run.time_saved_minutes,
    43	        error=run.error,
    44	    )

exec
/bin/zsh -lc "nl -ba apps/api/captureos/schemas/company.py && printf '\\n---\\n' && nl -ba apps/api/captureos/schemas/document.py && printf '\\n---\\n' && nl -ba apps/api/captureos/schemas/workflow.py && printf '\\n---\\n' && nl -ba apps/api/captureos/ingestion/chunking.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Company Brain schemas (PRD §9.1)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from pydantic import Field
     8	
     9	from captureos.schemas.common import CamelModel
    10	
    11	
    12	class BuildProfileRequest(CamelModel):
    13	    name: str = Field(min_length=1, max_length=255)
    14	    website_url: str | None = None
    15	    industry: str | None = None
    16	    location: str | None = None
    17	    uei: str | None = None
    18	    description: str | None = None
    19	    document_ids: list[uuid.UUID] | None = None
    20	
    21	
    22	class CompanyProfileResponse(CamelModel):
    23	    org_id: uuid.UUID
    24	    website_url: str | None = None
    25	    industry: str | None = None
    26	    location: str | None = None
    27	    description: str | None = None
    28	    services: list = Field(default_factory=list)
    29	    naics_guesses: list = Field(default_factory=list)
    30	    funding_categories: list = Field(default_factory=list)
    31	    target_customers: list = Field(default_factory=list)
    32	    certifications: list = Field(default_factory=list)
    33	    capability_statement: str | None = None
    34	    missing_fields: list = Field(default_factory=list)
    35	    evidence_count: int = 0
    36	
    37	
    38	class ProfilePatch(CamelModel):
    39	    """Any provided field overrides the inferred value and is stored as user_provided
    40	    evidence (FR-CB-5)."""
    41	
    42	    website_url: str | None = None
    43	    industry: str | None = None
    44	    location: str | None = None
    45	    description: str | None = None
    46	    services: list | None = None
    47	    naics_guesses: list | None = None
    48	    funding_categories: list | None = None
    49	    target_customers: list | None = None
    50	    certifications: list | None = None
    51	    capability_statement: str | None = None

---
     1	"""Document ingestion schemas (PRD §9.2)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from pydantic import Field
     8	
     9	from captureos.schemas.common import CamelModel
    10	
    11	
    12	class InitiateUploadRequest(CamelModel):
    13	    filename: str = Field(min_length=1, max_length=512)
    14	    mime_type: str | None = None
    15	
    16	
    17	class InitiateUploadResponse(CamelModel):
    18	    document_id: uuid.UUID
    19	    upload_url: str
    20	    method: str = "PUT"
    21	    storage_uri: str
    22	
    23	
    24	class IngestRequest(CamelModel):
    25	    raw_text: str | None = None
    26	
    27	
    28	class PasteRequest(CamelModel):
    29	    filename: str = Field(default="pasted-text.txt", max_length=512)
    30	    raw_text: str = Field(min_length=1)
    31	
    32	
    33	class DocumentResponse(CamelModel):
    34	    id: uuid.UUID
    35	    filename: str
    36	    mime_type: str | None = None
    37	    source_kind: str
    38	    parse_status: str
    39	    chunk_count: int = 0
    40	    page_count: int | None = None

---
     1	"""Workflow-run schemas (PRD §9.4 polling contract)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	
     7	from captureos.schemas.common import CamelModel
     8	
     9	
    10	class WorkflowRunCreated(CamelModel):
    11	    workflow_run_id: uuid.UUID
    12	
    13	
    14	class WorkflowStepResponse(CamelModel):
    15	    name: str
    16	    status: str
    17	
    18	
    19	class WorkflowRunResponse(CamelModel):
    20	    id: uuid.UUID
    21	    type: str
    22	    status: str
    23	    steps: list[WorkflowStepResponse]
    24	    partial_results: dict | None = None
    25	    time_saved_minutes: int | None = None
    26	    error: str | None = None

---
     1	"""Text chunking for retrieval. Page-aware when the parser gives pages, so each chunk
     2	carries a locator that resolves citations back to a source (FR-DI-5)."""
     3	
     4	from __future__ import annotations
     5	
     6	import re
     7	from dataclasses import dataclass
     8	
     9	from captureos.providers.base import ParsedDocument
    10	
    11	_PARA_SPLIT = re.compile(r"\n\s*\n")
    12	
    13	
    14	@dataclass(slots=True)
    15	class Chunk:
    16	    ordinal: int
    17	    text: str
    18	    locator: str
    19	
    20	
    21	def _split(text: str, target_chars: int, overlap: int) -> list[str]:
    22	    text = text.strip()
    23	    if not text:
    24	        return []
    25	    out: list[str] = []
    26	    buf = ""
    27	    for para in _PARA_SPLIT.split(text):
    28	        para = para.strip()
    29	        if not para:
    30	            continue
    31	        if len(buf) + len(para) + 2 <= target_chars:
    32	            buf = f"{buf}\n\n{para}" if buf else para
    33	        else:
    34	            if buf:
    35	                out.append(buf)
    36	            if len(para) > target_chars:
    37	                step = max(1, target_chars - overlap)
    38	                for j in range(0, len(para), step):
    39	                    out.append(para[j : j + target_chars])
    40	                buf = ""
    41	            else:
    42	                buf = para
    43	    if buf:
    44	        out.append(buf)
    45	    return [c for c in out if c.strip()]
    46	
    47	
    48	def chunk_document(
    49	    parsed: ParsedDocument, *, target_chars: int = 1200, overlap: int = 150
    50	) -> list[Chunk]:
    51	    chunks: list[Chunk] = []
    52	    ordinal = 0
    53	    if parsed.pages and len(parsed.pages) > 1:
    54	        for page in parsed.pages:
    55	            for piece in _split(page.text, target_chars, overlap):
    56	                chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"page {page.page}"))
    57	                ordinal += 1
    58	    else:
    59	        for i, piece in enumerate(_split(parsed.text, target_chars, overlap)):
    60	            chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"chunk {i + 1}"))
    61	            ordinal += 1
    62	    return chunks

exec
/bin/zsh -lc "nl -ba apps/api/captureos/models/workflow.py && printf '\\n---\\n' && nl -ba apps/api/captureos/models/documents.py && printf '\\n---\\n' && nl -ba apps/api/captureos/models/evidence.py && printf '\\n---\\n' && nl -ba apps/api/captureos/models/company.py && printf '\\n---\\n' && nl -ba apps/api/captureos/models/audit.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Workflow engine tables (PRD §8, §10) — runs → steps → agent_runs.
     2	
     3	Drives every async pipeline and is the backbone of the audit trail (CON-3, FR-AU-1).
     4	``agent_runs.step_id`` is the only link between steps and agent runs (the PRD's
     5	``workflow_steps.agent_run_id`` is dropped to avoid a circular FK); retries append rows.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	
    12	from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
    13	from sqlalchemy.dialects.postgresql import JSONB
    14	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    15	from sqlalchemy.orm import Mapped, mapped_column, relationship
    16	
    17	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
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
    91	    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    92	    status: Mapped[str] = mapped_column(
    93	        String(16), nullable=False, default=AgentRunStatus.success.value
    94	    )
    95	    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    96	
    97	    step: Mapped[WorkflowStep] = relationship(back_populates="agent_runs")

---
     1	"""Documents and their embedded chunks (FR-DI-*).
     2	
     3	The ``embedding`` column dimension is fixed at schema-creation time and must match
     4	``Settings.embedding_dim`` (D7 = 768, Gemini text-embedding-004 compatible). Changing
     5	the embedding model's dimension requires a migration.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	
    12	from pgvector.sqlalchemy import Vector
    13	from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
    14	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    15	from sqlalchemy.orm import Mapped, mapped_column, relationship
    16	
    17	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    18	from captureos.models.enums import DocumentSourceKind, ParseStatus
    19	
    20	EMBEDDING_DIM = 768  # keep in sync with Settings.embedding_dim
    21	
    22	
    23	class Document(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    24	    __tablename__ = "documents"
    25	    # Idempotent ingestion: same content within an org is not re-ingested (FR-DI-6).
    26	    __table_args__ = (UniqueConstraint("org_id", "content_hash"),)
    27	
    28	    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    29	    storage_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    30	    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    31	    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    32	    source_kind: Mapped[str] = mapped_column(
    33	        String(32), nullable=False, default=DocumentSourceKind.upload.value
    34	    )
    35	    parse_status: Mapped[str] = mapped_column(
    36	        String(16), nullable=False, default=ParseStatus.pending.value
    37	    )
    38	    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    39	
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

---
     1	"""Sources and the Evidence Vault (FR-CB-4, FR-DI-5, CON-2).
     2	
     3	A ``Source`` is anything a claim can cite (a fetched URL, a document, user input).
     4	An ``EvidenceItem`` is an atomic, sourced fact reusable across filings.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import uuid
    10	from datetime import datetime
    11	
    12	from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
    13	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    14	from sqlalchemy.orm import Mapped, mapped_column
    15	
    16	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    17	from captureos.models.enums import EvidenceOrigin, EvidenceType, SourceKind
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

---
     1	"""Company Brain: the structured org profile (FR-CB-*)."""
     2	
     3	from __future__ import annotations
     4	
     5	from sqlalchemy import String, Text, UniqueConstraint, text
     6	from sqlalchemy.dialects.postgresql import JSONB
     7	from sqlalchemy.orm import Mapped, mapped_column
     8	
     9	from captureos.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
    10	
    11	_EMPTY_LIST = text("'[]'::jsonb")
    12	_EMPTY_OBJ = text("'{}'::jsonb")
    13	
    14	
    15	class CompanyProfile(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    16	    __tablename__ = "company_profiles"
    17	    # One profile per org.
    18	    __table_args__ = (UniqueConstraint("org_id"),)
    19	
    20	    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    21	    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    22	    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    23	    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    24	
    25	    # array of {name, description}
    26	    services: Mapped[list] = mapped_column(
    27	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    28	    )
    29	    # array of {code, label, confidence}
    30	    naics_guesses: Mapped[list] = mapped_column(
    31	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    32	    )
    33	    funding_categories: Mapped[list] = mapped_column(
    34	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    35	    )
    36	    target_customers: Mapped[list] = mapped_column(
    37	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    38	    )
    39	    # array of {name, status: detected/missing/unknown, source_id}
    40	    certifications: Mapped[list] = mapped_column(
    41	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    42	    )
    43	    # checklist of fields that could not be populated (FR-CB-3)
    44	    missing_fields: Mapped[list] = mapped_column(
    45	        JSONB, nullable=False, default=list, server_default=_EMPTY_LIST
    46	    )
    47	    # which fields the user has explicitly overridden (FR-CB-5 precedence)
    48	    user_overrides: Mapped[dict] = mapped_column(
    49	        JSONB, nullable=False, default=dict, server_default=_EMPTY_OBJ
    50	    )
    51	
    52	    capability_statement: Mapped[str | None] = mapped_column(Text, nullable=True)

---
     1	"""Postgres mirror of the append-only audit event stream (PRD §8.4, FR-AU-2).
     2	
     3	In production the authoritative stream is BigQuery; this table powers the in-app
     4	dashboard and CSV/JSON export, and is the default sink in local/dev (AUDIT_SINK=postgres).
     5	Rows are append-only — never updated or deleted (CON-3).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import uuid
    11	from datetime import datetime
    12	
    13	from sqlalchemy import DateTime, Index, Integer, String, func
    14	from sqlalchemy.dialects.postgresql import JSONB
    15	from sqlalchemy.dialects.postgresql import UUID as PGUUID
    16	from sqlalchemy.orm import Mapped, mapped_column
    17	
    18	from captureos.db.base import Base, UUIDPKMixin
    19	from captureos.models.enums import ActorType
    20	
    21	
    22	class AuditEvent(UUIDPKMixin, Base):
    23	    __tablename__ = "audit_events"
    24	    __table_args__ = (
    25	        Index("ix_audit_events_org_occurred", "org_id", "occurred_at"),
    26	        Index("ix_audit_events_run", "run_id"),
    27	    )
    28	
    29	    # Nullable + NO FK on purpose: the audit stream is append-only and decoupled (matches
    30	    # the BigQuery design, PRD §8.4). It is written in its own transaction and must not be
    31	    # constrained by referential integrity to rows that may still be uncommitted in the
    32	    # caller's transaction, nor cascade-deleted when an org is removed (it's a legal record).
    33	    # System/auth events (login, register) also legitimately have no org (CON-3, FR-AU-2).
    34	    org_id: Mapped[uuid.UUID | None] = mapped_column(
    35	        PGUUID(as_uuid=True), nullable=True, index=True
    36	    )
    37	    filing_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    38	    run_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    39	    step_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    40	
    41	    actor: Mapped[str] = mapped_column(String(16), nullable=False, default=ActorType.system.value)
    42	    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    43	    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    44	    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    45	    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    46	    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    47	    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    48	    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    49	    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    50	    # PII-restricted payload: store summaries/pointers, not full document text (NFR-3).
    51	    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    52	
    53	    occurred_at: Mapped[datetime] = mapped_column(
    54	        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    55	    )

exec
/bin/zsh -lc "nl -ba apps/api/tests/test_company_brain.py && printf '\\n---\\n' && nl -ba apps/api/tests/test_ingestion.py && printf '\\n---\\n' && nl -ba apps/api/captureos/api/router.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Company Brain build, evidence sourcing, and override persistence (FR-CB-*)."""
     2	
     3	from __future__ import annotations
     4	
     5	from httpx import AsyncClient
     6	
     7	from tests.conftest import auth_headers, register
     8	
     9	
    10	async def _build(client: AsyncClient, headers: dict, org_id: str, **body) -> dict:
    11	    resp = await client.post(
    12	        f"/api/v1/orgs/{org_id}/company-profile:build", json=body, headers=headers
    13	    )
    14	    assert resp.status_code == 202, resp.text
    15	    run_id = resp.json()["workflowRunId"]
    16	    # Background task already ran under ASGITransport; confirm via the run status.
    17	    run = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    18	    assert run.status_code == 200, run.text
    19	    return run.json()
    20	
    21	
    22	async def _bootstrap_org(client: AsyncClient, email: str) -> tuple[dict, str]:
    23	    tokens = await register(client, email, org_name="Acme")
    24	    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    25	    org_id = me.json()["orgs"][0]["orgId"]
    26	    return auth_headers(tokens), org_id
    27	
    28	
    29	async def test_build_company_profile_produces_sourced_profile(client: AsyncClient) -> None:
    30	    headers, org_id = await _bootstrap_org(client, "cb1@example.com")
    31	    run = await _build(
    32	        client,
    33	        headers,
    34	        org_id,
    35	        name="Acme Robotics",
    36	        industry="software and IT consulting",
    37	        location="Austin, TX",
    38	        description="We build custom software platforms and provide cloud consulting.",
    39	    )
    40	    assert run["status"] == "succeeded"
    41	    assert run["timeSavedMinutes"] == 60
    42	
    43	    profile = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    44	    assert profile.status_code == 200, profile.text
    45	    body = profile.json()
    46	    assert body["capabilityStatement"]
    47	    assert len(body["naicsGuesses"]) >= 1
    48	    assert len(body["services"]) >= 1
    49	    assert len(body["missingFields"]) >= 1
    50	    # Every derived fact is sourced evidence (CON-2 / FR-CB-4).
    51	    assert body["evidenceCount"] >= 1
    52	
    53	
    54	async def test_profile_unbuilt_returns_404(client: AsyncClient) -> None:
    55	    headers, org_id = await _bootstrap_org(client, "cb2@example.com")
    56	    resp = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    57	    assert resp.status_code == 404
    58	
    59	
    60	async def test_override_survives_rebuild(client: AsyncClient) -> None:
    61	    headers, org_id = await _bootstrap_org(client, "cb3@example.com")
    62	    await _build(client, headers, org_id, name="Acme", industry="software")
    63	
    64	    patched = await client.patch(
    65	        f"/api/v1/orgs/{org_id}/company-profile",
    66	        json={"industry": "Aerospace manufacturing"},
    67	        headers=headers,
    68	    )
    69	    assert patched.status_code == 200
    70	    assert patched.json()["industry"] == "Aerospace manufacturing"
    71	
    72	    # Rebuilding with a different industry must NOT clobber the user override (FR-CB-6).
    73	    await _build(client, headers, org_id, name="Acme", industry="software")
    74	    after = await client.get(f"/api/v1/orgs/{org_id}/company-profile", headers=headers)
    75	    assert after.json()["industry"] == "Aerospace manufacturing"
    76	
    77	
    78	async def test_cross_org_profile_isolation(client: AsyncClient) -> None:
    79	    headers_a, org_a = await _bootstrap_org(client, "cb-a@example.com")
    80	    await _build(client, headers_a, org_a, name="Acme", industry="software")
    81	    tokens_b = await register(client, "cb-b@example.com")
    82	    resp = await client.get(f"/api/v1/orgs/{org_a}/company-profile", headers=auth_headers(tokens_b))
    83	    assert resp.status_code == 404  # CON-5

---
     1	"""Document ingestion: paste, upload, idempotent dedupe, and blob isolation (FR-DI-*)."""
     2	
     3	from __future__ import annotations
     4	
     5	from httpx import AsyncClient
     6	
     7	from tests.conftest import auth_headers, register
     8	
     9	_SOLICITATION = (
    10	    "Section L. Offerors shall submit a technical proposal not exceeding 20 pages.\n\n"
    11	    "Section M. Award will be made to the offeror representing the best value.\n\n"
    12	    "The contractor must be registered in SAM.gov and hold an active UEI."
    13	)
    14	
    15	
    16	async def _bootstrap_org(client: AsyncClient, email: str) -> tuple[dict, str]:
    17	    tokens = await register(client, email, org_name="Acme")
    18	    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    19	    return auth_headers(tokens), me.json()["orgs"][0]["orgId"]
    20	
    21	
    22	async def _run_status(client: AsyncClient, headers: dict, org_id: str, run_id: str) -> dict:
    23	    resp = await client.get(f"/api/v1/orgs/{org_id}/workflow-runs/{run_id}", headers=headers)
    24	    assert resp.status_code == 200, resp.text
    25	    return resp.json()
    26	
    27	
    28	async def test_paste_ingestion_creates_chunks(client: AsyncClient) -> None:
    29	    headers, org_id = await _bootstrap_org(client, "ing1@example.com")
    30	    resp = await client.post(
    31	        f"/api/v1/orgs/{org_id}/documents:paste",
    32	        json={"filename": "rfp.txt", "rawText": _SOLICITATION},
    33	        headers=headers,
    34	    )
    35	    assert resp.status_code == 202, resp.text
    36	    run = await _run_status(client, headers, org_id, resp.json()["workflowRunId"])
    37	    assert run["status"] == "succeeded"
    38	    assert run["partialResults"]["chunkCount"] >= 1
    39	
    40	    docs = await client.get(f"/api/v1/orgs/{org_id}/documents", headers=headers)
    41	    assert docs.status_code == 200
    42	    assert docs.json()[0]["parseStatus"] == "parsed"
    43	    assert docs.json()[0]["chunkCount"] >= 1
    44	
    45	
    46	async def test_ingestion_is_idempotent(client: AsyncClient) -> None:
    47	    headers, org_id = await _bootstrap_org(client, "ing2@example.com")
    48	    body = {"filename": "rfp.txt", "rawText": _SOLICITATION}
    49	    first = await client.post(f"/api/v1/orgs/{org_id}/documents:paste", json=body, headers=headers)
    50	    await _run_status(client, headers, org_id, first.json()["workflowRunId"])
    51	
    52	    second = await client.post(f"/api/v1/orgs/{org_id}/documents:paste", json=body, headers=headers)
    53	    run2 = await _run_status(client, headers, org_id, second.json()["workflowRunId"])
    54	    assert run2["status"] == "succeeded"
    55	    assert run2["partialResults"]["deduped"] is True  # FR-DI-6
    56	
    57	
    58	async def test_upload_then_ingest(client: AsyncClient) -> None:
    59	    headers, org_id = await _bootstrap_org(client, "ing3@example.com")
    60	    init = await client.post(
    61	        f"/api/v1/orgs/{org_id}/documents:initiate-upload",
    62	        json={"filename": "capabilities.txt", "mimeType": "text/plain"},
    63	        headers=headers,
    64	    )
    65	    assert init.status_code == 200, init.text
    66	    upload_url = init.json()["uploadUrl"]
    67	    doc_id = init.json()["documentId"]
    68	
    69	    put = await client.put(upload_url, content=_SOLICITATION.encode(), headers=headers)
    70	    assert put.status_code == 200, put.text
    71	
    72	    ingest = await client.post(
    73	        f"/api/v1/orgs/{org_id}/documents/{doc_id}:ingest", json={}, headers=headers
    74	    )
    75	    assert ingest.status_code == 202, ingest.text
    76	    run = await _run_status(client, headers, org_id, ingest.json()["workflowRunId"])
    77	    assert run["status"] == "succeeded"
    78	    assert run["partialResults"]["chunkCount"] >= 1
    79	
    80	
    81	async def test_blob_upload_is_org_scoped(client: AsyncClient) -> None:
    82	    headers_a, org_a = await _bootstrap_org(client, "ing-a@example.com")
    83	    init = await client.post(
    84	        f"/api/v1/orgs/{org_a}/documents:initiate-upload",
    85	        json={"filename": "secret.txt", "mimeType": "text/plain"},
    86	        headers=headers_a,
    87	    )
    88	    upload_url = init.json()["uploadUrl"]
    89	
    90	    tokens_b = await register(client, "ing-b@example.com")
    91	    # User B is not a member of org A → cannot write to A's blob namespace (CON-5).
    92	    resp = await client.put(upload_url, content=b"malicious", headers=auth_headers(tokens_b))
    93	    assert resp.status_code == 404

---
     1	"""Aggregates all v1 routers under /api/v1."""
     2	
     3	from __future__ import annotations
     4	
     5	from fastapi import APIRouter
     6	
     7	from captureos.api import auth, company_profile, documents, health, orgs, workflows
     8	
     9	api_router = APIRouter()
    10	api_router.include_router(health.router)
    11	api_router.include_router(auth.router)
    12	api_router.include_router(orgs.router)
    13	api_router.include_router(company_profile.router)
    14	api_router.include_router(documents.router)
    15	api_router.include_router(documents.blobs_router)
    16	api_router.include_router(workflows.router)

exec
/bin/zsh -lc "rg -n \"class LocalStorage|def put\\(|def get\\(|presign_upload|exists\\(|class .*Storage|session_scope|record_event|OrgEditor|OrgViewer|WorkflowRun\\(|AgentRun\\(|AuditEvent\\(\" apps/api/captureos -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/models/workflow.py:21:class WorkflowRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
apps/api/captureos/models/workflow.py:76:class AgentRun(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
apps/api/captureos/providers/base.py:90:class StorageProvider(Protocol):
apps/api/captureos/providers/base.py:93:    async def put(
apps/api/captureos/providers/base.py:96:    async def get(self, uri: str) -> bytes: ...
apps/api/captureos/providers/base.py:98:    async def exists(self, uri: str) -> bool: ...
apps/api/captureos/providers/base.py:99:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
apps/api/captureos/providers/base.py:129:    def get(self, key: str) -> str | None: ...
apps/api/captureos/models/audit.py:22:class AuditEvent(UUIDPKMixin, Base):
apps/api/captureos/agents/base.py:20:from captureos.audit import record_event
apps/api/captureos/agents/base.py:137:                AgentRun(
apps/api/captureos/agents/base.py:153:        await record_event(
apps/api/captureos/workflows/dispatch.py:10:from captureos.db.session import session_scope
apps/api/captureos/workflows/dispatch.py:21:    async with session_scope() as session:
apps/api/captureos/workflows/engine.py:17:from captureos.audit import record_event
apps/api/captureos/workflows/engine.py:91:    await record_event(
apps/api/captureos/workflows/engine.py:109:            await record_event(
apps/api/captureos/workflows/engine.py:119:            await record_event(
apps/api/captureos/workflows/engine.py:137:    await record_event("workflow.succeeded", org_id=run.org_id, run_id=run.id, status="succeeded")
apps/api/captureos/api/workflows.py:10:from captureos.core.deps import OrgViewer, SessionDep
apps/api/captureos/api/workflows.py:20:    ctx: OrgViewer, session: SessionDep, run_id: uuid.UUID
apps/api/captureos/providers/storage.py:21:class LocalStorage(StorageProvider):
apps/api/captureos/providers/storage.py:35:    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
apps/api/captureos/providers/storage.py:41:    async def get(self, uri: str) -> bytes:
apps/api/captureos/providers/storage.py:46:        if path.exists():
apps/api/captureos/providers/storage.py:49:    async def exists(self, uri: str) -> bool:
apps/api/captureos/providers/storage.py:50:        return self._path(_key_from_uri(uri)).exists()
apps/api/captureos/providers/storage.py:52:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
apps/api/captureos/providers/storage.py:65:class GCSStorage(StorageProvider):  # pragma: no cover - requires GCP credentials
apps/api/captureos/providers/storage.py:83:    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
apps/api/captureos/providers/storage.py:92:    async def get(self, uri: str) -> bytes:
apps/api/captureos/providers/storage.py:104:    async def exists(self, uri: str) -> bool:
apps/api/captureos/providers/storage.py:110:    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
apps/api/captureos/providers/secrets.py:20:    def get(self, key: str) -> str | None:
apps/api/captureos/providers/secrets.py:42:    def get(self, key: str) -> str | None:
apps/api/captureos/api/auth.py:11:from captureos.audit import record_event
apps/api/captureos/api/auth.py:66:        await record_event(
apps/api/captureos/api/auth.py:70:    await record_event("auth.register", actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/auth.py:91:    await record_event("auth.login", actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/providers/audit.py:53:        from captureos.db.session import session_scope
apps/api/captureos/providers/audit.py:58:            async with session_scope() as session:
apps/api/captureos/providers/audit.py:59:                session.add(AuditEvent(**data))
apps/api/captureos/config.py:44:class StorageProviderName(StrEnum):
apps/api/captureos/api/orgs.py:8:from captureos.audit import record_event
apps/api/captureos/api/orgs.py:9:from captureos.core.deps import CurrentUser, OrgOwner, OrgViewer, SessionDep
apps/api/captureos/api/orgs.py:24:    await record_event("org.created", org_id=org.id, actor=ActorType.user, actor_id=str(user.id))
apps/api/captureos/api/orgs.py:57:async def get_org(ctx: OrgViewer) -> OrgResponse:
apps/api/captureos/api/orgs.py:70:async def list_members(ctx: OrgViewer, session: SessionDep) -> list[OrgMemberResponse]:
apps/api/captureos/api/orgs.py:100:    await record_event(
apps/api/captureos/api/company_profile.py:9:from captureos.audit import record_event
apps/api/captureos/api/company_profile.py:10:from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
apps/api/captureos/api/company_profile.py:58:    ctx: OrgEditor,
apps/api/captureos/api/company_profile.py:62:    run = WorkflowRun(
apps/api/captureos/api/company_profile.py:74:    await record_event(
apps/api/captureos/api/company_profile.py:85:async def get_profile(ctx: OrgViewer, session: SessionDep) -> CompanyProfileResponse:
apps/api/captureos/api/company_profile.py:96:    body: ProfilePatch, ctx: OrgEditor, session: SessionDep
apps/api/captureos/api/company_profile.py:142:        await record_event(
apps/api/captureos/audit/__init__.py:3:from captureos.audit.service import record_event
apps/api/captureos/audit/__init__.py:5:__all__ = ["record_event"]
apps/api/captureos/api/documents.py:13:from captureos.audit import record_event
apps/api/captureos/api/documents.py:15:from captureos.core.deps import OrgEditor, OrgViewer, SessionDep
apps/api/captureos/api/documents.py:74:    body: InitiateUploadRequest, ctx: OrgEditor, session: SessionDep
apps/api/captureos/api/documents.py:79:    presigned = get_storage().presign_upload(full_key, content_type=body.mime_type)
apps/api/captureos/api/documents.py:100:    await record_event(
apps/api/captureos/api/documents.py:116:async def put_blob(request: Request, ctx: OrgEditor, rel_key: str) -> dict:
apps/api/captureos/api/documents.py:136:async def get_blob(ctx: OrgViewer, rel_key: str) -> Response:
apps/api/captureos/api/documents.py:139:    if not await storage.exists(uri):
apps/api/captureos/api/documents.py:150:    ctx: OrgEditor,
apps/api/captureos/api/documents.py:159:    run = WorkflowRun(
apps/api/captureos/api/documents.py:173:    body: PasteRequest, ctx: OrgEditor, session: SessionDep, background_tasks: BackgroundTasks
apps/api/captureos/api/documents.py:188:    run = WorkflowRun(
apps/api/captureos/api/documents.py:201:async def list_documents(ctx: OrgViewer, session: SessionDep) -> list[DocumentResponse]:
apps/api/captureos/api/documents.py:221:    ctx: OrgViewer, session: SessionDep, document_id: uuid.UUID
apps/api/captureos/scripts/seed.py:9:from captureos.db.session import session_scope
apps/api/captureos/scripts/seed.py:21:    async with session_scope() as session:
apps/api/captureos/db/__init__.py:4:from captureos.db.session import get_engine, get_session, get_sessionmaker, session_scope
apps/api/captureos/db/__init__.py:14:    "session_scope",
apps/api/captureos/db/session.py:4:FastAPI dependency; ``session_scope`` is the equivalent for workers/scripts.
apps/api/captureos/db/session.py:56:async def session_scope() -> AsyncIterator[AsyncSession]:
apps/api/captureos/audit/service.py:16:async def record_event(
apps/api/captureos/core/deps.py:107:OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
apps/api/captureos/core/deps.py:108:OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/storage.py && printf '\\n---\\n' && nl -ba apps/api/captureos/providers/base.py" in /Users/anishguntreddi/Documents/hackathon
exec
/bin/zsh -lc "nl -ba apps/api/captureos/audit/service.py && printf '\\n---\\n' && nl -ba apps/api/captureos/providers/audit.py" in /Users/anishguntreddi/Documents/hackathon
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
   121	            storage_uri=f"gs://{self._bucket_name}/{key}",
   122	        )
   123	
   124	    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
   125	        from datetime import timedelta
   126	
   127	        blob = self._bucket.blob(self._key_from_uri(uri))
   128	        return blob.generate_signed_url(
   129	            version="v4", expiration=timedelta(seconds=expires_seconds), method="GET"
   130	        )

---
     1	"""Provider interfaces (Protocols) and shared result types.
     2	
     3	Call sites depend on these abstractions only. Concrete implementations (local + GCP)
     4	live in sibling modules and are selected by config in ``providers/__init__.py``.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from dataclasses import dataclass, field
    10	from enum import StrEnum
    11	from typing import Protocol, runtime_checkable
    12	
    13	
    14	class ModelTier(StrEnum):
    15	    flash = "flash"  # cheap/extractive (PRD NFR-6)
    16	    pro = "pro"  # reasoning-heavy
    17	
    18	
    19	@dataclass(slots=True)
    20	class LLMResponse:
    21	    text: str
    22	    model: str
    23	    input_tokens: int = 0
    24	    output_tokens: int = 0
    25	    finish_reason: str = "stop"
    26	
    27	
    28	@dataclass(slots=True)
    29	class EmbeddingResult:
    30	    vectors: list[list[float]]
    31	    model: str
    32	    dim: int
    33	
    34	
    35	@dataclass(slots=True)
    36	class ParsedPage:
    37	    page: int
    38	    text: str
    39	
    40	
    41	@dataclass(slots=True)
    42	class ParsedDocument:
    43	    text: str
    44	    pages: list[ParsedPage] = field(default_factory=list)
    45	    page_count: int = 0
    46	
    47	
    48	@dataclass(slots=True)
    49	class StoredBlob:
    50	    uri: str
    51	    size: int
    52	
    53	
    54	@dataclass(slots=True)
    55	class PresignedUpload:
    56	    """How the client uploads a blob. For local storage this is an API route the
    57	    backend hosts; for GCS it is a signed PUT URL."""
    58	
    59	    url: str
    60	    method: str = "PUT"
    61	    headers: dict[str, str] = field(default_factory=dict)
    62	    storage_uri: str = ""
    63	
    64	
    65	@runtime_checkable
    66	class LLMProvider(Protocol):
    67	    name: str
    68	
    69	    async def generate(
    70	        self,
    71	        prompt: str,
    72	        *,
    73	        tier: ModelTier = ModelTier.flash,
    74	        system: str | None = None,
    75	        json_schema: dict | None = None,
    76	        temperature: float = 0.2,
    77	        max_output_tokens: int = 4096,
    78	    ) -> LLMResponse: ...
    79	
    80	
    81	@runtime_checkable
    82	class EmbeddingsProvider(Protocol):
    83	    name: str
    84	    dim: int
    85	
    86	    async def embed(self, texts: list[str]) -> EmbeddingResult: ...
    87	
    88	
    89	@runtime_checkable
    90	class StorageProvider(Protocol):
    91	    name: str
    92	
    93	    async def put(
    94	        self, key: str, data: bytes, *, content_type: str | None = None
    95	    ) -> StoredBlob: ...
    96	    async def get(self, uri: str) -> bytes: ...
    97	    async def delete(self, uri: str) -> None: ...
    98	    async def exists(self, uri: str) -> bool: ...
    99	    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload: ...
   100	    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str: ...
   101	
   102	
   103	@dataclass(slots=True)
   104	class QueueMessage:
   105	    body: dict
   106	    message_id: str = ""
   107	
   108	
   109	@runtime_checkable
   110	class QueueProvider(Protocol):
   111	    name: str
   112	
   113	    async def publish(self, body: dict) -> str: ...
   114	
   115	
   116	@runtime_checkable
   117	class DocparseProvider(Protocol):
   118	    name: str
   119	
   120	    async def parse(
   121	        self, data: bytes, *, mime_type: str | None, filename: str
   122	    ) -> ParsedDocument: ...
   123	
   124	
   125	@runtime_checkable
   126	class SecretsProvider(Protocol):
   127	    name: str
   128	
   129	    def get(self, key: str) -> str | None: ...
   130	
   131	
   132	@runtime_checkable
   133	class AuditSink(Protocol):
   134	    name: str
   135	
   136	    async def emit(self, event: dict) -> None: ...

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

---
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

exec
/bin/zsh -lc "nl -ba apps/api/captureos/core/deps.py && printf '\\n---\\n' && nl -ba apps/api/captureos/db/session.py && printf '\\n---\\n' && nl -ba apps/api/captureos/config.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Request dependencies: authentication, org resolution, and role enforcement (CON-5, NFR-1)."""
     2	
     3	from __future__ import annotations
     4	
     5	import uuid
     6	from collections.abc import Awaitable, Callable
     7	from dataclasses import dataclass
     8	from typing import Annotated
     9	
    10	from fastapi import Depends, Path
    11	from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    12	from sqlalchemy import select
    13	from sqlalchemy.ext.asyncio import AsyncSession
    14	
    15	from captureos.auth import get_auth_provider
    16	from captureos.core.errors import AuthError, ForbiddenError, NotFoundError
    17	from captureos.db.session import get_session
    18	from captureos.models.enums import OrgRole
    19	from captureos.models.org import Organization, OrgMember, User
    20	
    21	bearer_scheme = HTTPBearer(auto_error=False)
    22	
    23	SessionDep = Annotated[AsyncSession, Depends(get_session)]
    24	BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
    25	
    26	_ROLE_ORDER = {OrgRole.viewer: 0, OrgRole.editor: 1, OrgRole.owner: 2}
    27	
    28	
    29	async def get_current_user(session: SessionDep, creds: BearerDep = None) -> User:
    30	    if creds is None or not creds.credentials:
    31	        raise AuthError("Missing or malformed Authorization header")
    32	    principal = await get_auth_provider().verify_token(creds.credentials)
    33	
    34	    if principal.is_local:
    35	        try:
    36	            user_id = uuid.UUID(principal.subject)
    37	        except ValueError as exc:
    38	            raise AuthError("Invalid token subject") from exc
    39	        user = await session.get(User, user_id)
    40	    else:
    41	        result = await session.execute(
    42	            select(User).where(User.external_auth_id == principal.subject)
    43	        )
    44	        user = result.scalar_one_or_none()
    45	        if user is None and principal.email:
    46	            user = User(email=principal.email, external_auth_id=principal.subject)
    47	            session.add(user)
    48	            await session.flush()
    49	
    50	    if user is None or not user.is_active:
    51	        raise AuthError("User not found or inactive")
    52	    return user
    53	
    54	
    55	CurrentUser = Annotated[User, Depends(get_current_user)]
    56	
    57	
    58	@dataclass(slots=True)
    59	class OrgContext:
    60	    user: User
    61	    organization: Organization
    62	    membership: OrgMember
    63	
    64	    @property
    65	    def role(self) -> str:
    66	        return self.membership.role
    67	
    68	    @property
    69	    def org_id(self) -> uuid.UUID:
    70	        return self.organization.id
    71	
    72	
    73	async def _load_org_context(org_id: uuid.UUID, user: User, session: AsyncSession) -> OrgContext:
    74	    org = await session.get(Organization, org_id)
    75	    # Non-existent OR not-a-member both return 404 to avoid leaking org existence (CON-5).
    76	    if org is None:
    77	        raise NotFoundError("Organization not found")
    78	    result = await session.execute(
    79	        select(OrgMember).where(OrgMember.org_id == org_id, OrgMember.user_id == user.id)
    80	    )
    81	    membership = result.scalar_one_or_none()
    82	    if membership is None:
    83	        raise NotFoundError("Organization not found")
    84	    return OrgContext(user=user, organization=org, membership=membership)
    85	
    86	
    87	def require_org(
    88	    min_role: OrgRole = OrgRole.viewer,
    89	) -> Callable[..., Awaitable[OrgContext]]:
    90	    """Dependency factory: resolves the org from the path, asserts membership and a
    91	    minimum role, and returns the OrgContext. Use on every org-scoped route."""
    92	
    93	    async def dependency(
    94	        user: CurrentUser,
    95	        session: SessionDep,
    96	        org_id: Annotated[uuid.UUID, Path()],
    97	    ) -> OrgContext:
    98	        ctx = await _load_org_context(org_id, user, session)
    99	        if _ROLE_ORDER[OrgRole(ctx.membership.role)] < _ROLE_ORDER[min_role]:
   100	            raise ForbiddenError(f"This action requires '{min_role.value}' role")
   101	        return ctx
   102	
   103	    return dependency
   104	
   105	
   106	# Common pre-bound dependencies.
   107	OrgViewer = Annotated[OrgContext, Depends(require_org(OrgRole.viewer))]
   108	OrgEditor = Annotated[OrgContext, Depends(require_org(OrgRole.editor))]
   109	OrgOwner = Annotated[OrgContext, Depends(require_org(OrgRole.owner))]

---
     1	"""Async engine + session management.
     2	
     3	A single lazily-created engine/sessionmaker per process. ``get_session`` is the
     4	FastAPI dependency; ``session_scope`` is the equivalent for workers/scripts.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from collections.abc import AsyncIterator
    10	from contextlib import asynccontextmanager
    11	from functools import lru_cache
    12	
    13	from sqlalchemy.ext.asyncio import (
    14	    AsyncEngine,
    15	    AsyncSession,
    16	    async_sessionmaker,
    17	    create_async_engine,
    18	)
    19	
    20	from captureos.config import get_settings
    21	
    22	
    23	@lru_cache
    24	def get_engine() -> AsyncEngine:
    25	    settings = get_settings()
    26	    return create_async_engine(
    27	        settings.database_url,
    28	        echo=settings.db_echo,
    29	        pool_pre_ping=True,
    30	        future=True,
    31	    )
    32	
    33	
    34	@lru_cache
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

---
     1	"""Central typed configuration.
     2	
     3	Everything cloud-related is selected here via env vars, so call sites depend only
     4	on abstract provider interfaces (see ``captureos.providers``). This is the seam that
     5	makes the system "local-first, cloud-ready" (PROJECT.md D1).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	from enum import StrEnum
    11	from functools import lru_cache
    12	from pathlib import Path
    13	
    14	from pydantic import field_validator, model_validator
    15	from pydantic_settings import BaseSettings, SettingsConfigDict
    16	
    17	# Load the repo-root .env regardless of CWD (the app/alembic run from apps/api).
    18	# In containers this path won't exist; real env vars are used instead.
    19	_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
    20	
    21	
    22	class AppEnv(StrEnum):
    23	    local = "local"
    24	    ci = "ci"
    25	    staging = "staging"
    26	    production = "production"
    27	
    28	
    29	class AuthProviderName(StrEnum):
    30	    local = "local"
    31	    firebase = "firebase"
    32	
    33	
    34	class LLMProviderName(StrEnum):
    35	    mock = "mock"
    36	    gemini = "gemini"
    37	
    38	
    39	class EmbeddingsProviderName(StrEnum):
    40	    mock = "mock"
    41	    gemini = "gemini"
    42	
    43	
    44	class StorageProviderName(StrEnum):
    45	    local = "local"
    46	    gcs = "gcs"
    47	
    48	
    49	class QueueProviderName(StrEnum):
    50	    local = "local"
    51	    pubsub = "pubsub"
    52	
    53	
    54	class DocparseProviderName(StrEnum):
    55	    local = "local"
    56	    docai = "docai"
    57	
    58	
    59	class AuditSinkName(StrEnum):
    60	    postgres = "postgres"
    61	    bigquery = "bigquery"
    62	
    63	
    64	class SecretsBackendName(StrEnum):
    65	    env = "env"
    66	    gcp_secret_manager = "gcp_secret_manager"  # noqa: S105 - enum value, not a secret
    67	
    68	
    69	class BillingProviderName(StrEnum):
    70	    mock = "mock"
    71	    stripe = "stripe"
    72	
    73	
    74	class Settings(BaseSettings):
    75	    model_config = SettingsConfigDict(
    76	        env_file=(str(_ROOT_ENV), ".env"),
    77	        env_file_encoding="utf-8",
    78	        extra="ignore",
    79	        case_sensitive=False,
    80	    )
    81	
    82	    # ---- Core ----
    83	    captureos_env: AppEnv = AppEnv.local
    84	    log_level: str = "INFO"
    85	    api_host: str = "0.0.0.0"  # noqa: S104 — containerized service binds all interfaces
    86	    api_port: int = 8000
    87	    cors_allow_origins: str = "http://localhost:3000"
    88	
    89	    # ---- Auth ----
    90	    auth_provider: AuthProviderName = AuthProviderName.local
    91	    jwt_secret: str = "dev-only-insecure-change-me-please-32chars-min"  # noqa: S105
    92	    jwt_algorithm: str = "HS256"
    93	    jwt_access_ttl_minutes: int = 60
    94	    jwt_refresh_ttl_days: int = 14
    95	    firebase_project_id: str | None = None
    96	    google_application_credentials: str | None = None
    97	
    98	    # ---- Database ----
    99	    database_url: str = "postgresql+asyncpg://captureos:captureos@localhost:5432/captureos"
   100	    database_url_sync: str = "postgresql+psycopg://captureos:captureos@localhost:5432/captureos"
   101	    db_echo: bool = False
   102	    run_migrations_on_start: bool = False
   103	
   104	    # ---- LLM ----
   105	    llm_provider: LLMProviderName = LLMProviderName.mock
   106	    gemini_api_key: str | None = None
   107	    gemini_model_pro: str = "gemini-2.5-pro"
   108	    gemini_model_flash: str = "gemini-2.5-flash"
   109	    llm_timeout_seconds: int = 60
   110	    llm_max_retries: int = 2
   111	
   112	    # ---- Embeddings ----
   113	    embeddings_provider: EmbeddingsProviderName = EmbeddingsProviderName.mock
   114	    embedding_model: str = "text-embedding-004"
   115	    embedding_dim: int = 768
   116	
   117	    # ---- Storage ----
   118	    storage_provider: StorageProviderName = StorageProviderName.local
   119	    storage_local_dir: str = "./.data/blobs"
   120	    gcs_bucket: str | None = None
   121	
   122	    # ---- Queue ----
   123	    queue_provider: QueueProviderName = QueueProviderName.local
   124	    pubsub_project_id: str | None = None
   125	    pubsub_topic: str = "captureos-workflow-steps"
   126	
   127	    # ---- Docparse ----
   128	    docparse_provider: DocparseProviderName = DocparseProviderName.local
   129	    docai_processor_id: str | None = None
   130	    docai_location: str = "us"
   131	
   132	    # ---- Audit ----
   133	    audit_sink: AuditSinkName = AuditSinkName.postgres
   134	    bigquery_dataset: str = "captureos_audit"
   135	    bigquery_table: str = "events"
   136	
   137	    # ---- Secrets ----
   138	    secrets_backend: SecretsBackendName = SecretsBackendName.env
   139	    gcp_project_id: str | None = None
   140	
   141	    # ---- Billing ----
   142	    billing_provider: BillingProviderName = BillingProviderName.mock
   143	    stripe_secret_key: str | None = None
   144	    stripe_webhook_secret: str | None = None
   145	    stripe_price_audit: str | None = None
   146	    stripe_price_sprint: str | None = None
   147	    stripe_price_autopilot: str | None = None
   148	
   149	    # ---- External sources ----
   150	    sam_gov_api_key: str | None = None
   151	    grants_gov_base_url: str = "https://api.grants.gov/v1/api"
   152	    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
   153	    source_fetch_cache_ttl_seconds: int = 86400
   154	    source_fetch_rate_limit_per_min: int = 30
   155	
   156	    # ---- Cost guard ----
   157	    workflow_token_budget: int = 200_000
   158	
   159	    @field_validator("cors_allow_origins")
   160	    @classmethod
   161	    def _strip_origins(cls, v: str) -> str:
   162	        return v.strip()
   163	
   164	    @property
   165	    def cors_origins_list(self) -> list[str]:
   166	        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]
   167	
   168	    @property
   169	    def is_production_like(self) -> bool:
   170	        return self.captureos_env in (AppEnv.staging, AppEnv.production)
   171	
   172	    @model_validator(mode="after")
   173	    def _guard_production_secrets(self) -> Settings:
   174	        """Fail fast if a prod-like env still uses insecure defaults (CON-4)."""
   175	        if self.is_production_like:
   176	            if "insecure" in self.jwt_secret or len(self.jwt_secret) < 32:
   177	                raise ValueError(
   178	                    "JWT_SECRET must be a strong, non-default value (>=32 chars) in production"
   179	                )
   180	            if self.auth_provider is AuthProviderName.firebase and not self.firebase_project_id:
   181	                raise ValueError("FIREBASE_PROJECT_ID required when AUTH_PROVIDER=firebase")
   182	            if self.llm_provider is LLMProviderName.gemini and not self.gemini_api_key:
   183	                raise ValueError("GEMINI_API_KEY required when LLM_PROVIDER=gemini")
   184	        return self
   185	
   186	
   187	@lru_cache
   188	def get_settings() -> Settings:
   189	    return Settings()

exec
/bin/zsh -lc "nl -ba apps/api/captureos/providers/docparse.py && printf '\\n---\\n' && nl -ba apps/api/captureos/providers/embeddings.py && printf '\\n---\\n' && nl -ba apps/api/captureos/providers/llm.py" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
     1	"""Document parsing: LocalDocparse (pdf/docx/text, default) and DocAIDocparse (prod).
     2	
     3	PDF/DOCX parsing uses the `docparse` extra (pypdf, python-docx). Plain text always works.
     4	"""
     5	
     6	from __future__ import annotations
     7	
     8	import io
     9	
    10	from captureos.config import Settings
    11	from captureos.providers.base import DocparseProvider, ParsedDocument, ParsedPage
    12	
    13	
    14	class LocalDocparse(DocparseProvider):
    15	    name = "local"
    16	
    17	    def __init__(self, settings: Settings) -> None:
    18	        self._settings = settings
    19	
    20	    async def parse(self, data: bytes, *, mime_type: str | None, filename: str) -> ParsedDocument:
    21	        lname = filename.lower()
    22	        mt = (mime_type or "").lower()
    23	
    24	        if "pdf" in mt or lname.endswith(".pdf"):
    25	            return self._parse_pdf(data)
    26	        if "word" in mt or lname.endswith((".docx", ".doc")):
    27	            return self._parse_docx(data)
    28	        # Fallback: treat as UTF-8 text (also handles pasted solicitation text, FR-DI-3).
    29	        text = data.decode("utf-8", errors="replace")
    30	        return ParsedDocument(text=text, pages=[ParsedPage(page=1, text=text)], page_count=1)
    31	
    32	    def _parse_pdf(self, data: bytes) -> ParsedDocument:
    33	        try:
    34	            from pypdf import PdfReader  # type: ignore
    35	        except ImportError as exc:  # pragma: no cover
    36	            raise RuntimeError("pypdf not installed (uv sync --extra docparse)") from exc
    37	        reader = PdfReader(io.BytesIO(data))
    38	        pages = [
    39	            ParsedPage(page=i + 1, text=(p.extract_text() or ""))
    40	            for i, p in enumerate(reader.pages)
    41	        ]
    42	        return ParsedDocument(
    43	            text="\n\n".join(p.text for p in pages), pages=pages, page_count=len(pages)
    44	        )
    45	
    46	    def _parse_docx(self, data: bytes) -> ParsedDocument:
    47	        try:
    48	            import docx  # type: ignore
    49	        except ImportError as exc:  # pragma: no cover
    50	            raise RuntimeError("python-docx not installed (uv sync --extra docparse)") from exc
    51	        document = docx.Document(io.BytesIO(data))
    52	        text = "\n".join(p.text for p in document.paragraphs)
    53	        return ParsedDocument(text=text, pages=[ParsedPage(page=1, text=text)], page_count=1)
    54	
    55	
    56	class DocAIDocparse(DocparseProvider):  # pragma: no cover - requires GCP credentials
    57	    name = "docai"
    58	
    59	    def __init__(self, settings: Settings) -> None:
    60	        if not settings.docai_processor_id:
    61	            raise RuntimeError("DOCAI_PROCESSOR_ID required when DOCPARSE_PROVIDER=docai")
    62	        self._settings = settings
    63	
    64	    async def parse(self, data: bytes, *, mime_type: str | None, filename: str) -> ParsedDocument:
    65	        import anyio
    66	        from google.cloud import documentai  # type: ignore
    67	
    68	        def _run() -> ParsedDocument:
    69	            client = documentai.DocumentProcessorServiceClient()
    70	            raw = documentai.RawDocument(content=data, mime_type=mime_type or "application/pdf")
    71	            request = documentai.ProcessRequest(
    72	                name=self._settings.docai_processor_id, raw_document=raw
    73	            )
    74	            result = client.process_document(request=request)
    75	            doc = result.document
    76	            pages = [ParsedPage(page=i + 1, text=doc.text) for i in range(len(doc.pages))]
    77	            return ParsedDocument(text=doc.text, pages=pages, page_count=len(doc.pages))
    78	
    79	        return await anyio.to_thread.run_sync(_run)

---
     1	"""Embeddings providers: deterministic Mock (default) and Gemini (prod).
     2	
     3	Mock vectors are deterministic unit vectors derived from a hash of the text, so cosine
     4	similarity is stable and meaningful for tests (identical text → identical vector,
     5	similar text → not necessarily similar; good enough for plumbing + idempotency tests).
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import hashlib
    11	import math
    12	
    13	from captureos.config import Settings
    14	from captureos.providers.base import EmbeddingResult, EmbeddingsProvider
    15	
    16	
    17	class MockEmbeddings(EmbeddingsProvider):
    18	    name = "mock"
    19	
    20	    def __init__(self, settings: Settings) -> None:
    21	        self.dim = settings.embedding_dim
    22	        self._model = settings.embedding_model
    23	
    24	    def _vector(self, text: str) -> list[float]:
    25	        # Expand a sha256 digest into `dim` deterministic floats, then L2-normalize.
    26	        raw = bytearray()
    27	        counter = 0
    28	        while len(raw) < self.dim * 2:
    29	            raw += hashlib.sha256(f"{counter}:{text}".encode()).digest()
    30	            counter += 1
    31	        vals = [
    32	            (int.from_bytes(raw[i : i + 2], "big") / 65535.0) - 0.5
    33	            for i in range(0, self.dim * 2, 2)
    34	        ][: self.dim]
    35	        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    36	        return [v / norm for v in vals]
    37	
    38	    async def embed(self, texts: list[str]) -> EmbeddingResult:
    39	        return EmbeddingResult(
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

---
     1	"""LLM providers: deterministic Mock (default, offline) and Gemini (prod)."""
     2	
     3	from __future__ import annotations
     4	
     5	import hashlib
     6	import json
     7	
     8	from captureos.config import Settings
     9	from captureos.providers.base import LLMProvider, LLMResponse, ModelTier
    10	
    11	
    12	def _est_tokens(text: str) -> int:
    13	    return max(1, len(text) // 4)
    14	
    15	
    16	class MockLLM(LLMProvider):
    17	    """Deterministic LLM for offline dev/test/CI. Same input → same output.
    18	
    19	    Agents generally call their own ``mock()`` path in mock mode to produce rich,
    20	    domain-shaped data; this provider is the generic fallback and exercises the
    21	    LLMResponse/token-accounting contract end-to-end.
    22	    """
    23	
    24	    name = "mock"
    25	
    26	    def __init__(self, settings: Settings) -> None:
    27	        self._settings = settings
    28	
    29	    async def generate(
    30	        self,
    31	        prompt: str,
    32	        *,
    33	        tier: ModelTier = ModelTier.flash,
    34	        system: str | None = None,
    35	        json_schema: dict | None = None,
    36	        temperature: float = 0.2,
    37	        max_output_tokens: int = 4096,
    38	    ) -> LLMResponse:
    39	        digest = hashlib.sha256(f"{system or ''}\n{prompt}".encode()).hexdigest()[:12]
    40	        if json_schema is not None:
    41	            text = json.dumps({"_mock": True, "digest": digest})
    42	        else:
    43	            text = f"[mock:{tier.value}] deterministic response {digest}"
    44	        model = (
    45	            self._settings.gemini_model_pro
    46	            if tier is ModelTier.pro
    47	            else self._settings.gemini_model_flash
    48	        )
    49	        return LLMResponse(
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

codex
The high-risk paths are visible now. I’m checking the invariants those modules depend on next: whether the schema/migrations actually support the new rows, whether audit logging can fail silently, and whether any route/service bypasses org scoping indirectly.
exec
/bin/zsh -lc 'git diff --unified=40 1e48a2e -- apps/api/migrations/versions/f28c812fca98_initial_schema.py apps/api/tests/conftest.py apps/api/tests/test_security.py apps/api/captureos/main.py apps/api/captureos/api/router.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
diff --git a/apps/api/captureos/api/router.py b/apps/api/captureos/api/router.py
index a6327cb..879fdb4 100644
--- a/apps/api/captureos/api/router.py
+++ b/apps/api/captureos/api/router.py
@@ -1,12 +1,16 @@
 """Aggregates all v1 routers under /api/v1."""
 
 from __future__ import annotations
 
 from fastapi import APIRouter
 
-from captureos.api import auth, health, orgs
+from captureos.api import auth, company_profile, documents, health, orgs, workflows
 
 api_router = APIRouter()
 api_router.include_router(health.router)
 api_router.include_router(auth.router)
 api_router.include_router(orgs.router)
+api_router.include_router(company_profile.router)
+api_router.include_router(documents.router)
+api_router.include_router(documents.blobs_router)
+api_router.include_router(workflows.router)
diff --git a/apps/api/captureos/main.py b/apps/api/captureos/main.py
index 48c8514..53e4821 100644
--- a/apps/api/captureos/main.py
+++ b/apps/api/captureos/main.py
@@ -21,63 +21,64 @@ logger = get_logger(__name__)
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
         # Swagger/ReDoc are disabled in production to avoid exposing the API surface.
         docs_url=None if settings.is_production_like else "/docs",
         redoc_url=None if settings.is_production_like else "/redoc",
     )
     app.add_middleware(
         CORSMiddleware,
         allow_origins=settings.cors_origins_list,
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
+
     @app.middleware("http")
     async def _security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
         response = await call_next(request)
         response.headers.setdefault("X-Content-Type-Options", "nosniff")
         response.headers.setdefault("X-Frame-Options", "DENY")
         response.headers.setdefault("Referrer-Policy", "no-referrer")
         if settings.is_production_like:
             response.headers.setdefault(
                 "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
             )
         return response
 
     register_exception_handlers(app)
     app.include_router(api_router, prefix="/api/v1")
 
     @app.get("/health", tags=["health"])
     async def root_health() -> dict:
         return {"status": "ok", "version": __version__}
 
     return app
 
 
 app = create_app()
diff --git a/apps/api/migrations/versions/f28c812fca98_initial_schema.py b/apps/api/migrations/versions/f28c812fca98_initial_schema.py
index 2b77e5f..3e8d505 100644
--- a/apps/api/migrations/versions/f28c812fca98_initial_schema.py
+++ b/apps/api/migrations/versions/f28c812fca98_initial_schema.py
@@ -26,81 +26,80 @@ def upgrade() -> None:
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
     sa.Column('org_id', sa.UUID(), nullable=True),
-    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_audit_events_org_id_organizations'), ondelete='CASCADE'),
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
diff --git a/apps/api/tests/conftest.py b/apps/api/tests/conftest.py
index fd38e73..50fd04f 100644
--- a/apps/api/tests/conftest.py
+++ b/apps/api/tests/conftest.py
@@ -38,87 +38,92 @@ os.environ.setdefault("LLM_PROVIDER", "mock")
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
-    """Create the test database + extensions + schema once (sync engine, no loop)."""
+    """Create the test database + extensions + schema once (sync engine, no loop).
+
+    Drops the whole public schema (CASCADE) rather than metadata.drop_all so a stale
+    schema from a previous run — with constraints no longer in the model — can't block
+    a clean rebuild after a schema change."""
     _ensure_database_exists()
     sync_engine = create_engine(os.environ["DATABASE_URL_SYNC"], future=True)
     with sync_engine.begin() as conn:
+        conn.execute(text("DROP SCHEMA public CASCADE"))
+        conn.execute(text("CREATE SCHEMA public"))
         conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
         conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
-    Base.metadata.drop_all(sync_engine)
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
diff --git a/apps/api/tests/test_security.py b/apps/api/tests/test_security.py
index 228843c..5317add 100644
--- a/apps/api/tests/test_security.py
+++ b/apps/api/tests/test_security.py
@@ -1,44 +1,46 @@
 """Security hardening checks for M0 (gate findings)."""
 
 from __future__ import annotations
 
 from httpx import AsyncClient
 from sqlalchemy import select
 
 from captureos.db.session import get_sessionmaker
 from captureos.models.audit import AuditEvent
 from tests.conftest import register
 
 
 async def test_security_headers_present(client: AsyncClient) -> None:
     resp = await client.get("/health")
     assert resp.headers.get("x-content-type-options") == "nosniff"
     assert resp.headers.get("x-frame-options") == "DENY"
     assert resp.headers.get("referrer-policy") == "no-referrer"
 
 
 async def test_login_unknown_email_is_same_401(client: AsyncClient) -> None:
     """A non-existent account must fail identically to a wrong password (no enumeration)."""
     resp = await client.post(
         "/api/v1/auth/login",
         json={"email": "ghost@example.com", "password": "password123"},
     )
     assert resp.status_code == 401
     assert resp.json()["error"]["message"] == "Invalid email or password"
 
 
 async def test_login_records_org_less_audit_event(client: AsyncClient) -> None:
     """CON-3: login is audited; auth events carry no org_id (nullable)."""
     await register(client, "audit@example.com")
     resp = await client.post(
         "/api/v1/auth/login",
         json={"email": "audit@example.com", "password": "password123"},
     )
     assert resp.status_code == 200
 
     async with get_sessionmaker()() as session:
         rows = (
-            await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login"))
-        ).scalars().all()
+            (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login")))
+            .scalars()
+            .all()
+        )
     assert len(rows) >= 1
     assert rows[0].org_id is None

exec
/bin/zsh -lc 'rg -n "evidence_item|source_id|document_chunk_id|company_profile|workflow_runs|workflow_steps|agent_runs|audit_events|document_chunks|documents" apps/api/migrations/versions/f28c812fca98_initial_schema.py' in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
49:    op.create_table('audit_events',
66:    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
68:    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
69:    op.create_index(op.f('ix_audit_events_occurred_at'), 'audit_events', ['occurred_at'], unique=False)
70:    op.create_index(op.f('ix_audit_events_org_id'), 'audit_events', ['org_id'], unique=False)
71:    op.create_index('ix_audit_events_org_occurred', 'audit_events', ['org_id', 'occurred_at'], unique=False)
72:    op.create_index('ix_audit_events_run', 'audit_events', ['run_id'], unique=False)
73:    op.create_table('company_profiles',
90:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_company_profiles_org_id_organizations'), ondelete='CASCADE'),
91:    sa.PrimaryKeyConstraint('id', name=op.f('pk_company_profiles')),
92:    sa.UniqueConstraint('org_id', name=op.f('uq_company_profiles_org_id'))
94:    op.create_index(op.f('ix_company_profiles_org_id'), 'company_profiles', ['org_id'], unique=False)
107:    op.create_table('documents',
119:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_documents_org_id_organizations'), ondelete='CASCADE'),
120:    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
121:    sa.UniqueConstraint('org_id', 'content_hash', name=op.f('uq_documents_org_id'))
123:    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)
124:    op.create_index(op.f('ix_documents_org_id'), 'documents', ['org_id'], unique=False)
171:    op.create_table('document_chunks',
181:    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_chunks_document_id_documents'), ondelete='CASCADE'),
182:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_document_chunks_org_id_organizations'), ondelete='CASCADE'),
183:    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks')),
184:    sa.UniqueConstraint('document_id', 'ordinal', name=op.f('uq_document_chunks_document_id'))
186:    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
187:    op.create_index('ix_document_chunks_embedding', 'document_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
188:    op.create_index(op.f('ix_document_chunks_org_id'), 'document_chunks', ['org_id'], unique=False)
200:    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_sources_document_id_documents'), ondelete='SET NULL'),
206:    op.create_table('evidence_items',
209:    sa.Column('source_id', sa.UUID(), nullable=False),
212:    sa.Column('document_chunk_id', sa.UUID(), nullable=True),
217:    sa.ForeignKeyConstraint(['document_chunk_id'], ['document_chunks.id'], name=op.f('fk_evidence_items_document_chunk_id_document_chunks'), ondelete='SET NULL'),
218:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_evidence_items_org_id_organizations'), ondelete='CASCADE'),
219:    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_evidence_items_source_id_sources'), ondelete='CASCADE'),
220:    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_items'))
222:    op.create_index(op.f('ix_evidence_items_document_chunk_id'), 'evidence_items', ['document_chunk_id'], unique=False)
223:    op.create_index(op.f('ix_evidence_items_org_id'), 'evidence_items', ['org_id'], unique=False)
224:    op.create_index(op.f('ix_evidence_items_source_id'), 'evidence_items', ['source_id'], unique=False)
231:    sa.Column('source_id', sa.UUID(), nullable=True),
242:    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_opportunities_source_id_sources'), ondelete='SET NULL'),
248:    op.create_index(op.f('ix_opportunities_source_id'), 'opportunities', ['source_id'], unique=False)
288:    sa.Column('source_id', sa.UUID(), nullable=True),
297:    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_filing_requirements_source_id_sources'), ondelete='SET NULL'),
302:    op.create_table('generated_documents',
315:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_generated_documents_filing_id_filings'), ondelete='CASCADE'),
316:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_generated_documents_org_id_organizations'), ondelete='CASCADE'),
317:    sa.PrimaryKeyConstraint('id', name=op.f('pk_generated_documents')),
318:    sa.UniqueConstraint('filing_id', 'type', 'version', name=op.f('uq_generated_documents_filing_id'))
320:    op.create_index(op.f('ix_generated_documents_filing_id'), 'generated_documents', ['filing_id'], unique=False)
321:    op.create_index(op.f('ix_generated_documents_org_id'), 'generated_documents', ['org_id'], unique=False)
339:    op.create_table('workflow_runs',
353:    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], name=op.f('fk_workflow_runs_filing_id_filings'), ondelete='CASCADE'),
354:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_runs_org_id_organizations'), ondelete='CASCADE'),
355:    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_runs'))
357:    op.create_index(op.f('ix_workflow_runs_filing_id'), 'workflow_runs', ['filing_id'], unique=False)
358:    op.create_index(op.f('ix_workflow_runs_org_id'), 'workflow_runs', ['org_id'], unique=False)
359:    op.create_index(op.f('ix_workflow_runs_status'), 'workflow_runs', ['status'], unique=False)
363:    sa.Column('evidence_item_id', sa.UUID(), nullable=True),
371:    sa.ForeignKeyConstraint(['evidence_item_id'], ['evidence_items.id'], name=op.f('fk_evidence_matches_evidence_item_id_evidence_items'), ondelete='SET NULL'),
381:    op.create_table('workflow_steps',
391:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_workflow_steps_org_id_organizations'), ondelete='CASCADE'),
392:    sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.id'], name=op.f('fk_workflow_steps_run_id_workflow_runs'), ondelete='CASCADE'),
393:    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_steps')),
394:    sa.UniqueConstraint('run_id', 'name', name=op.f('uq_workflow_steps_run_id'))
396:    op.create_index(op.f('ix_workflow_steps_org_id'), 'workflow_steps', ['org_id'], unique=False)
397:    op.create_index(op.f('ix_workflow_steps_run_id'), 'workflow_steps', ['run_id'], unique=False)
398:    op.create_table('agent_runs',
413:    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_agent_runs_org_id_organizations'), ondelete='CASCADE'),
414:    sa.ForeignKeyConstraint(['step_id'], ['workflow_steps.id'], name=op.f('fk_agent_runs_step_id_workflow_steps'), ondelete='CASCADE'),
415:    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs'))
417:    op.create_index(op.f('ix_agent_runs_org_id'), 'agent_runs', ['org_id'], unique=False)
418:    op.create_index(op.f('ix_agent_runs_step_id'), 'agent_runs', ['step_id'], unique=False)
424:    op.drop_index(op.f('ix_agent_runs_step_id'), table_name='agent_runs')
425:    op.drop_index(op.f('ix_agent_runs_org_id'), table_name='agent_runs')
426:    op.drop_table('agent_runs')
427:    op.drop_index(op.f('ix_workflow_steps_run_id'), table_name='workflow_steps')
428:    op.drop_index(op.f('ix_workflow_steps_org_id'), table_name='workflow_steps')
429:    op.drop_table('workflow_steps')
435:    op.drop_index(op.f('ix_workflow_runs_status'), table_name='workflow_runs')
436:    op.drop_index(op.f('ix_workflow_runs_org_id'), table_name='workflow_runs')
437:    op.drop_index(op.f('ix_workflow_runs_filing_id'), table_name='workflow_runs')
438:    op.drop_table('workflow_runs')
442:    op.drop_index(op.f('ix_generated_documents_org_id'), table_name='generated_documents')
443:    op.drop_index(op.f('ix_generated_documents_filing_id'), table_name='generated_documents')
444:    op.drop_table('generated_documents')
455:    op.drop_index(op.f('ix_opportunities_source_id'), table_name='opportunities')
460:    op.drop_index(op.f('ix_evidence_items_source_id'), table_name='evidence_items')
461:    op.drop_index(op.f('ix_evidence_items_org_id'), table_name='evidence_items')
462:    op.drop_index(op.f('ix_evidence_items_document_chunk_id'), table_name='evidence_items')
463:    op.drop_table('evidence_items')
467:    op.drop_index(op.f('ix_document_chunks_org_id'), table_name='document_chunks')
468:    op.drop_index('ix_document_chunks_embedding', table_name='document_chunks', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
469:    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
470:    op.drop_table('document_chunks')
479:    op.drop_index(op.f('ix_documents_org_id'), table_name='documents')
480:    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
481:    op.drop_table('documents')
484:    op.drop_index(op.f('ix_company_profiles_org_id'), table_name='company_profiles')
485:    op.drop_table('company_profiles')
486:    op.drop_index('ix_audit_events_run', table_name='audit_events')
487:    op.drop_index('ix_audit_events_org_occurred', table_name='audit_events')
488:    op.drop_index(op.f('ix_audit_events_org_id'), table_name='audit_events')
489:    op.drop_index(op.f('ix_audit_events_occurred_at'), table_name='audit_events')
490:    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
491:    op.drop_table('audit_events')

exec
/bin/zsh -lc "rg -n \"document_ids|uei|missing_fields|user_overrides|partial_results|total_input_tokens|total_output_tokens|source_kind|locator|document_chunk_id|audit.emit_failed|workflow.failed|company_brain.build_requested|document.upload_initiated\" apps/api/captureos apps/api/tests -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/services/company_brain.py:102:    overrides = profile.user_overrides or {}
apps/api/captureos/services/company_brain.py:119:    profile.missing_fields = output.missing_fields
apps/api/captureos/services/company_brain.py:173:                source_id=source_ids.get(claim.source_kind, fallback),  # CON-2: always sourced
apps/api/captureos/services/company_brain.py:183:        missingFieldsCount=len(output.missing_fields),
apps/api/captureos/agents/company_brain.py:51:    source_kind: str  # web / user_input / document
apps/api/captureos/agents/company_brain.py:62:    missing_fields: list[str]
apps/api/captureos/agents/company_brain.py:137:            "capability_statement, missing_fields (what you couldn't determine), and an evidence "
apps/api/captureos/agents/company_brain.py:138:            "list where each claim cites source_kind (web|user_input|document)."
apps/api/captureos/agents/company_brain.py:145:        source_kind = (
apps/api/captureos/agents/company_brain.py:194:                    source_kind=source_kind,
apps/api/captureos/agents/company_brain.py:204:                        source_kind=source_kind,
apps/api/captureos/agents/company_brain.py:213:                    source_kind="user_input",
apps/api/captureos/agents/company_brain.py:251:            missing_fields=missing,
apps/api/captureos/schemas/workflow.py:24:    partial_results: dict | None = None
apps/api/captureos/api/workflows.py:41:        partial_results=run.partial_results or {},
apps/api/captureos/models/org.py:19:    uei: Mapped[str | None] = mapped_column(String(32), nullable=True)
apps/api/captureos/models/evidence.py:55:    # Optional pointer to the chunk this fact was derived from (locator resolution).
apps/api/captureos/models/evidence.py:56:    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
apps/api/captureos/schemas/document.py:37:    source_kind: str
apps/api/captureos/workflows/engine.py:45:        current = dict(self.run.partial_results or {})
apps/api/captureos/workflows/engine.py:47:        self.run.partial_results = current
apps/api/captureos/workflows/engine.py:120:                "workflow.failed",
apps/api/captureos/models/workflow.py:39:    partial_results: Mapped[dict] = mapped_column(
apps/api/captureos/models/workflow.py:44:    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
apps/api/captureos/models/workflow.py:45:    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
apps/api/captureos/models/documents.py:32:    source_kind: Mapped[str] = mapped_column(
apps/api/captureos/models/documents.py:68:    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
apps/api/captureos/api/company_profile.py:42:        missing_fields=profile.missing_fields,
apps/api/captureos/api/company_profile.py:75:        "company_brain.build_requested",
apps/api/captureos/api/company_profile.py:126:        overrides = dict(profile.user_overrides or {})
apps/api/captureos/api/company_profile.py:140:        profile.user_overrides = overrides
apps/api/captureos/models/company.py:44:    missing_fields: Mapped[list] = mapped_column(
apps/api/captureos/models/company.py:48:    user_overrides: Mapped[dict] = mapped_column(
apps/api/captureos/models/filings.py:77:    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
apps/api/captureos/api/orgs.py:20:    org = Organization(name=body.name, uei=body.uei)
apps/api/captureos/api/orgs.py:28:        uei=org.uei,
apps/api/captureos/api/orgs.py:47:            uei=org.uei,
apps/api/captureos/api/orgs.py:62:        uei=org.uei,
apps/api/captureos/schemas/company.py:17:    uei: str | None = None
apps/api/captureos/schemas/company.py:19:    document_ids: list[uuid.UUID] | None = None
apps/api/captureos/schemas/company.py:34:    missing_fields: list = Field(default_factory=list)
apps/api/captureos/ingestion/service.py:95:                    locator=chunk.locator,
apps/api/captureos/ingestion/chunking.py:2:carries a locator that resolves citations back to a source (FR-DI-5)."""
apps/api/captureos/ingestion/chunking.py:18:    locator: str
apps/api/captureos/ingestion/chunking.py:56:                chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"page {page.page}"))
apps/api/captureos/ingestion/chunking.py:60:            chunks.append(Chunk(ordinal=ordinal, text=piece, locator=f"chunk {i + 1}"))
apps/api/captureos/schemas/org.py:15:    uei: str | None = Field(default=None, max_length=32)
apps/api/captureos/schemas/org.py:21:    uei: str | None = None
apps/api/captureos/providers/audit.py:61:            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))
apps/api/captureos/api/documents.py:52:        source_kind=doc.source_kind,
apps/api/captureos/api/documents.py:87:        source_kind=DocumentSourceKind.upload.value,
apps/api/captureos/api/documents.py:101:        "document.upload_initiated",
apps/api/captureos/api/documents.py:183:        source_kind=DocumentSourceKind.paste.value,

exec
/bin/zsh -lc "rg -n \"except Exception|contextlib\\.suppress|raise_for_status|logger\\.info\\(|logger\\.error\\(|return \\\"\\\"|return \\{\\}\" apps/api/captureos/agents apps/api/captureos/workflows apps/api/captureos/ingestion apps/api/captureos/services apps/api/captureos/api apps/api/captureos/providers -g '"'!**/__pycache__/**'"'" in /Users/anishguntreddi/Documents/hackathon
 succeeded in 0ms:
apps/api/captureos/agents/base.py:60:        return {}
apps/api/captureos/agents/base.py:86:        except Exception as exc:
apps/api/captureos/agents/base.py:88:            logger.error("agent.failed", agent=self.name, error=str(exc))
apps/api/captureos/providers/secrets.py:47:        except Exception:
apps/api/captureos/ingestion/website.py:33:    except Exception:  # noqa: BLE001 - DNS failure → treat as unreachable, degrade gracefully
apps/api/captureos/ingestion/website.py:74:    with contextlib.suppress(Exception):  # malformed HTML should not crash ingestion
apps/api/captureos/ingestion/website.py:86:        logger.info("website.blocked_url", url=url, reason="ssrf_guard")
apps/api/captureos/ingestion/website.py:87:        return ""
apps/api/captureos/ingestion/website.py:95:            resp.raise_for_status()
apps/api/captureos/ingestion/website.py:97:    except Exception as exc:  # noqa: BLE001 - graceful degradation (NFR-7/8)
apps/api/captureos/ingestion/website.py:98:        logger.info("website.fetch_failed", url=url, error=str(exc))
apps/api/captureos/ingestion/website.py:99:        return ""
apps/api/captureos/providers/audit.py:60:        except Exception as exc:  # audit must never break the caller
apps/api/captureos/providers/audit.py:61:            logger.error("audit.emit_failed", error=str(exc), action=event.get("action"))
apps/api/captureos/providers/audit.py:88:            logger.error("audit.bigquery_insert_failed", errors=str(errors))
apps/api/captureos/workflows/engine.py:113:        except Exception as exc:  # noqa: BLE001 - failure must be captured, not propagated
apps/api/captureos/workflows/engine.py:127:            logger.error("workflow.step_failed", run_id=str(run.id), step=name, error=str(exc))
apps/api/captureos/workflows/dispatch.py:24:            logger.error("workflow.run_missing", run_id=str(run_id))
apps/api/captureos/ingestion/service.py:69:        logger.info("ingest.deduped", document_id=str(document.id), existing=str(dup.id))

codex
**Findings**
- `Critical` [api/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:77), [providers/storage.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:28): local blob isolation is bypassable. `filename` is embedded into `rel_key` unchanged, and `LocalStorage._path()` only constrains the resolved path to the storage base, not to `base/<org_id>`. A filename like `../../<victim-org>/secret.txt` lets org A write/read org B blobs through the `put_blob`/`get_blob` routes when `STORAGE_PROVIDER=local`, violating `CON-5`. Fix: reject path separators / dot-segments in `filename` and `rel_key`, and enforce the resolved path stays under the caller’s org subdirectory.

- `High` [ingestion/website.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/website.py:89): the SSRF guard only validates the initial URL, but `httpx` is configured with `follow_redirects=True`. A public URL can 30x to `http://127.0.0.1/...`, `http://169.254.169.254/...`, or another internal host and will be fetched server-side. Fix: disable automatic redirects or re-validate every redirect target (scheme + hostname + resolved IP) before following it.

- `High` [api/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:117), [providers/storage.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:110), [services/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/documents.py:36): the upload/ingest path is still unbounded. `put_blob()` reads the entire request body into memory, `_MAX_UPLOAD_BYTES` is unused, GCS signed uploads have no size restriction, and ingest later loads the full stored object into memory again. This is a straightforward memory/DoS vector. Fix: enforce a hard byte limit at upload initiation and sink time, stream uploads instead of `await request.body()`, and reject or chunk large objects before ingest.

- `High` [agents/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/company_brain.py:48), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:173): the citation contract is not schema-enforced. `EvidenceClaim.source_kind` is a free-form `str`, so bad LLM output will still validate, and the service silently rewrites unknown values to the `user_input` source via the fallback. That means malformed model output does not trigger `FR-RE-2` schema-retry and can materialize as falsely sourced evidence. Fix: make `source_kind` an enum / `Literal["web","user_input","document"]` and reject unknown values instead of falling back.

- `High` [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:63), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:168), [api/company_profile.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/company_profile.py:29): `CON-2` is still broken end-to-end. Every `EvidenceItem` does get a non-null `source_id`, but document provenance is lost: the build step throws away `document_chunk_id`/locator, mixes excerpts from many docs, then attaches all `"document"` claims to the newest document source only. On top of that, the profile API returns claim-bearing fields and the capability statement with no citation/evidence references at all. Fix: carry excerpt IDs/chunk IDs through the agent, persist `document_chunk_id` on evidence, bind each field/claim to evidence, and return resolvable citations in the API response.

- `High` [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:50), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:96), [agents/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/company_brain.py:145), [ingestion/website.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/website.py:97): website fetch failures are silently treated as grounded input. If the fetch is blocked or fails, the workflow still sets `has_website=True` based only on URL presence, and the agent can emit `web`-sourced claims even though no website text was ingested. That is both a silent failure and a fabricated citation path. Fix: only mark website grounding available when fetch succeeds with usable text; otherwise surface the failure in run state/audit and force claims to cite actual remaining sources.

- `Medium` [schemas/company.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/company.py:17), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:62): `BuildProfileRequest` accepts `uei` and `document_ids`, but M1 ignores both. The build step always reads the most recent chunks from all org documents, so unrelated pasted solicitations/uploads can contaminate the company profile, and the optional inputs from `FR-CB-1` are not honored. Fix: persist/use `uei`, and filter grounding documents by `document_ids` when supplied.

- `Medium` [providers/audit.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:57): audit persistence failures are swallowed. If the Postgres/BigQuery write fails, the caller still succeeds and `CON-3` is silently broken. Fix: use an outbox/retry path and mark the originating request/run failed or degraded when audit durability is not achieved.

The commit-then-dispatch handoff looks correct, and I did not find a concrete rebuild-override clobber bug for fields that are actually stored. The schema-retry loop is bounded correctly, but the citation schema itself is too loose, which defeats the retry protection for sourcing.

**VERDICT**
Fail the M1 gate.

Must-fix before signoff:
- Local blob path traversal / cross-org blob access.
- Redirect-based SSRF in website fetch.
- Hard upload/object size enforcement and streaming.
- Citation contract enforcement (`source_kind` enum, no silent fallback).
- Real claim provenance for Company Brain output, including API-visible citations.
- Stop treating failed website fetches as valid web grounding.
tokens used
105,919
**Findings**
- `Critical` [api/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:77), [providers/storage.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:28): local blob isolation is bypassable. `filename` is embedded into `rel_key` unchanged, and `LocalStorage._path()` only constrains the resolved path to the storage base, not to `base/<org_id>`. A filename like `../../<victim-org>/secret.txt` lets org A write/read org B blobs through the `put_blob`/`get_blob` routes when `STORAGE_PROVIDER=local`, violating `CON-5`. Fix: reject path separators / dot-segments in `filename` and `rel_key`, and enforce the resolved path stays under the caller’s org subdirectory.

- `High` [ingestion/website.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/website.py:89): the SSRF guard only validates the initial URL, but `httpx` is configured with `follow_redirects=True`. A public URL can 30x to `http://127.0.0.1/...`, `http://169.254.169.254/...`, or another internal host and will be fetched server-side. Fix: disable automatic redirects or re-validate every redirect target (scheme + hostname + resolved IP) before following it.

- `High` [api/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/documents.py:117), [providers/storage.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/storage.py:110), [services/documents.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/documents.py:36): the upload/ingest path is still unbounded. `put_blob()` reads the entire request body into memory, `_MAX_UPLOAD_BYTES` is unused, GCS signed uploads have no size restriction, and ingest later loads the full stored object into memory again. This is a straightforward memory/DoS vector. Fix: enforce a hard byte limit at upload initiation and sink time, stream uploads instead of `await request.body()`, and reject or chunk large objects before ingest.

- `High` [agents/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/company_brain.py:48), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:173): the citation contract is not schema-enforced. `EvidenceClaim.source_kind` is a free-form `str`, so bad LLM output will still validate, and the service silently rewrites unknown values to the `user_input` source via the fallback. That means malformed model output does not trigger `FR-RE-2` schema-retry and can materialize as falsely sourced evidence. Fix: make `source_kind` an enum / `Literal["web","user_input","document"]` and reject unknown values instead of falling back.

- `High` [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:63), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:168), [api/company_profile.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/api/company_profile.py:29): `CON-2` is still broken end-to-end. Every `EvidenceItem` does get a non-null `source_id`, but document provenance is lost: the build step throws away `document_chunk_id`/locator, mixes excerpts from many docs, then attaches all `"document"` claims to the newest document source only. On top of that, the profile API returns claim-bearing fields and the capability statement with no citation/evidence references at all. Fix: carry excerpt IDs/chunk IDs through the agent, persist `document_chunk_id` on evidence, bind each field/claim to evidence, and return resolvable citations in the API response.

- `High` [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:50), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:96), [agents/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/agents/company_brain.py:145), [ingestion/website.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/ingestion/website.py:97): website fetch failures are silently treated as grounded input. If the fetch is blocked or fails, the workflow still sets `has_website=True` based only on URL presence, and the agent can emit `web`-sourced claims even though no website text was ingested. That is both a silent failure and a fabricated citation path. Fix: only mark website grounding available when fetch succeeds with usable text; otherwise surface the failure in run state/audit and force claims to cite actual remaining sources.

- `Medium` [schemas/company.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/schemas/company.py:17), [services/company_brain.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/services/company_brain.py:62): `BuildProfileRequest` accepts `uei` and `document_ids`, but M1 ignores both. The build step always reads the most recent chunks from all org documents, so unrelated pasted solicitations/uploads can contaminate the company profile, and the optional inputs from `FR-CB-1` are not honored. Fix: persist/use `uei`, and filter grounding documents by `document_ids` when supplied.

- `Medium` [providers/audit.py](/Users/anishguntreddi/Documents/hackathon/apps/api/captureos/providers/audit.py:57): audit persistence failures are swallowed. If the Postgres/BigQuery write fails, the caller still succeeds and `CON-3` is silently broken. Fix: use an outbox/retry path and mark the originating request/run failed or degraded when audit durability is not achieved.

The commit-then-dispatch handoff looks correct, and I did not find a concrete rebuild-override clobber bug for fields that are actually stored. The schema-retry loop is bounded correctly, but the citation schema itself is too loose, which defeats the retry protection for sourcing.

**VERDICT**
Fail the M1 gate.

Must-fix before signoff:
- Local blob path traversal / cross-org blob access.
- Redirect-based SSRF in website fetch.
- Hard upload/object size enforcement and streaming.
- Citation contract enforcement (`source_kind` enum, no silent fallback).
- Real claim provenance for Company Brain output, including API-visible citations.
- Stop treating failed website fetches as valid web grounding.
CODEX_EXIT=0

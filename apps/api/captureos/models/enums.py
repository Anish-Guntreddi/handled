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
    program = "program"  # Money-Finder: SBA loans, SBIR/STTR, tax credits, set-aside advantages
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
    obligation_sync = "obligation_sync"
    program_scan = "program_scan"
    # Onboarding: enrich (company_brain) then match (program_scan) in one polled run (WS3).
    onboarding = "onboarding"


class CorpusAuthority(StrEnum):
    """Where a shared-corpus document came from (all public-domain US gov sources)."""

    ecfr = "ecfr"
    federal_register = "federal_register"
    govinfo = "govinfo"
    grants_gov = "grants_gov"
    irs = "irs"
    sba = "sba"
    gsa = "gsa"
    sam = "sam"
    firecrawl = "firecrawl"
    manual = "manual"


class CorpusCadence(StrEnum):
    """How often a corpus source is swept — tiered by source volatility (WS2 scheduler).

    Cost scales with *what changed* (unchanged docs never re-embed thanks to the hash diff), so
    high-volatility sources run often and slow-moving reference text runs rarely:
      * ``weekly``    — Federal Register (new final rules) + the discovery sweep.
      * ``monthly``   — eCFR/FAR codified parts + Firecrawl form/guidance pages.
      * ``quarterly`` — IRS/SBA/NIST publications (PDF sources).
    """

    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"


class CorpusDiscoveryTrigger(StrEnum):
    """How a corpus-discovery sweep was kicked off (platform op — never per-tenant)."""

    scheduled = "scheduled"  # fired by the cron/`make corpus-sync` cadence
    manual = "manual"  # an operator ran it by hand


class CorpusDiscoveryRunStatus(StrEnum):
    """Lifecycle of one bounded discovery sweep (for observability + provable currency)."""

    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class CorpusDocType(StrEnum):
    regulation = "regulation"
    form = "form"
    program = "program"
    nofo = "nofo"
    guidance = "guidance"
    publication = "publication"  # IRS pubs, SBA policy directives, NIST SPs (PDF sources)


class ObligationKind(StrEnum):
    """Recurring compliance obligations that keep a govcon/grants entity eligible (retention)."""

    sam_registration = "sam_registration"  # SAM.gov entity registration — annual
    reps_and_certs = "reps_and_certs"  # annual representations & certifications
    certification_renewal = "certification_renewal"  # 8(a)/WOSB/HUBZone/SDVOSB recert
    grant_report = "grant_report"  # post-award progress/financial reporting
    contract_deliverable = "contract_deliverable"  # CDRL / CPARS / periodic deliverable
    filing_deadline = "filing_deadline"  # a specific opportunity's submission deadline
    custom = "custom"


class RecurrenceCadence(StrEnum):
    none = "none"
    monthly = "monthly"
    quarterly = "quarterly"
    semiannual = "semiannual"
    annual = "annual"


class ObligationStatus(StrEnum):
    upcoming = "upcoming"  # due_date is beyond the reminder window
    due_soon = "due_soon"  # within the reminder lead window
    overdue = "overdue"  # past due_date, not completed
    completed = "completed"
    dismissed = "dismissed"


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


class EntitlementTier(StrEnum):
    """Which paid tier an org's active entitlement covers (drives ``assert_entitled``)."""

    audit = "audit"
    sprint = "sprint"
    autopilot = "autopilot"


class EntitlementStatus(StrEnum):
    """Lifecycle of a per-org subscription entitlement (mirrors Stripe subscription states)."""

    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"


class CardholderStatus(StrEnum):
    """Stripe Issuing cardholder status."""

    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class CardStatus(StrEnum):
    """Stripe Issuing card status."""

    active = "active"
    inactive = "inactive"
    canceled = "canceled"


class SpendInterval(StrEnum):
    """Budget reset interval — mirrors Stripe ``spending_controls`` interval values."""

    per_authorization = "per_authorization"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"
    all_time = "all_time"


class SpendBudgetSource(StrEnum):
    """How a budget rule was created: translated from natural language, or set by hand."""

    nl = "nl"
    manual = "manual"


class SpendDecision(StrEnum):
    """Outcome of a real-time issuing authorization (the deterministic hot-path verdict)."""

    approved = "approved"
    declined = "declined"


class SpendRuleKind(StrEnum):
    """A precomputed allow/deny rule the hot path reads (materialized by the cold-path agent)."""

    allow = "allow"
    deny = "deny"


class SpendRuleMatch(StrEnum):
    """What dimension a spend rule / budget matches an authorization on."""

    merchant = "merchant"
    mcc = "mcc"
    category = "category"

"""All ORM models. Importing this package registers every table on ``Base.metadata``
(required for Alembic autogenerate and ``create_all``)."""

from captureos.db.base import Base
from captureos.models.audit import AuditEvent
from captureos.models.billing import (
    BillingWebhookEvent,
    CustomerFeedback,
    RevenueRecord,
    Subscription,
)
from captureos.models.company import CompanyProfile
from captureos.models.corpus import CorpusChunk, CorpusDocument
from captureos.models.corpus_discovery import CorpusDiscoveryRun
from captureos.models.documents import Document, DocumentChunk
from captureos.models.entitlement import Entitlement
from captureos.models.evidence import EvidenceItem, Source
from captureos.models.filings import (
    Approval,
    EvidenceMatch,
    Filing,
    FilingRequirement,
    GeneratedDocument,
    Recommendation,
)
from captureos.models.guardrails import ConnectedAccount, PaymentEvent, SpendPolicy
from captureos.models.jobs import WorkflowJob
from captureos.models.obligations import Obligation
from captureos.models.opportunities import Opportunity
from captureos.models.org import Organization, OrgMember, User
from captureos.models.spend import (
    Card,
    Cardholder,
    SpendAuthorization,
    SpendBudget,
    SpendMerchantRule,
)
from captureos.models.workflow import AgentRun, WorkflowRun, WorkflowStep

__all__ = [
    "Base",
    "AuditEvent",
    "BillingWebhookEvent",
    "CustomerFeedback",
    "RevenueRecord",
    "Subscription",
    "CompanyProfile",
    "CorpusChunk",
    "CorpusDocument",
    "CorpusDiscoveryRun",
    "Document",
    "DocumentChunk",
    "Entitlement",
    "EvidenceItem",
    "Source",
    "Approval",
    "EvidenceMatch",
    "Filing",
    "FilingRequirement",
    "GeneratedDocument",
    "Recommendation",
    "Obligation",
    "Opportunity",
    "OrgMember",
    "Organization",
    "User",
    "Card",
    "Cardholder",
    "SpendAuthorization",
    "SpendBudget",
    "SpendMerchantRule",
    "AgentRun",
    "WorkflowRun",
    "WorkflowStep",
    "WorkflowJob",
    "ConnectedAccount",
    "SpendPolicy",
    "PaymentEvent",
]

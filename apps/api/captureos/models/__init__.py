"""All ORM models. Importing this package registers every table on ``Base.metadata``
(required for Alembic autogenerate and ``create_all``)."""

from captureos.db.base import Base
from captureos.models.audit import AuditEvent
from captureos.models.billing import CustomerFeedback, RevenueRecord, Subscription
from captureos.models.company import CompanyProfile
from captureos.models.corpus import CorpusChunk, CorpusDocument
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
from captureos.models.jobs import WorkflowJob
from captureos.models.obligations import Obligation
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
    "CorpusChunk",
    "CorpusDocument",
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
    "Obligation",
    "Opportunity",
    "OrgMember",
    "Organization",
    "User",
    "AgentRun",
    "WorkflowRun",
    "WorkflowStep",
    "WorkflowJob",
]

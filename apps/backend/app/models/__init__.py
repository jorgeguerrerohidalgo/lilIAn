from app.models.agent import AgentRun, AgentStep
from app.models.analysis_report import AnalysisReport
from app.models.audit_log import AuditLog
from app.models.chat import ChatMessage, ChatSession
from app.models.client import Client
from app.models.consent import (
    BreachIncident,
    BreachSeverity,
    ConsentRecord,
    ConsentScope,
    DataProcessingActivity,
    RightsRequest,
    RightsRequestStatus,
    RightsRequestType,
)
from app.models.deadline_alert import DeadlineAlert
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_chunk import DocumentChunk
from app.models.invitation import Invitation
from app.models.law_chunk import LawChunk
from app.models.law_chunk_version import LawChunkVersion
from app.models.legal_area import LegalArea
from app.models.legal_source import LegalSource, LegalSourceVersion
from app.models.matter import Matter
from app.models.memory import CaseContextSnapshot, FeedbackSignal, UserFact
from app.models.norm_catalog import NormCatalog, NormType
from app.models.norm_relation import NormRelation, NormRelationType
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.precedent import Precedent
from app.models.review import Review
from app.models.risk_item import RiskItem
from app.models.subscription import Plan, Subscription, UsageEvent
from app.models.template import MatterNote, MatterStatusHistory, Template
from app.models.user import User

__all__ = [
    "Organization",
    "User",
    "OrganizationMember",
    "Matter",
    "Document",
    "DocumentChunk",
    "DocumentAnalysis",
    "LegalSource",
    "LegalSourceVersion",
    "AnalysisReport",
    "RiskItem",
    "ChatSession",
    "ChatMessage",
    "Template",
    "MatterNote",
    "MatterStatusHistory",
    "Subscription",
    "UsageEvent",
    "Plan",
    "AuditLog",
    "Client",
    "DeadlineAlert",
    "Review",
    "Precedent",
    "Invitation",
    "LawChunk",
    "LegalArea",
    "UserFact",
    "CaseContextSnapshot",
    "FeedbackSignal",
    "AgentRun",
    "AgentStep",
    # Ley 21.719 compliance tables — see app/models/consent.py.
    "ConsentRecord",
    "ConsentScope",
    "DataProcessingActivity",
    "RightsRequest",
    "RightsRequestType",
    "RightsRequestStatus",
    "BreachIncident",
    "BreachSeverity",
    # Fase 1 corpus legal — see app/models/norm_catalog.py,
    # law_chunk_version.py, norm_relation.py.
    "NormCatalog",
    "NormType",
    "LawChunkVersion",
    "NormRelation",
    "NormRelationType",
]
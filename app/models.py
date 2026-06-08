import datetime
import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Float, Date, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

# --- Enums for Enterprise Governance ---
class ProjectStatus(str, enum.Enum):
    DRAFT = "Draft"
    VALIDATING = "Validating"
    REVIEWED = "Reviewed"
    COMPLETED = "Completed"

class DisclosureType(str, enum.Enum):
    ENTITY_PAI = "entity_pai"
    PRECONTRACTUAL = "precontractual"
    PERIODIC = "periodic"

class AnswerStatus(str, enum.Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    MISSING = "Missing"

class UserRole(str, enum.Enum):
    REVIEWER = "Reviewer"
    COMPLIANCE_OFFICER = "ComplianceOfficer"
    ADMINISTRATOR = "Administrator"

class Severity(str, enum.Enum):
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"

class PenaltyTier(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=UserRole.REVIEWER.value, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    approved_answers = relationship("FieldAnswer", back_populates="approver")
    audit_logs = relationship("AuditLog", back_populates="actor")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default="Asset Manager")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("ReportingProject", back_populates="organization", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    sfdr_article = Column(String, default="Article 8")  # "Article 6", "Article 8", "Article 9"
    strategy = Column(Text, nullable=True)
    benchmark = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    organization = relationship("Organization", back_populates="products")
    projects = relationship("ReportingProject", back_populates="product", cascade="all, delete-orphan")


class ReportingProject(Base):
    __tablename__ = "reporting_projects"

    id = Column(String, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    disclosure_type = Column(String, nullable=False)  # "entity_pai", "precontractual", "periodic"
    reporting_period_start = Column(Date, nullable=False)
    reporting_period_end = Column(Date, nullable=False)
    status = Column(String, default=ProjectStatus.DRAFT.value)  # Enum mapped as string
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    organization = relationship("Organization", back_populates="projects")
    product = relationship("Product", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    field_evidence = relationship("FieldEvidence", back_populates="project", cascade="all, delete-orphan")
    field_answers = relationship("FieldAnswer", back_populates="project", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="project", cascade="all, delete-orphan")
    what_if_scenarios = relationship("WhatIfScenario", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "pdf", "docx", "csv", "xlsx", "txt"
    source_type = Column(String, nullable=False)  # "annual_report", "sustainability_report", "factsheet", "policy"
    storage_url = Column(String, nullable=False)
    parsed_status = Column(String, default="Pending")  # "Pending", "Parsing", "Completed", "Failed"
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    project = relationship("ReportingProject", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_no = Column(Integer, default=1)
    section_title = Column(String, nullable=True)
    chunk_text = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    chunk_hash = Column(String, index=True, nullable=True)
    embedding_metadata = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="chunks")
    evidence = relationship("FieldEvidence", back_populates="chunk")


class RegulationField(Base):
    __tablename__ = "regulation_fields"

    id = Column(String, primary_key=True, index=True)
    framework = Column(String, default="SFDR")
    disclosure_type = Column(String, nullable=False)  # "entity_pai", "precontractual", "periodic"
    annex_code = Column(String, nullable=True)        # e.g., "Annex I"
    field_code = Column(String, unique=True, index=True, nullable=False) # e.g., "PAI_GHG_001"
    field_label = Column(String, nullable=False)      # e.g., "Scope 1 GHG emissions"
    field_kind = Column(String, default="narrative")  # "narrative", "numeric", "boolean", "table"
    mandatory = Column(Boolean, default=True)
    guidance = Column(JSON, nullable=True)            # JSON metadata for rules and guides
    regulation_version = Column(String, default="2022/1288", nullable=False)

    # --- Legal Consequence Metadata (NEW) ---
    legal_basis = Column(String, nullable=True)       # e.g., "SFDR Art. 7(1)(a), RTS Art. 5"
    penalty_tier = Column(String, default=PenaltyTier.MEDIUM.value)  # Low/Medium/High/Critical
    enforcement_body = Column(String, nullable=True)  # e.g., "ESMA", "National Competent Authority"
    cross_references = Column(JSON, nullable=True)    # [{framework, field_code, relationship}]

    answers = relationship("FieldAnswer", back_populates="regulation_field", cascade="all, delete-orphan")
    evidence = relationship("FieldEvidence", back_populates="regulation_field", cascade="all, delete-orphan")


class FieldEvidence(Base):
    __tablename__ = "field_evidence"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False)
    regulation_field_id = Column(String, ForeignKey("regulation_fields.id", ondelete="CASCADE"), nullable=False)
    document_chunk_id = Column(String, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    source_locator = Column(JSON, nullable=True)      # e.g., {"page": 12, "file": "report.pdf"}
    extracted_value = Column(JSON, nullable=True)     # e.g., {"value": 125000, "unit": "tCO2e"}
    confidence = Column(Float, default=1.0)
    extraction_method = Column(String, default="hybrid_retrieval") # "hybrid_retrieval", "manual", "llm"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Replicability fields
    regulation_version = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    model_parameters = Column(JSON, nullable=True)

    project = relationship("ReportingProject", back_populates="field_evidence")
    regulation_field = relationship("RegulationField", back_populates="evidence")
    chunk = relationship("DocumentChunk", back_populates="evidence")

    # Composite Unique Constraint for deduplication
    __table_args__ = (
        UniqueConstraint(
            "project_id", "regulation_field_id", "document_chunk_id", "extraction_method", 
            name="uq_project_field_evidence_chunk"
        ),
    )


class FieldAnswer(Base):
    __tablename__ = "field_answers"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False)
    regulation_field_id = Column(String, ForeignKey("regulation_fields.id", ondelete="CASCADE"), nullable=False)
    answer_json = Column(JSON, nullable=True)         # structured representation
    answer_text = Column(Text, nullable=True)         # narrative draft
    status = Column(String, default=AnswerStatus.DRAFT.value)          # Enum mapped as string
    model_name = Column(String, nullable=True)        # model used for drafting
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Versioning & Traceability
    version_no = Column(Integer, default=1, nullable=False)
    is_latest = Column(Boolean, default=True, nullable=False)
    regulation_version = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    model_parameters = Column(JSON, nullable=True)

    # Auditable reviewer workflow
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    project = relationship("ReportingProject", back_populates="field_answers")
    regulation_field = relationship("RegulationField", back_populates="answers")
    approver = relationship("User", back_populates="approved_answers")

    # Unique version constraint per project/field
    __table_args__ = (
        UniqueConstraint(
            "project_id", "regulation_field_id", "version_no", 
            name="uq_project_field_answer_version"
        ),
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False)
    regulation_field_id = Column(String, ForeignKey("regulation_fields.id", ondelete="CASCADE"), nullable=True)
    rule_name = Column(String, nullable=False)        # e.g., "rule_answer_must_have_evidence"
    severity = Column(String, default=Severity.WARNING.value)
    passed = Column(Boolean, default=True)
    details = Column(JSON, nullable=True)             # e.g., {"message": "Answer differs from..."}
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # --- Legal Consequence Fields (NEW) ---
    regulation_ref = Column(String, nullable=True)    # e.g., "SFDR RTS Annex I, Article 1.14"
    legal_consequence = Column(Text, nullable=True)   # human-readable legal consequence
    penalty_range = Column(String, nullable=True)     # e.g., "Up to €5M or 10% annual turnover"
    remediation = Column(Text, nullable=True)         # actionable remediation steps
    escalation_required = Column(Boolean, default=False)

    project = relationship("ReportingProject", back_populates="validation_results")


class WhatIfScenario(Base):
    """Stores what-if legal risk simulation results for a project."""
    __tablename__ = "what_if_scenarios"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False)
    scenario_name = Column(String, nullable=False)
    scenario_description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)          # scenario input parameters
    triggered_obligations = Column(JSON, nullable=True)  # list of triggered regulation articles
    legal_consequences = Column(JSON, nullable=True)  # list of consequence objects
    risk_score = Column(Float, default=0.0)           # computed overall risk score (0-100)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    project = relationship("ReportingProject", back_populates="what_if_scenarios")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)      # "project", "answer", "document"
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)           # "create", "modify", "approve", "reject"
    actor_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(String, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    actor = relationship("User", back_populates="audit_logs")
    project = relationship("ReportingProject")

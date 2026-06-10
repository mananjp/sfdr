import os
import uuid
import datetime
import tempfile
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List, Dict, Any, Optional

from app.config import UPLOAD_DIR, BASE_DIR, GROQ_API_KEY, DEFAULT_MODEL
from app.database import get_db, Base, engine
from app.models import (
    Organization, Product, ReportingProject, Document, DocumentChunk,
    RegulationField, FieldEvidence, FieldAnswer, ValidationResult, AuditLog, User,
    WhatIfScenario, ProjectStatus, AnswerStatus, AuditorLedgerEntry, MetricSnapshot
)
from app.schemas import (
    ReportingProjectCreate, ReportingProjectUpdate, ReportingProject as RPResponse,
    Product as ProductResponse, MatrixItem, FieldAnswerUpdate,
    UserCreate, User as UserResponse, AuditLogResponse, Token,
    RegulationField as RegFieldResponse, LegalConsequenceDetail,
    WhatIfScenarioCreate, WhatIfScenarioResponse, LegalRiskSummary,
    ScenarioParseRequest, ScenarioParseResponse, AuditorLedgerResponse,
    DocumentIntegrityResponse, MetricSnapshotResponse, TrendForecastResponse,
    ScenarioInterventionRequest
)
from app.auth import (
    get_password_hash, verify_password, create_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
)
from fastapi.security import OAuth2PasswordRequestForm
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.generation import GenerationService
from app.services.validation import ValidationService
from app.services.export import ExportService
from app.services.what_if_engine import WhatIfEngine

# Initialize database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Regulatory Intelligence & Compliance Workflow Engine API",
    description="GenAI-powered compliance workspace with legal consequence mapping across SFDR, CSRD, and multi-framework regulatory obligations.",
    version="2.0.0"
)

@app.on_event("startup")
def on_startup():
    from app.seed_regulations import seed_database
    try:
        seed_database()
        print("Database successfully verified/seeded on startup.")
    except Exception as e:
        print(f"Error seeding database on startup: {e}")
    
    # Integrated Maintenance & Resilience Engine
    try:
        db = next(get_db())
        
        # 0. Ensure default organization exists for multi-tenant anchoring
        default_org = db.query(Organization).filter(Organization.id == "default_org").first()
        if not default_org:
            db.add(Organization(id="default_org", name="Clarix Default Organization", type="System Root"))
            db.commit()
            print("Seeded default_org for system stability.")

        # 1. Back-fill organizations for users
        users_without_org = db.query(User).filter((User.organization_id == None) | (User.organization_id == "")).all()
        for u in users_without_org:
            u.organization_id = "default_org"
            
        # 2. Repair orphaned projects and back-fill baseline answers
        projects = db.query(ReportingProject).all()
        backfilled_count = 0
        for proj in projects:
            if not proj.organization_id:
                proj.organization_id = "default_org"

            fields = db.query(RegulationField).filter(
                RegulationField.disclosure_type == proj.disclosure_type,
                RegulationField.framework == "SFDR"
            ).all()
            for field in fields:
                exists = db.query(FieldAnswer).filter(
                    FieldAnswer.project_id == proj.id,
                    FieldAnswer.regulation_field_id == field.id
                ).first()
                if not exists:
                    db.add(FieldAnswer(
                        id=str(uuid.uuid4()),
                        project_id=proj.id,
                        regulation_field_id=field.id,
                        status=AnswerStatus.MISSING.value,
                        answer_text="",
                        version_no=1,
                        is_latest=True,
                        regulation_version=field.regulation_version
                    ))
                    backfilled_count += 1
        
        db.commit()
        db.close()
        print(f"System maintenance complete. Synchronized {backfilled_count} answering units across multi-tenant boundaries.")
    except Exception as e:
        print(f"Maintenance engine warning: {e}")

# Global Resilience Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import logging
    logging.error(f"SYSTEM_STABILITY_ALERT: {str(exc)}", exc_info=True)
    return HTMLResponse(
        status_code=500,
        content=f"Internal Server Error: {str(exc)}" if app.debug else "A critical error occurred. The system is still stable."
    )

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Endpoints ---

# --- Auth Endpoints ---

@app.post("/api/auth/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    db_user = User(
        id=str(uuid.uuid4()),
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        active=user_in.active,
        organization_id="default_org"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/auth/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- User Management Endpoints ---

@app.get("/api/users/me", response_model=UserResponse)
def get_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.get("/api/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all registered users/reviewers."""
    return db.query(User).all()

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve details of a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


# --- API Endpoints ---

@app.get("/api/products", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all seeded financial products."""
    return db.query(Product).filter(Product.active == True).all()


@app.get("/api/projects")
def get_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve reporting projects for the current user's organization strictly."""
    if not current_user.organization_id:
        # Emergency fallback for unassociated users
        return []

    projects = db.query(ReportingProject).filter(ReportingProject.organization_id == current_user.organization_id).all()
    results = []
    
    for proj in projects:
        doc_count = db.query(Document).filter(Document.project_id == proj.id).count()
        fields_count = db.query(RegulationField).filter(RegulationField.disclosure_type == proj.disclosure_type).count()
        approved_count = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == proj.id,
            FieldAnswer.status == AnswerStatus.APPROVED.value,
            FieldAnswer.is_latest == True
        ).count()
        
        progress = 0
        if fields_count > 0:
            progress = int((approved_count / fields_count) * 100)
            
        results.append({
            "id": proj.id,
            "name": proj.name,
            "disclosure_type": proj.disclosure_type,
            "reporting_period_start": proj.reporting_period_start.isoformat() if proj.reporting_period_start else None,
            "reporting_period_end": proj.reporting_period_end.isoformat() if proj.reporting_period_end else None,
            "status": proj.status,
            "created_at": proj.created_at.isoformat() if proj.created_at else None,
            "document_count": doc_count,
            "progress": progress,
            "product_name": proj.product.name if proj.product else "Entity-Level PAI"
        })
    return results


@app.post("/api/projects", response_model=RPResponse)
def create_project(project_in: ReportingProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new compliance reporting project and isolated within org."""
    project_id = str(uuid.uuid4())
    org_id = project_in.organization_id or "default_org"
    
    if project_in.product_id:
        prod = db.query(Product).filter(Product.id == project_in.product_id).first()
        if not prod:
            raise HTTPException(status_code=400, detail="Specified product not found.")
            
    db_project = ReportingProject(
        id=project_id,
        organization_id=org_id,
        product_id=project_in.product_id,
        name=project_in.name,
        disclosure_type=project_in.disclosure_type,
        reporting_period_start=project_in.reporting_period_start,
        reporting_period_end=project_in.reporting_period_end,
        status=ProjectStatus.DRAFT.value
    )
    db.add(db_project)
    
    # Create empty baseline answers
    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project_in.disclosure_type,
        RegulationField.framework == "SFDR"
    ).all()
    for field in fields:
        baseline_answer = FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=project_id,
            regulation_field_id=field.id,
            status=AnswerStatus.MISSING.value,
            answer_text="",
            version_no=1,
            is_latest=True,
            regulation_version=field.regulation_version
        )
        db.add(baseline_answer)
        
    db.commit()
    db.refresh(db_project)
    
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="create",
        actor_id=current_user.id,
        project_id=project_id,
        payload={"name": db_project.name}
    )
    db.add(audit)
    db.commit()
    return db_project


@app.put("/api/projects/{project_id}", response_model=RPResponse)
def update_project(project_id: str, update_in: ReportingProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update an existing compliance reporting project."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    update_data = update_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    
    # Audit trail
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="update",
        actor_id=current_user.id,
        project_id=project_id,
        payload=update_data
    )
    db.add(audit)
    db.commit()
    
    return project


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a reporting project and all associated cascades with ownership check."""
    project = db.query(ReportingProject).filter(
        ReportingProject.id == project_id,
        ReportingProject.organization_id == (current_user.organization_id or "default_org")
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")
        
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}


@app.post("/api/projects/{project_id}/documents")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload an ESG/sustainability report, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    doc_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"
    try:
        content = await file.read()
        import hashlib
        file_hash = hashlib.sha256(content).hexdigest()
        
        storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{file_ext}")
        with open(storage_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Create document record
    db_doc = Document(
        id=doc_id,
        project_id=project_id,
        file_name=file.filename,
        file_type=file_ext,
        source_type=source_type,
        storage_url=storage_path,
        parsed_status="Parsing",
        file_hash=file_hash,
        hash_algorithm="sha256",
        hashed_at=datetime.datetime.utcnow()
    )
    db.add(db_doc)
    db.commit()

    # Process chunks and save
    try:
        pages_content = IngestionService.process_document(storage_path, file_ext)
        chunks = IngestionService.chunk_document_data(pages_content)
        
        for idx, chk in enumerate(chunks):
            # Generate chunk hash for deduplication
            text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

            db_chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                page_no=chk["page_no"],
                section_title=chk["section_title"],
                chunk_text=chk["chunk_text"],
                metadata_json=chk["metadata"],
                chunk_hash=text_hash,
                embedding_metadata={"char_count": len(chk["chunk_text"])}
            )
            db.add(db_chunk)
            
        db_doc.parsed_status = "Completed"
        db.commit()
    except Exception as e:
        db_doc.parsed_status = "Failed"
        db.commit()
        print(f"Error parsing document: {e}")
        raise HTTPException(status_code=500, detail=f"Parsing error: {e}")

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="document",
        entity_id=doc_id,
        action="upload",
        actor_id="system",
        project_id=project_id,
        payload={"file_name": file.filename}
    )
    db.add(audit)
    db.commit()

    return {"id": doc_id, "file_name": file.filename, "status": "Completed"}


@app.post("/api/projects/{project_id}/documents/batch")
async def upload_documents_batch(
    project_id: str,
    files: List[UploadFile] = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload multiple ESG/sustainability reports, parse pages, split chunks, and save to DB."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    uploaded_docs = []
    for file in files:
        doc_id = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "txt"

        try:
            content = await file.read()
            import hashlib
            file_hash = hashlib.sha256(content).hexdigest()
            
            storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}.{file_ext}")
            with open(storage_path, "wb") as f:
                f.write(content)
        except Exception as e:
            print(f"Failed to save file {file.filename}: {e}")
            continue

        # Create document record
        db_doc = Document(
            id=doc_id,
            project_id=project_id,
            file_name=file.filename,
            file_type=file_ext,
            source_type=source_type,
            storage_url=storage_path,
            parsed_status="Parsing",
            file_hash=file_hash,
            hash_algorithm="sha256",
            hashed_at=datetime.datetime.utcnow()
        )
        db.add(db_doc)
        db.commit()

        # Process chunks and save
        try:
            pages_content = IngestionService.process_document(storage_path, file_ext)
            chunks = IngestionService.chunk_document_data(pages_content)
            
            for idx, chk in enumerate(chunks):
                text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

                db_chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    page_no=chk["page_no"],
                    section_title=chk["section_title"],
                    chunk_text=chk["chunk_text"],
                    metadata_json=chk["metadata"],
                    chunk_hash=text_hash,
                    embedding_metadata={"char_count": len(chk["chunk_text"])}
                )
                db.add(db_chunk)
                
            db_doc.parsed_status = "Completed"
            db.commit()
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Completed"})
        except Exception as e:
            db_doc.parsed_status = "Failed"
            db.commit()
            print(f"Error parsing document {file.filename}: {e}")
            uploaded_docs.append({"id": doc_id, "file_name": file.filename, "status": "Failed", "error": str(e)})

        # Audit log
        audit = AuditLog(
            id=str(uuid.uuid4()),
            entity_type="document",
            entity_id=doc_id,
            action="upload",
            actor_id="system",
            project_id=project_id,
            payload={"file_name": file.filename}
        )
        db.add(audit)
        db.commit()

    return uploaded_docs


@app.get("/api/projects/{project_id}/documents")
def get_project_documents(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve all uploaded documents for a project."""
    return db.query(Document).filter(Document.project_id == project_id).all()


@app.get("/api/projects/{project_id}/matrix", response_model=List[MatrixItem])
def get_project_compliance_matrix(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Unified compliance requirement matrix with legal consequence metadata,
    combining regulation fields, answers, citations, validation flags, and
    legal risk data from enriched regulation fields.
    """
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Get SFDR fields for this project's disclosure type
    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project.disclosure_type,
        RegulationField.framework == "SFDR"
    ).all()
    matrix = []

    for field in fields:
        # Fetch latest answer
        answer = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.regulation_field_id == field.id,
            FieldAnswer.is_latest == True
        ).first()

        # Fetch evidence (could have multiple, get the highest confidence one)
        evidence = db.query(FieldEvidence).filter(
            FieldEvidence.project_id == project_id,
            FieldEvidence.regulation_field_id == field.id
        ).order_by(FieldEvidence.confidence.desc()).first()

        # Fetch validation errors with legal consequence data
        validations = db.query(ValidationResult).filter(
            ValidationResult.project_id == project_id,
            ValidationResult.regulation_field_id == field.id
        ).all()

        validation_passed = all(v.passed for v in validations)
        validation_errors = [v.details.get("message", "") for v in validations if not v.passed]
        
        # Build enriched legal consequence details
        legal_consequences = []
        for v in validations:
            if not v.passed:
                legal_consequences.append({
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "message": v.details.get("message", "") if v.details else "",
                    "regulation_ref": v.regulation_ref,
                    "legal_consequence": v.legal_consequence,
                    "penalty_range": v.penalty_range,
                    "remediation": v.remediation,
                    "escalation_required": v.escalation_required
                })

        # Gather source location
        page_no = None
        source_file = None
        evidence_quote = None
        extracted_value = None
        confidence = 0.0
        evidence_id = None
        
        if evidence:
            evidence_id = evidence.id
            evidence_quote = evidence.source_locator.get("quote") if evidence.source_locator else None
            extracted_value = evidence.extracted_value
            confidence = evidence.confidence
            
            # Fetch source page
            chunk = db.query(DocumentChunk).filter(DocumentChunk.id == evidence.document_chunk_id).first()
            if chunk:
                page_no = chunk.page_no
                doc = db.query(Document).filter(Document.id == chunk.document_id).first()
                if doc:
                    source_file = doc.file_name

        matrix.append({
            "field_id": field.id,
            "field_code": field.field_code,
            "field_label": field.field_label,
            "field_kind": field.field_kind,
            "mandatory": field.mandatory,
            "annex_code": field.annex_code,
            "description": field.guidance.get("description", "") if field.guidance else "",
            "expected_unit": field.guidance.get("unit") if field.guidance else None,
            "regulation_version": field.regulation_version,
            "framework": field.framework,
            
            # Legal consequence metadata from field
            "legal_basis": field.legal_basis,
            "penalty_tier": field.penalty_tier or "Medium",
            "enforcement_body": field.enforcement_body,
            "cross_references": field.cross_references or [],
            
            "answer_id": answer.id if answer else None,
            "answer_text": answer.answer_text if answer else None,
            "answer_status": answer.status if answer else "Missing",
            "version_no": answer.version_no if answer else 1,
            "is_latest": answer.is_latest if answer else True,
            
            "evidence_id": evidence_id,
            "evidence_quote": evidence_quote or (evidence.source_locator.get("quote") if evidence and evidence.source_locator else None),
            "extracted_value": extracted_value,
            "confidence": confidence,
            "page_no": page_no,
            "source_file": source_file,
            
            "validation_passed": validation_passed,
            "validation_errors": validation_errors,
            "legal_consequences": legal_consequences
        })
        
    return matrix


@app.post("/api/projects/{project_id}/process")
def process_rag_and_drafting(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Core GenAI Ingestion, Retrieval, Extraction, and Drafting runner.
    For each target field, queries local chunks via TF-IDF search, extracts
    evidence through Groq, drafts template segments, and validates compliance.
    """
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # 1. Fetch all chunks in this project
    documents = db.query(Document).filter(Document.project_id == project_id).all()
    if not documents:
        raise HTTPException(status_code=400, detail="Please upload at least one ESG document before running GenAI processing.")

    doc_ids = [doc.id for doc in documents]
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(doc_ids)).all()
    if not chunks:
         raise HTTPException(status_code=400, detail="Parsed chunks are empty. Please re-upload documents.")

    chunk_dicts = [
        {
            "id": c.id,
            "page_no": c.page_no,
            "section_title": c.section_title,
            "chunk_text": c.chunk_text,
            "document_id": c.document_id
        } for c in chunks
    ]

    # Update project status
    project.status = ProjectStatus.VALIDATING.value
    db.commit()

    # 2. Iterate through SFDR fields and extract
    fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project.disclosure_type,
        RegulationField.framework == "SFDR"
    ).all()
    
    for field in fields:
        # Search chunks for field keywords
        query = f"{field.field_label} {field.guidance.get('description', '') if field.guidance else ''}"
        matching_chunks = RetrievalService.search(query, chunk_dicts, top_k=5)
        
        # Call Groq/Simulator evidence extraction
        evidence_res = GenerationService.extract_evidence(
            field_code=field.field_code,
            field_label=field.field_label,
            field_kind=field.field_kind,
            chunks=matching_chunks
        )

        # Match evidence_res chunk_id to local chunk record if found
        top_match_chunk_id = None
        if matching_chunks:
            top_match_chunk_id = matching_chunks[0]["id"]

        # Save extracted evidence — use upsert pattern for PostgreSQL
        source_locator = {
            "quote": evidence_res.get("evidence_quote"),
            "file": documents[0].file_name if documents else "Primary Report",
            "page": matching_chunks[0]["page_no"] if matching_chunks else 1
        }

        # Check for existing evidence and update, or create new
        existing_evidence = db.query(FieldEvidence).filter(
            FieldEvidence.project_id == project_id,
            FieldEvidence.regulation_field_id == field.id,
            FieldEvidence.extraction_method == ("groq_llama3" if GROQ_API_KEY else "simulation_engine")
        ).first()

        if existing_evidence:
            existing_evidence.source_locator = source_locator
            existing_evidence.extracted_value = evidence_res.get("extracted_value")
            existing_evidence.confidence = evidence_res.get("confidence", 0.0)
            existing_evidence.document_chunk_id = top_match_chunk_id
            existing_evidence.regulation_version = field.regulation_version
            existing_evidence.prompt_version = "v1.0"
            existing_evidence.model_parameters = {"temperature": 0.0, "response_format": "json_object"}
            existing_evidence.updated_at = datetime.datetime.utcnow()
        else:
            new_evidence = FieldEvidence(
                id=str(uuid.uuid4()),
                project_id=project_id,
                regulation_field_id=field.id,
                document_chunk_id=top_match_chunk_id,
                source_locator=source_locator,
                extracted_value=evidence_res.get("extracted_value"),
                confidence=evidence_res.get("confidence", 0.0),
                extraction_method="groq_llama3" if GROQ_API_KEY else "simulation_engine",
                regulation_version=field.regulation_version,
                prompt_version="v1.0",
                model_parameters={"temperature": 0.0, "response_format": "json_object"}
            )
            db.add(new_evidence)

        # Draft compliance statement narrative
        draft_res = GenerationService.draft_answer(
            field_code=field.field_code,
            field_label=field.field_label,
            field_kind=field.field_kind,
            evidence=evidence_res
        )

        # Save/Update Answer using Versioning
        existing_answers = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == project_id,
            FieldAnswer.regulation_field_id == field.id
        ).all()

        # Set is_latest = False for all existing
        for ea in existing_answers:
            ea.is_latest = False

        next_version = len(existing_answers) + 1

        db_answer = FieldAnswer(
            id=str(uuid.uuid4()),
            project_id=project_id,
            regulation_field_id=field.id,
            answer_json=draft_res.get("answer_json"),
            answer_text=draft_res.get("answer_text"),
            status=AnswerStatus.DRAFT.value if evidence_res.get("status") == "found" else AnswerStatus.MISSING.value,
            model_name=draft_res.get("model_name"),
            version_no=next_version,
            is_latest=True,
            regulation_version=field.regulation_version,
            prompt_version="v1.0",
            model_parameters={"temperature": 0.2, "response_format": "json_object"}
        )
        db.add(db_answer)

    db.commit()

    # 3. Run validation checks immediately
    ValidationService.validate_project(db, project_id)

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="process_ai",
        actor_id="system",
        project_id=project_id,
        payload={"model": DEFAULT_MODEL}
    )
    db.add(audit)
    
    # Update project status to Completed after successful extraction and validation
    project.status = ProjectStatus.COMPLETED.value
    
    db.commit()

    return {"message": "GenAI compliance workflow complete. All fields extracted, drafted, and validated."}


@app.post("/api/projects/{project_id}/validate")
def run_project_validation(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manually re-run validation checks over project disclosures."""
    results = ValidationService.validate_project(db, project_id)
    
    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="validate",
        actor_id="system",
        project_id=project_id,
        payload={"warning_count": len([r for r in results if not r.passed])}
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Validation complete", "errors_warnings_count": len(results)}


@app.put("/api/answers/{answer_id}")
def update_answer(answer_id: str, update_in: FieldAnswerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Allows reviewers to manually override and edit a generated disclosure draft, creating a new version."""
    orig_answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not orig_answer:
        raise HTTPException(status_code=404, detail="Disclosure draft segment not found.")

    # Find and update all versions to not latest
    existing_answers = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == orig_answer.project_id,
        FieldAnswer.regulation_field_id == orig_answer.regulation_field_id
    ).all()

    for ea in existing_answers:
        ea.is_latest = False

    next_version = len(existing_answers) + 1

    # Check that reviewer exists if user ID is passed
    approver_id = update_in.approved_by_user_id
    if approver_id:
        user = db.query(User).filter(User.id == approver_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    new_answer = FieldAnswer(
        id=str(uuid.uuid4()),
        project_id=orig_answer.project_id,
        regulation_field_id=orig_answer.regulation_field_id,
        answer_json=update_in.answer_json if update_in.answer_json is not None else orig_answer.answer_json,
        answer_text=update_in.answer_text,
        status=update_in.status,
        model_name=orig_answer.model_name,
        version_no=next_version,
        is_latest=True,
        regulation_version=orig_answer.regulation_version,
        prompt_version=orig_answer.prompt_version,
        model_parameters=orig_answer.model_parameters,
        approved_by=approver_id
    )
    db.add(new_answer)
    db.commit()

    # Run validation immediately to clear/update error markers
    ValidationService.validate_project(db, orig_answer.project_id)
    
    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=new_answer.id,
        action="manual_edit",
        actor_id=approver_id or "system",
        project_id=orig_answer.project_id,
        payload={"new_status": update_in.status, "version": next_version}
    )
    db.add(audit)
    db.commit()

    return {"message": "New answer version created and re-validated.", "answer_id": new_answer.id}


@app.post("/api/answers/{answer_id}/approve")
def approve_disclosure_answer(answer_id: str, reviewer_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Approve a draft disclosure field, flagging it as compliance-ready."""
    answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")

    if reviewer_id:
        user = db.query(User).filter(User.id == reviewer_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    answer.status = AnswerStatus.APPROVED.value
    answer.approved_by = reviewer_id
    db.commit()

    # Create Auditor Ledger Entry
    try:
        evidence = db.query(FieldEvidence).filter(
            FieldEvidence.regulation_field_id == answer.regulation_field_id,
            FieldEvidence.project_id == answer.project_id
        ).first()

        doc_hash = None
        doc_id = None
        source_passage = None
        source_page = None
        if evidence:
            source_passage = evidence.source_locator.get("quote") if evidence.source_locator else None
            source_page = evidence.source_locator.get("page") if evidence.source_locator else None
            
            if evidence.document_chunk_id:
                chunk = db.query(DocumentChunk).filter(DocumentChunk.id == evidence.document_chunk_id).first()
                if chunk:
                    doc_id = chunk.document_id
                    doc = db.query(Document).filter(Document.id == chunk.document_id).first()
                    if doc:
                        doc_hash = doc.file_hash

        # Remove duplicate ledger entries for the same answer
        db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.field_answer_id == answer.id).delete()

        ledger_entry = AuditorLedgerEntry(
            id=str(uuid.uuid4()),
            project_id=answer.project_id,
            regulation_field_id=answer.regulation_field_id,
            field_answer_id=answer.id,
            evidence_id=evidence.id if evidence else None,
            document_id=doc_id,
            document_hash=doc_hash,
            source_passage=source_passage,
            source_page=source_page,
            extraction_model=answer.model_name or "system",
            extraction_timestamp=answer.generated_at,
            approved_by_user_id=reviewer_id or current_user.id,
            approval_timestamp=datetime.datetime.utcnow(),
            final_value=answer.answer_text,
            integrity_verified=True,
            ledger_created_at=datetime.datetime.utcnow()
        )
        db.add(ledger_entry)
        db.commit()
    except Exception as e:
        print(f"Error creating auditor ledger entry: {e}")

    # If all latest fields in project are approved, mark project as completed
    project_id = answer.project_id
    total_fields = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.is_latest == True
    ).count()
    approved_fields = db.query(FieldAnswer).filter(
        FieldAnswer.project_id == project_id,
        FieldAnswer.is_latest == True,
        FieldAnswer.status == AnswerStatus.APPROVED.value
    ).count()

    if total_fields == approved_fields:
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        project.status = ProjectStatus.COMPLETED.value
        db.commit()

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=answer_id,
        action="approve",
        actor_id=reviewer_id or current_user.id,
        project_id=project_id
    )
    db.add(audit)
    db.commit()

    return {"message": "Disclosure approved."}


@app.post("/api/answers/{answer_id}/reject")
def reject_disclosure_answer(answer_id: str, reviewer_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Reject a draft disclosure field, pushing it back to draft status."""
    answer = db.query(FieldAnswer).filter(FieldAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")

    if reviewer_id:
        user = db.query(User).filter(User.id == reviewer_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Reviewer user not found.")

    answer.status = AnswerStatus.REJECTED.value
    answer.approved_by = None
    db.commit()

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="answer",
        entity_id=answer_id,
        action="reject",
        actor_id=reviewer_id or "system",
        project_id=answer.project_id
    )
    db.add(audit)
    db.commit()

    return {"message": "Disclosure rejected."}


# --- Regulation Fields & Cross-Framework Endpoints (NEW) ---

@app.get("/api/regulation-fields", response_model=List[RegFieldResponse])
def get_all_regulation_fields(framework: Optional[str] = None, db: Session = Depends(get_db)):
    """List all regulation fields across frameworks with legal metadata."""
    query = db.query(RegulationField)
    if framework:
        query = query.filter(RegulationField.framework == framework)
    return query.all()


@app.get("/api/regulation-fields/{field_id}/cross-references")
def get_field_cross_references(field_id: str, db: Session = Depends(get_db)):
    """Get cross-framework links for a specific field, resolved to full field objects."""
    field = db.query(RegulationField).filter(RegulationField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found.")
    
    cross_refs = field.cross_references or []
    resolved = []
    for ref in cross_refs:
        linked_field = db.query(RegulationField).filter(
            RegulationField.field_code == ref.get("field_code")
        ).first()
        resolved.append({
            "framework": ref.get("framework"),
            "field_code": ref.get("field_code"),
            "relationship": ref.get("relationship"),
            "field_label": linked_field.field_label if linked_field else "Unknown",
            "legal_basis": linked_field.legal_basis if linked_field else None,
            "penalty_tier": linked_field.penalty_tier if linked_field else None,
            "annex_code": linked_field.annex_code if linked_field else None
        })
    
    return {
        "source_field": {
            "id": field.id,
            "field_code": field.field_code,
            "field_label": field.field_label,
            "framework": field.framework
        },
        "cross_references": resolved
    }


# --- What-If Simulator Endpoints (NEW) ---

@app.get("/api/what-if/templates")
def get_what_if_templates():
    """Return pre-built what-if scenario templates."""
    return WhatIfEngine.get_templates()


@app.post("/api/projects/{project_id}/what-if/parse", response_model=ScenarioParseResponse)
def parse_what_if_scenario(project_id: str, parse_in: ScenarioParseRequest,
                           db: Session = Depends(get_db)):
    """Parse a natural language or hybrid context scenario input."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    result = WhatIfEngine.parse_scenario(
        db=db,
        project_id=project_id,
        params=parse_in.model_dump()
    )
    return result


@app.post("/api/projects/{project_id}/what-if", response_model=WhatIfScenarioResponse)
def run_what_if_scenario(project_id: str, scenario_in: WhatIfScenarioCreate,
                         db: Session = Depends(get_db)):
    """Run a what-if legal risk simulation on a project."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    result = WhatIfEngine.run_scenario(
        db=db,
        project_id=project_id,
        scenario_name=scenario_in.scenario_name,
        scenario_description=scenario_in.scenario_description,
        parameters=scenario_in.parameters
    )

    # Audit log
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="what_if",
        entity_id=result.id,
        action="simulate",
        actor_id="system",
        project_id=project_id,
        payload={"scenario": scenario_in.scenario_name, "risk_score": result.risk_score}
    )
    db.add(audit)
    db.commit()

    return result


@app.get("/api/projects/{project_id}/what-if", response_model=List[WhatIfScenarioResponse])
def get_project_what_if_scenarios(project_id: str, db: Session = Depends(get_db)):
    """List all what-if scenarios run for a project."""
    return db.query(WhatIfScenario).filter(
        WhatIfScenario.project_id == project_id
    ).order_by(WhatIfScenario.created_at.desc()).all()


# --- Legal Risk Summary Endpoint (NEW) ---

@app.get("/api/projects/{project_id}/legal-summary", response_model=LegalRiskSummary)
def get_project_legal_summary(project_id: str, db: Session = Depends(get_db)):
    """Aggregated legal risk summary for a project."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Get all SFDR fields for this project type
    sfdr_fields = db.query(RegulationField).filter(
        RegulationField.disclosure_type == project.disclosure_type,
        RegulationField.framework == "SFDR"
    ).all()

    # Count by penalty tier
    tier_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    critical_gaps = 0
    escalation_count = 0
    top_obligations = []

    for field in sfdr_fields:
        tier = field.penalty_tier or "Medium"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        # Check if field has failing validations
        failing = db.query(ValidationResult).filter(
            ValidationResult.project_id == project_id,
            ValidationResult.regulation_field_id == field.id,
            ValidationResult.passed == False
        ).all()

        if failing:
            if tier in ("Critical", "High"):
                critical_gaps += 1
            for v in failing:
                if v.escalation_required:
                    escalation_count += 1
                top_obligations.append({
                    "field_code": field.field_code,
                    "field_label": field.field_label,
                    "penalty_tier": tier,
                    "regulation_ref": v.regulation_ref,
                    "message": v.details.get("message", "") if v.details else ""
                })

    # Risk score: weighted sum
    tier_weights = {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}
    total_risk = sum(tier_weights.get(t, 5) * c for t, c in tier_counts.items() if c > 0)
    max_risk = sum(tier_weights.get(t, 5) * len(sfdr_fields) for t in ["Critical"])  # normalize
    risk_score = min(100, (critical_gaps / max(len(sfdr_fields), 1)) * 100)

    # Framework coverage
    sfdr_compliant = len(sfdr_fields) - critical_gaps
    csrd_fields = db.query(RegulationField).filter(
        RegulationField.framework == "CSRD"
    ).all()

    return {
        "total_fields": len(sfdr_fields),
        "critical_gaps": critical_gaps,
        "high_risk_fields": tier_counts["High"],
        "medium_risk_fields": tier_counts["Medium"],
        "low_risk_fields": tier_counts["Low"],
        "total_risk_score": round(risk_score, 1),
        "escalation_count": escalation_count,
        "top_obligations": sorted(top_obligations, key=lambda x: {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(x["penalty_tier"], 4))[:10],
        "framework_coverage": {
            "SFDR": {"total": len(sfdr_fields), "compliant": sfdr_compliant},
            "CSRD": {"total": len(csrd_fields), "compliant": 0}
        }
    }


# --- Exports ---

@app.get("/api/projects/{project_id}/export/markdown")
def download_markdown_package(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download an audit-ready Markdown disclosure package."""
    try:
        report = ExportService.generate_markdown_report(db, project_id)
        return PlainTextResponse(content=report, headers={
            "Content-Disposition": f"attachment; filename=SFDR_Disclosure_Package_{project_id}.md"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/export/html")
def download_html_package(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Download a stunningly designed printable HTML audit disclosure package."""
    try:
        report = ExportService.generate_html_report(db, project_id)
        return HTMLResponse(content=report, headers={
            "Content-Disposition": f"attachment; filename=SFDR_RTS_Report_{project_id}.html"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/audit-logs", response_model=List[AuditLogResponse])
def get_project_audit_logs(project_id: str, db: Session = Depends(get_db)):
    """Retrieve audit trail log entries for a specific reporting project."""
    logs = db.query(AuditLog).filter(AuditLog.project_id == project_id).order_by(AuditLog.created_at.desc()).all()
    
    results = []
    for log in logs:
        actor_username = None
        actor_role = None
        if log.actor_id:
            user = db.query(User).filter(User.id == log.actor_id).first()
            if user:
                actor_username = user.username
                actor_role = user.role
        
        results.append(AuditLogResponse(
            id=log.id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            actor_id=log.actor_id,
            project_id=log.project_id,
            payload=log.payload,
            created_at=log.created_at,
            actor_username=actor_username,
            actor_role=actor_role
        ))
    return results


# --- Settings ---

@app.get("/api/settings")
def get_settings():
    """Retrieve API settings details (hiding sensitive keys)."""
    return {
        "groq_api_key_configured": bool(GROQ_API_KEY or os.getenv("GROQ_API_KEY")),
        "default_model": DEFAULT_MODEL,
        "environment": "Development"
    }


@app.post("/api/settings")
def save_settings(payload: Dict[str, str]):
    """Update settings and environment variables dynamically."""
    global GROQ_API_KEY
    key = payload.get("groq_api_key", "").strip()
    if key:
        os.environ["GROQ_API_KEY"] = key
        return {"message": "API key configured successfully."}
    return {"message": "Empty key ignored."}


# --- Auditor & Trend Analytics Endpoints ---

@app.get("/api/projects/{project_id}/auditor-ledger", response_model=List[AuditorLedgerResponse])
def get_project_auditor_ledger(
    project_id: str,
    field_code: Optional[str] = None,
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.project_id == project_id)
    
    if field_code:
        query = query.join(RegulationField).filter(RegulationField.field_code == field_code)
    elif framework:
        query = query.join(RegulationField).filter(RegulationField.framework == framework)
        
    entries = query.all()
    results = []
    for entry in entries:
        field_code_val = entry.regulation_field.field_code if entry.regulation_field else None
        field_label_val = entry.regulation_field.field_label if entry.regulation_field else None
        doc_name_val = entry.document.file_name if entry.document else None
        approver_name_val = entry.approved_by.username if entry.approved_by else None
        
        results.append(AuditorLedgerResponse(
            id=entry.id,
            project_id=entry.project_id,
            regulation_field_id=entry.regulation_field_id,
            field_answer_id=entry.field_answer_id,
            evidence_id=entry.evidence_id,
            document_id=entry.document_id,
            document_hash=entry.document_hash,
            source_passage=entry.source_passage,
            source_page=entry.source_page,
            extraction_model=entry.extraction_model,
            extraction_timestamp=entry.extraction_timestamp,
            approved_by_user_id=entry.approved_by_user_id,
            approval_timestamp=entry.approval_timestamp,
            final_value=entry.final_value,
            integrity_verified=entry.integrity_verified,
            ledger_created_at=entry.ledger_created_at,
            field_code=field_code_val,
            field_label=field_label_val,
            document_name=doc_name_val,
            approver_username=approver_name_val
        ))
    return results


@app.get("/api/projects/{project_id}/auditor-ledger/{field_id}", response_model=AuditorLedgerResponse)
def get_auditor_ledger_field_entry(
    project_id: str,
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entry = db.query(AuditorLedgerEntry).filter(
        AuditorLedgerEntry.project_id == project_id,
        AuditorLedgerEntry.regulation_field_id == field_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Auditor ledger entry not found for this field.")
    
    field_code_val = entry.regulation_field.field_code if entry.regulation_field else None
    field_label_val = entry.regulation_field.field_label if entry.regulation_field else None
    doc_name_val = entry.document.file_name if entry.document else None
    approver_name_val = entry.approved_by.username if entry.approved_by else None
    
    return AuditorLedgerResponse(
        id=entry.id,
        project_id=entry.project_id,
        regulation_field_id=entry.regulation_field_id,
        field_answer_id=entry.field_answer_id,
        evidence_id=entry.evidence_id,
        document_id=entry.document_id,
        document_hash=entry.document_hash,
        source_passage=entry.source_passage,
        source_page=entry.source_page,
        extraction_model=entry.extraction_model,
        extraction_timestamp=entry.extraction_timestamp,
        approved_by_user_id=entry.approved_by_user_id,
        approval_timestamp=entry.approval_timestamp,
        final_value=entry.final_value,
        integrity_verified=entry.integrity_verified,
        ledger_created_at=entry.ledger_created_at,
        field_code=field_code_val,
        field_label=field_label_val,
        document_name=doc_name_val,
        approver_username=approver_name_val
    )


@app.get("/api/documents/{document_id}/integrity", response_model=DocumentIntegrityResponse)
def check_document_integrity(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = IngestionService.verify_document_integrity(document_id, db)
        return DocumentIntegrityResponse(
            document_id=result["document_id"],
            stored_hash=result["stored_hash"],
            current_hash=result["current_hash"],
            integrity_status=result["integrity_status"],
            hashed_at=result["hashed_at"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/audit-export")
def generate_audit_export_package(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        import io
        import zipfile
        import csv
        import json
        
        # Create a temp zip file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        zip_path = temp_zip.name
        temp_zip.close()

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Final reports
            try:
                markdown_report = ExportService.generate_markdown_report(db, project_id)
                zip_file.writestr("Final_Report.md", markdown_report)
            except Exception as e:
                zip_file.writestr("Final_Report.md", f"Error generating report: {e}")

            try:
                html_report = ExportService.generate_html_report(db, project_id)
                zip_file.writestr("Final_Report.html", html_report)
            except Exception as e:
                zip_file.writestr("Final_Report.html", f"Error generating report: {e}")

            # 2. Add source documents
            documents = db.query(Document).filter(Document.project_id == project_id).all()
            integrity_report = {}
            for doc in documents:
                file_path = doc.storage_url
                if file_path and os.path.exists(file_path):
                    zip_file.write(file_path, arcname=f"sources/{doc.file_name}")
                
                integrity_info = IngestionService.verify_document_integrity(doc.id, db)
                integrity_report[doc.id] = {
                    "file_name": doc.file_name,
                    "stored_hash": integrity_info.get("stored_hash"),
                    "current_hash": integrity_info.get("current_hash"),
                    "status": integrity_info.get("integrity_status"),
                    "hashed_at": integrity_info.get("hashed_at").isoformat() if integrity_info.get("hashed_at") else None
                }

            zip_file.writestr("integrity_report.json", json.dumps(integrity_report, indent=4))

            # 3. Add evidence_mapping.csv
            ledger_entries = db.query(AuditorLedgerEntry).filter(AuditorLedgerEntry.project_id == project_id).all()
            
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow([
                "ledger_entry_id", "field_code", "field_label", "reported_value",
                "source_document", "source_page", "source_passage", "document_hash",
                "approver", "approval_timestamp"
            ])
            for entry in ledger_entries:
                field_code_val = entry.regulation_field.field_code if entry.regulation_field else ""
                field_label_val = entry.regulation_field.field_label if entry.regulation_field else ""
                doc_name_val = entry.document.file_name if entry.document else ""
                approver_name_val = entry.approved_by.username if entry.approved_by else ""
                
                writer.writerow([
                    entry.id, field_code_val, field_label_val, entry.final_value or "",
                    doc_name_val, entry.source_page or "", entry.source_passage or "",
                    entry.document_hash or "", approver_name_val,
                    entry.approval_timestamp.isoformat() if entry.approval_timestamp else ""
                ])
            zip_file.writestr("evidence_mapping.csv", csv_buffer.getvalue())

            # 4. Add audit_log.csv
            logs = db.query(AuditLog).filter(AuditLog.project_id == project_id).all()
            log_buffer = io.StringIO()
            log_writer = csv.writer(log_buffer)
            log_writer.writerow(["log_id", "entity_type", "entity_id", "action", "actor", "timestamp", "payload"])
            for log in logs:
                actor_username = "system"
                if log.actor_id:
                    user = db.query(User).filter(User.id == log.actor_id).first()
                    if user:
                        actor_username = user.username
                
                log_writer.writerow([
                    log.id, log.entity_type, log.entity_id, log.action, actor_username,
                    log.created_at.isoformat() if log.created_at else "",
                    json.dumps(log.payload) if log.payload else ""
                ])
            zip_file.writestr("audit_log.csv", log_buffer.getvalue())

        return FileResponse(
            path=zip_path,
            filename=f"Audit_Export_Package_{project_id}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.post("/api/projects/{project_id}/finalize-snapshots")
def finalize_project_snapshots(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.services.snapshot_extractor import create_snapshot_from_project
    count = create_snapshot_from_project(project_id, db)
    return {"message": f"Successfully finalized and extracted {count} metric snapshots."}


@app.get("/api/organizations/{org_id}/trends/{field_code}", response_model=Dict[str, Any])
async def get_organization_metric_trends(
    org_id: str,
    field_code: str,
    horizon: int = 1,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    snapshots = db.query(MetricSnapshot).join(RegulationField).filter(
        MetricSnapshot.organization_id == org_id,
        RegulationField.field_code == field_code
    ).order_by(MetricSnapshot.reporting_year.asc()).all()

    history = []
    years = []
    values = []
    last_val = 0.0
    last_year = datetime.datetime.utcnow().year
    unit = "units"
    field_name = field_code
    
    for s in snapshots:
        history.append({
            "year": s.reporting_year,
            "value": s.value_numeric,
            "unit": s.value_unit
        })
        years.append(s.reporting_year)
        values.append(s.value_numeric)
        last_val = s.value_numeric
        last_year = s.reporting_year
        if s.value_unit:
            unit = s.value_unit
        if s.regulation_field:
            field_name = s.regulation_field.field_label

    from app.services.forecasting import forecast_metric, generate_trend_narrative
    
    if len(history) >= 2:
        forecast_res = forecast_metric(years, values, horizon_years=horizon)
        project = db.query(ReportingProject).filter(ReportingProject.organization_id == org_id).first()
        sector = project.industry_sector if project else "General"
        
        narrative = await generate_trend_narrative(
            forecast=forecast_res,
            field_name=field_name,
            current_value=last_val,
            current_year=last_year,
            unit=unit,
            industry_sector=sector,
            target_value=target_value,
            target_year=target_year
        )
    else:
        forecast_res = {"status": "insufficient_data", "min_years_required": 2}
        narrative = "Insufficient historical data to calculate trends."

    return {
        "history": history,
        "forecast": forecast_res,
        "narrative": narrative,
        "field_name": field_name,
        "unit": unit
    }


@app.get("/api/companies/{company_id}/trends/{field_code}", response_model=Dict[str, Any])
async def get_company_metric_trends(
    company_id: str,
    field_code: str,
    horizon: int = 1,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_organization_metric_trends(
        org_id=company_id,
        field_code=field_code,
        horizon=horizon,
        target_value=target_value,
        target_year=target_year,
        db=db,
        current_user=current_user
    )


@app.post("/api/organizations/{org_id}/scenarios")
def simulate_scenario_intervention(
    org_id: str,
    request: ScenarioInterventionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    snapshots = db.query(MetricSnapshot).join(RegulationField).filter(
        MetricSnapshot.organization_id == org_id,
        RegulationField.field_code == request.field_code
    ).order_by(MetricSnapshot.reporting_year.asc()).all()

    years = [s.reporting_year for s in snapshots]
    values = [s.value_numeric for s in snapshots]

    from app.services.forecasting import forecast_metric, apply_intervention
    if len(years) < 2:
        raise HTTPException(status_code=400, detail="Insufficient historical data (minimum 2 years required).")

    last_year = max(years)
    horizon = request.applicable_from_year - last_year
    if horizon <= 0:
        horizon = 1

    base_forecast = forecast_metric(years, values, horizon_years=horizon)
    scenario_forecast = apply_intervention(
        base_forecast=base_forecast,
        effect_type=request.effect_type,
        effect_magnitude=request.effect_magnitude,
        applicable_from_year=request.applicable_from_year,
        field_code=request.field_code
    )

    return {
        "base_forecast": base_forecast,
        "scenario_forecast": scenario_forecast
    }


@app.post("/api/companies/{company_id}/scenarios")
def simulate_company_scenario_intervention(
    company_id: str,
    request: ScenarioInterventionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return simulate_scenario_intervention(
        org_id=company_id,
        request=request,
        db=db,
        current_user=current_user
    )


@app.get("/api/companies/{company_id}/trend-narrative/{field_code}")
async def get_company_trend_narrative(
    company_id: str,
    field_code: str,
    target_value: Optional[float] = None,
    target_year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await get_organization_metric_trends(
        org_id=company_id,
        field_code=field_code,
        target_value=target_value,
        target_year=target_year,
        db=db,
        current_user=current_user
    )
    return {"narrative": res.get("narrative")}


# Serve CSS, JS, and Assets
static_dir = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Ensure assets are served at /assets for the build links in index.html
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Catch-all: serve the frontend SPA for ALL non-API, non-static routes
# This enables React Router client-side navigation to work on page reload
@app.get("/{path:path}", response_class=HTMLResponse)
def serve_index(path: str = ""):
    index_path = os.path.join(BASE_DIR, "app", "static", "index.html")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), headers=headers)
    return HTMLResponse(content="""
    <html>
        <head><title>Clarix | Regulatory Intelligence Engine</title></head>
        <body style="font-family:sans-serif; text-align:center; padding-top:100px;">
            <h1>Regulatory Intelligence &amp; Compliance Workflow Engine</h1>
            <p>Please build/create the static folder and index.html file to view the rich UI workspace.</p>
            <p><a href="/docs">View REST API Documentation (Swagger)</a></p>
        </body>
    </html>
    """, headers=headers)

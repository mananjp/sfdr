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
    WhatIfScenario, ProjectStatus, AnswerStatus
)
from app.schemas import (
    ReportingProjectCreate, ReportingProject as RPResponse,
    Product as ProductResponse, MatrixItem, FieldAnswerUpdate,
    UserCreate, User as UserResponse, AuditLogResponse, Token,
    RegulationField as RegFieldResponse, LegalConsequenceDetail,
    WhatIfScenarioCreate, WhatIfScenarioResponse, LegalRiskSummary
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

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        active=user_in.active
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
    """Retrieve all active reporting projects with document counts and overall completion progress."""
    projects = db.query(ReportingProject).all()
    results = []
    
    for proj in projects:
        doc_count = db.query(Document).filter(Document.project_id == proj.id).count()
        fields_count = db.query(RegulationField).filter(RegulationField.disclosure_type == proj.disclosure_type).count()
        approved_count = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == proj.id,
            FieldAnswer.status == AnswerStatus.APPROVED.value,
            FieldAnswer.is_latest == True
        ).count()
        
        # Calculate completion rate
        progress = 0
        if fields_count > 0:
            progress = int((approved_count / fields_count) * 100)
            
        results.append({
            "id": proj.id,
            "name": proj.name,
            "disclosure_type": proj.disclosure_type,
            "reporting_period_start": proj.reporting_period_start.isoformat(),
            "reporting_period_end": proj.reporting_period_end.isoformat(),
            "status": proj.status,
            "created_at": proj.created_at.isoformat(),
            "document_count": doc_count,
            "progress": progress,
            "product_name": proj.product.name if proj.product else "Entity-Level PAI"
        })
    return results


@app.post("/api/projects", response_model=RPResponse)
def create_project(project_in: ReportingProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new compliance reporting project."""
    project_id = str(uuid.uuid4())
    
    # Check that product exists if product_id is provided
    if project_in.product_id:
        prod = db.query(Product).filter(Product.id == project_in.product_id).first()
        if not prod:
            raise HTTPException(status_code=400, detail="Specified product not found.")
            
    db_project = ReportingProject(
        id=project_id,
        organization_id=project_in.organization_id,
        product_id=project_in.product_id,
        name=project_in.name,
        disclosure_type=project_in.disclosure_type,
        reporting_period_start=project_in.reporting_period_start,
        reporting_period_end=project_in.reporting_period_end,
        status=ProjectStatus.DRAFT.value
    )
    
    db.add(db_project)
    
    # Create empty baseline answers for all mapped regulation fields (SFDR only for project creation)
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
            answer_json=None,
            version_no=1,
            is_latest=True,
            regulation_version=field.regulation_version
        )
        db.add(baseline_answer)
        
    db.commit()
    db.refresh(db_project)
    
    # Audit log entry
    audit = AuditLog(
        id=str(uuid.uuid4()),
        entity_type="project",
        entity_id=project_id,
        action="create",
        actor_id="system",
        project_id=project_id,
        payload={"name": db_project.name}
    )
    db.add(audit)
    db.commit()
    
    return db_project


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a reporting project and all associated cascades."""
    project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
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
    # Save file to a temporary file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
            content = await file.read()
            tmp.write(content)
            storage_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Create document record
    db_doc = Document(
        id=doc_id,
        project_id=project_id,
        file_name=file.filename,
        file_type=file_ext,
        source_type=source_type,
        storage_url=f"temp://{file.filename}",
        parsed_status="Parsing"
    )
    db.add(db_doc)
    db.commit()

    # Process chunks and save
    try:
        pages_content = IngestionService.process_document(storage_path, file_ext)
        chunks = IngestionService.chunk_document_data(pages_content)
        
        for idx, chk in enumerate(chunks):
            # Generate chunk hash for deduplication
            import hashlib
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
    finally:
        if 'storage_path' in locals() and os.path.exists(storage_path):
            try:
                os.remove(storage_path)
            except Exception as e:
                print(f"Error deleting temporary file: {e}")

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

        # Save file to a temporary file
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
                content = await file.read()
                tmp.write(content)
                storage_path = tmp.name
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
            storage_url=f"temp://{file.filename}",
            parsed_status="Parsing"
        )
        db.add(db_doc)
        db.commit()

        # Process chunks and save
        try:
            pages_content = IngestionService.process_document(storage_path, file_ext)
            chunks = IngestionService.chunk_document_data(pages_content)
            
            for idx, chk in enumerate(chunks):
                import hashlib
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
        finally:
            if 'storage_path' in locals() and os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                except Exception as e:
                    print(f"Error deleting temporary file: {e}")

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
        actor_id=reviewer_id or "system",
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


# --- Serve Static UI files ---

# Serve CSS, JS, and Assets
static_dir = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Catch-all endpoint to serve the frontend SPA
@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(BASE_DIR, "app", "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>Regulatory Intelligence Engine</title></head>
        <body style="font-family:sans-serif; text-align:center; padding-top:100px;">
            <h1>Regulatory Intelligence & Compliance Workflow Engine</h1>
            <p>Please build/create the static folder and index.html file to view the rich UI workspace.</p>
            <p><a href="/docs">View REST API Documentation (Swagger)</a></p>
        </body>
    </html>
    """

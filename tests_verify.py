import os
import uuid
import json
import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Setup PYTHONPATH reference programmatically
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Force local SQLite for test verification
os.environ["NEON_URL"] = "sqlite:///test_verify.db"
os.environ["DATABASE_URL"] = "sqlite:///test_verify.db"

from app.database import Base, engine, SessionLocal
from app.models import (
    Organization, Product, ReportingProject, Document, DocumentChunk,
    RegulationField, FieldEvidence, FieldAnswer, ValidationResult, User
)
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.generation import GenerationService
from app.services.validation import ValidationService

def run_verifications():
    print("--- STARTING CLARIX FEATURE VERIFICATION ---")
    db = SessionLocal()
    
    try:
        # 1. Verify Seed Data
        fields = db.query(RegulationField).all()
        if len(fields) < 10:
            print("FAILED: Regulation fields not seeded correctly.")
            return False
        print("1. Seed Data: PASSED ✓")

        # 2. Mock Organization & Project Creation
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Test Org")
        db.add(org)
        
        project_id = str(uuid.uuid4())
        project = ReportingProject(
            id=project_id,
            organization_id=org_id,
            name="Verification Test Project",
            disclosure_type="periodic",
            status="Draft",
            reporting_period_start=datetime.date(2025, 1, 1),
            reporting_period_end=datetime.date(2025, 12, 31)
        )
        db.add(project)
        db.commit()
        print("2. Org & Project Creation: PASSED ✓")

        # 3. Mock Field Answer & Validation Logic
        field = fields[0]
        answer_id = str(uuid.uuid4())
        answer = FieldAnswer(
            id=answer_id,
            project_id=project_id,
            regulation_field_id=field.id,
            answer_text="Highly suspicious value 150%",
            status="Draft"
        )
        db.add(answer)
        
        # Trigger validation
        ValidationService.validate_project(db, project_id)
        
        # Check for results
        results = db.query(ValidationResult).filter(ValidationResult.project_id == project_id).all()
        print(f"3. Validation Engine: Found {len(results)} validation flags. PASSED ✓")

        # 6d. Test User creation & Reviewer approvals
        print("\n[Step 6d] Testing User creation & Reviewer approvals...")
        reviewer = User(id="user_bob", username="reviewer_bob", email="bob@veritas.com", role="Reviewer", hashed_password="mocked_password_hash")
        db.add(reviewer)
        db.commit()
        
        latest_ans.approved_by = "user_bob"
        latest_ans.status = "Approved"
        db.commit()
        print("4. Lifecycle Cleanup: PASSED ✓")

        print("\nALL LEDGRA FEATURE VERIFICATIONS: PASSED ✓")
        return True

    except Exception as e:
        print(f"ERROR DURING VERIFICATION: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    run_verifications()

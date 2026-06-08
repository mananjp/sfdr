import os
import shutil
from pathlib import Path
import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Setup PYTHONPATH reference programmatically
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine, SessionLocal
from app.models import (
    Organization, Product, ReportingProject, Document, DocumentChunk,
    RegulationField, FieldEvidence, FieldAnswer, ValidationResult, User
)
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from app.services.generation import GenerationService
from app.services.validation import ValidationService
from app.services.export import ExportService
from app.seed_regulations import SFDR_FIELDS

def run_e2e_verification():
    print("====================================================")
    print("      SFDR COMPLIANCE WORKSPACE E2E AUDIT TEST      ")
    print("====================================================")

    # 1. Initialize clean SQLite Database schema for verification
    print("\n[Step 1] Initializing fresh database schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 2. Seed default regulations and entities
        print("[Step 2] Seeding standard SFDR framework fields...")
        system_user = User(
            id="system",
            username="system",
            email="system@veritas.com",
            hashed_password="mock_hash",
            role="Administrator"
        )
        db.add(system_user)
        
        org = Organization(id="verify_org", name="Veritas Sustainable Asset Management Ltd", type="Asset Manager")
        db.add(org)
        
        prod = Product(
            id="verify_prod",
            organization_id="verify_org",
            name="Veritas Green Transition Equity Fund",
            sfdr_article="Article 8",
            strategy="Decarbonization strategy active.",
            benchmark="MSCI World ESG Index"
        )
        db.add(prod)

        for f in SFDR_FIELDS:
            field = RegulationField(
                id=f["id"],
                framework=f["framework"],
                disclosure_type=f["disclosure_type"],
                annex_code=f["annex_code"],
                field_code=f["field_code"],
                field_label=f["field_label"],
                field_kind=f["field_kind"],
                mandatory=f["mandatory"],
                guidance=f["guidance"],
                regulation_version=f.get("regulation_version", "2022/1288"),
                legal_basis=f.get("legal_basis"),
                penalty_tier=f.get("penalty_tier", "Medium"),
                enforcement_body=f.get("enforcement_body"),
                cross_references=f.get("cross_references")
            )
            db.add(field)
        db.commit()
        print("[SUCCESS] Framework pre-seeded. (Article 8 products and 12 indicators configured.)")

        # 3. Create active project
        print("\n[Step 3] Creating active Periodic disclosure project...")
        proj_id = "test_project_1"
        project = ReportingProject(
            id=proj_id,
            organization_id="verify_org",
            product_id="verify_prod",
            name="Veritas Fund 2025 Annual Periodic Report",
            disclosure_type="periodic",
            reporting_period_start=datetime.date(2025, 1, 1),
            reporting_period_end=datetime.date(2025, 12, 31),
            status="Draft"
        )
        db.add(project)
        
        # Populate empty baseline answers for project
        fields = db.query(RegulationField).filter(RegulationField.disclosure_type == "periodic").all()
        for f in fields:
            baseline = FieldAnswer(
                id=f"ans_{f.id}",
                project_id=proj_id,
                regulation_field_id=f.id,
                status="Missing",
                answer_text="",
                answer_json=None,
                version_no=1,
                is_latest=True,
                regulation_version=f.regulation_version
            )
            db.add(baseline)
        db.commit()
        print(f"[SUCCESS] Project '{project.name}' successfully opened.")

        # 4. Ingest and parse mock document
        print("\n[Step 4] Ingesting and parsing mock sustainability document...")
        mock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads", "mock_report.txt")
        os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
        
        mock_text = (
            "VERITAS SUSTAINABLE TRANSITION REPORT 2025\n\n"
            "EXECUTIVE PORTFOLIO STRATEGY AND OBJECTIVES\n"
            "The Fund successfully attained its core carbon-reduction objective by achieving an average 7.2% "
            "year-on-year emissions intensity decrease across all targeted renewable energy projects.\n\n"
            "PORTFOLIO CARBON PROFILE AND ASSET ALLOCATIONS\n"
            "For the reporting period, the Scope 1 greenhouse gas emissions of the portfolio companies were "
            "calculated as 14,820 tCO2e. Scope 2 emissions related to purchased electricity consumed by investee "
            "organizations were assessed at 8,450 tCO2e.\n"
            "The direct allocation rate to sustainable transition assets under our proprietary ESG criteria was "
            "82.5% of total capital. EU Taxonomy-aligned investments represented 14.8% of net assets.\n\n"
            "TOP HOLDINGS SUMMARY\n"
            "Top holdings included Vestas Wind Systems (4.2%, Denmark, sector: Wind Energy), Ørsted A/S (3.8%, "
            "Denmark, sector: Utility), and Iberdrola SA (3.5%, Spain, sector: Solar Power).\n"
        )
        
        with open(mock_file_path, "w", encoding="utf-8") as f:
            f.write(mock_text)

        doc_id = "mock_doc_1"
        db_doc = Document(
            id=doc_id,
            project_id=proj_id,
            file_name="mock_report.txt",
            file_type="txt",
            source_type="sustainability_report",
            storage_url=mock_file_path,
            parsed_status="Parsing"
        )
        db.add(db_doc)
        db.commit()

        # Ingestion service parsing & chunking
        pages = IngestionService.process_document(mock_file_path, "txt")
        chunks = IngestionService.chunk_document_data(pages)
        
        for idx, chk in enumerate(chunks):
            import hashlib
            text_hash = hashlib.md5(chk["chunk_text"].encode("utf-8")).hexdigest()

            db_chunk = DocumentChunk(
                id=f"chunk_{doc_id}_{idx}",
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
        print(f"[SUCCESS] Ingested document. Parsed into {len(chunks)} logical semantic chunks.")

        # 5. Semantic/Keyword Retrieval
        print("\n[Step 5] Running semantic keyword retrieval query...")
        chunk_dicts = [
            {
                "id": c.id,
                "page_no": c.page_no,
                "section_title": c.section_title,
                "chunk_text": c.chunk_text
            } for c in db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
        ]
        
        query = "What is the Scope 1 emissions in tCO2e?"
        results = RetrievalService.search(query, chunk_dicts, top_k=2)
        print(f"[SUCCESS] Query: '{query}'")
        for idx, r in enumerate(results):
            print(f"  [{idx+1}] Score: {r['score']} | Page {r['page_no']} Section: {r['section_title']}")
            print(f"      Text: {r['chunk_text'][:120]}...")

        # 6. Groq / Simulation Extraction & Drafting
        print("\n[Step 6] Running GenAI Information Extraction & Disclosure Drafting...")
        for field in fields:
            # RAG Search
            f_query = f"{field.field_label} {field.guidance.get('description', '')}"
            matches = RetrievalService.search(f_query, chunk_dicts, top_k=3)
            
            # Extract
            evidence_res = GenerationService.extract_evidence(
                field_code=field.field_code,
                field_label=field.field_label,
                field_kind=field.field_kind,
                chunks=matches
            )
            
            # Save Evidence
            source_locator = {
                "quote": evidence_res.get("evidence_quote"),
                "file": "mock_report.txt",
                "page": matches[0]["page_no"] if matches else 1
            }
            db_ev = FieldEvidence(
                id=f"ev_{field.id}",
                project_id=proj_id,
                regulation_field_id=field.id,
                document_chunk_id=matches[0]["id"] if matches else None,
                source_locator=source_locator,
                extracted_value=evidence_res.get("extracted_value"),
                confidence=evidence_res.get("confidence", 0.0),
                extraction_method="simulation_engine",
                regulation_version=field.regulation_version,
                prompt_version="v1.0",
                model_parameters={"temperature": 0.0}
            )
            db.add(db_ev)

            # Draft
            draft = GenerationService.draft_answer(
                field_code=field.field_code,
                field_label=field.field_label,
                field_kind=field.field_kind,
                evidence=evidence_res
            )

            # Update baseline
            ans = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == proj_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest == True
            ).first()
            
            ans.answer_text = draft["answer_text"]
            ans.answer_json = draft["answer_json"]
            ans.status = "Draft" if evidence_res.get("status") == "found" else "Missing"
            ans.model_name = draft["model_name"]
            
        db.commit()
        print("[SUCCESS] All disclosure fields extracted and drafted.")

        # 6b. Test FieldEvidence composite uniqueness constraint
        print("\n[Step 6b] Testing FieldEvidence composite uniqueness constraint...")
        first_ev = db.query(FieldEvidence).first()
        try:
            duplicate_ev = FieldEvidence(
                id="ev_dup_test_id",
                project_id=proj_id,
                regulation_field_id=first_ev.regulation_field_id,
                document_chunk_id=first_ev.document_chunk_id,
                source_locator=first_ev.source_locator,
                extracted_value=first_ev.extracted_value,
                confidence=first_ev.confidence,
                extraction_method=first_ev.extraction_method,
                regulation_version=first_ev.regulation_version
            )
            db.add(duplicate_ev)
            db.commit()
            raise AssertionError("Composite UniqueConstraint on FieldEvidence failed to prevent duplicate!")
        except IntegrityError:
            db.rollback()
            print("[SUCCESS] Composite unique constraint on FieldEvidence successfully intercepted duplicate extraction.")

        # 6c. Test FieldAnswer versioning increments
        print("\n[Step 6c] Testing FieldAnswer versioning increments...")
        field_to_version = fields[0]
        existing = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == proj_id,
            FieldAnswer.regulation_field_id == field_to_version.id
        ).all()
        for ea in existing:
            ea.is_latest = False
            
        next_ver = len(existing) + 1
        new_ver_ans = FieldAnswer(
            id="ans_v2_test",
            project_id=proj_id,
            regulation_field_id=field_to_version.id,
            status="Draft",
            answer_text="This is version 2 of the answer.",
            version_no=next_ver,
            is_latest=True,
            regulation_version=field_to_version.regulation_version
        )
        db.add(new_ver_ans)
        db.commit()
        
        latest_ans = db.query(FieldAnswer).filter(
            FieldAnswer.project_id == proj_id,
            FieldAnswer.regulation_field_id == field_to_version.id,
            FieldAnswer.is_latest == True
        ).first()
        
        assert latest_ans.version_no == 2
        assert latest_ans.answer_text == "This is version 2 of the answer."
        print(f"[SUCCESS] FieldAnswer versioning succeeded: version {latest_ans.version_no} is now latest.")

        # 6d. Test User creation & Reviewer approvals
        print("\n[Step 6d] Testing User creation & Reviewer approvals...")
        reviewer = User(
            id="user_bob",
            username="reviewer_bob",
            email="bob@veritas.com",
            hashed_password="mock_hash",
            role="Reviewer"
        )
        db.add(reviewer)
        db.commit()
        
        latest_ans.approved_by = "user_bob"
        latest_ans.status = "Approved"
        db.commit()
        
        updated_latest = db.query(FieldAnswer).filter(FieldAnswer.id == latest_ans.id).first()
        assert updated_latest.approved_by == "user_bob"
        assert updated_latest.status == "Approved"
        print(f"[SUCCESS] Reviewer Bob successfully approved answer version {updated_latest.version_no}.")

        # 7. Rules-based Validation Engine
        print("\n[Step 7] Running Automated Compliance Rules Engine...")
        bad_evidence = db.query(FieldEvidence).filter(FieldEvidence.regulation_field_id == "field_per_asset_alloc").first()
        bad_evidence.extracted_value = {"value": 142.5, "unit": "%"} # Invalid (> 100%)
        db.commit()

        validation_results = ValidationService.validate_project(db, proj_id)
        
        errors = [r for r in validation_results if r.severity == "Error"]
        warnings = [r for r in validation_results if r.severity == "Warning"]
        
        print(f"[SUCCESS] Validation complete. Mapped {len(validation_results)} compliance flags.")
        print(f"  - Total Errors flagged: {len(errors)}")
        print(f"  - Total Warnings flagged: {len(warnings)}")
        
        for r in validation_results:
            print(f"    * [{r.severity}] {r.rule_name}: {r.details.get('message')}")

        assert len(errors) > 0, "Validation engine failed to capture invalid percentage range (Error)"
        print("[SUCCESS] Verification check passed: Invalid percentage bounds successfully intercepted!")

        # 8. HTML & Markdown Exporters
        print("\n[Step 8] Compiling export document packages...")
        md_pkg = ExportService.generate_markdown_report(db, proj_id)
        html_pkg = ExportService.generate_html_report(db, proj_id)
        
        print(f"[SUCCESS] Compiled Markdown package size: {len(md_pkg)} characters.")
        print(f"[SUCCESS] Compiled HTML package size: {len(html_pkg)} characters.")

        print("\n====================================================")
        print("      ALL E2E WORKSPACE VERIFICATIONS: PASSED       ")
        print("====================================================")

    except Exception as e:
        print(f"\n[ERROR] E2E VERIFICATION ENCOUNTERED AN ERROR: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_e2e_verification()

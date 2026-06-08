# Regulatory Intelligence & Compliance Workspace 🌿💼

An enterprise-ready, GenAI-powered regulatory compliance workspace designed to automate, audit, and simulate Sustainable Finance Disclosure Regulation (SFDR) Regulatory Technical Standards (RTS) reporting for asset managers.

This application simplifies the complex process of compiling entity-level Principal Adverse Impact (PAI) indicators and periodic financial product disclosures (Article 8 & Article 9) by leveraging layout-aware RAG, LLM-based extraction, programmatic validation, legal consequence mapping, a regulatory impact simulator, and multi-user reviewer workflows.

---

## 🚀 Key Features

* **Regulatory Consequence Engine**: Enriches every disclosure requirement with legal basis metadata (specific RTS articles), penalty severity tiers (Low, Medium, High, Critical), and responsible enforcement bodies (e.g. ESMA, NCAs).
* **Automated Compliance Rules & Remediation Playbooks**: Programmatic sanitization and validation checks that link errors directly to legal risk evaluations and actionable, step-by-step remediation playbooks.
* **Regulatory Impact Simulator Dashboard**: A simulation sandbox that allows compliance officers to test hypothetical scenarios (e.g. removing Scope 3 disclosures, dropping board gender diversity below 30%, or reclassifying funds between SFDR Article 6/8/9) to predict triggered obligations and risk scores.
* **Cross-Framework Alignment**: Relationally maps SFDR requirements to equivalent standards in other frameworks (such as CSRD ESRS indicators).
* **RAG-Driven Ingestion & Retrieval**: Layout-aware parsing of PDF/TXT sustainability reports using PyMuPDF, segmented into logical semantic chunks with MD5-based deduplication hashes.
* **Audit-Grade Traceability**: Relationally tracks `regulation_version`, `prompt_version`, and `model_parameters` for every drafted response, alongside detailed system audit logs relationally linked to actions.
* **Versioned Draft History**: Implements a `version_no` and `is_latest` versioning system on disclosure answers to track the evolution of drafts and reviewer overrides without data loss.
* **Multi-User Reviewer Workflows**: Dedicated roles (`Reviewer`, `ComplianceOfficer`, `Administrator`) with database-backed user validation, linking approvals and rejections directly to audited actors.
* **Compliance Package Exports**: Direct compiles of disclosures into audit-ready Markdown bundles or print-ready HTML reports.

---

## 🛠️ Technology Stack

* **Backend**: Python 3.10+, FastAPI (Asynchronous REST API), Pydantic v2 (Contracts & Validation).
* **Database & Migrations**: PostgreSQL (Neon Serverless) and local-first SQLite, SQLAlchemy 2.0 (ORM), Alembic (Schema Migrations).
* **Large Language Models**: Groq Cloud SDK (Llama 3.3/3.1) with a high-fidelity simulated local fallback engine.
* **Document Processing**: PyMuPDF (`fitz`) for PDF parsing.
* **Frontend**: React 19, Vite, TailwindCSS, Framer Motion (Modern animated SPA).

---

## 🗄️ Database Schema Architecture

The database contains 11 tables designed for enterprise trace-trails:

```mermaid
erDiagram
    organizations ||--o{ products : owns
    organizations ||--o{ reporting_projects : manages
    products ||--o{ reporting_projects : target_of
    reporting_projects ||--o{ documents : ingests
    reporting_projects ||--o{ field_answers : contains
    reporting_projects ||--o{ field_evidence : contains
    reporting_projects ||--o{ validation_results : evaluates
    reporting_projects ||--o{ what_if_scenarios : simulates
    documents ||--o{ document_chunks : parsed_into
    document_chunks ||--o{ field_evidence : references
    regulation_fields ||--o{ field_answers : defines
    regulation_fields ||--o{ field_evidence : defines
    users ||--o{ field_answers : approves
    users ||--o{ audit_logs : performs
```

### Main Entities
* **`User`**: Tracks active reviewers, compliance officers, administrators, and the automated `system` agent.
* **`RegulationField`**: Dictionary of SFDR RTS regulatory indicators enriched with legal basis, penalty tiers, enforcement body, and CSRD cross-references.
* **`FieldEvidence`**: Stores extracted values, units, confidence scores, and source quotes. Enforces composite uniqueness on `(project_id, regulation_field_id, document_chunk_id, extraction_method)` to avoid duplicate citations.
* **`FieldAnswer`**: Stores disclosure statements, tracking version history (`version_no`, `is_latest`).
* **`WhatIfScenario`**: Persists historical regulatory impact simulations and risk scores.
* **`AuditLog`**: Relational audit trails linked directly to the acting user.

---

## 🏁 Getting Started

### 1. Installation (Backend)
Clone the repository and set up a Python virtual environment:
```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Secrets
Create a `.env` file in the root directory:
```env
# Groq API Key (obtain from https://console.groq.com/keys)
GROQ_API_KEY=your_groq_api_key_here

# PostgreSQL URL (e.g. Neon connection string, falls back to SQLite if not provided)
NEON_URL=postgresql://user:pass@ep-host.aws.neon.tech/neondb?sslmode=require
```

### 3. Initialize the Database
Generate and apply database migrations, then seed default metadata and users:
```powershell
# Run migrations
alembic upgrade head

# Seed default regulation fields (SFDR + CSRD), templates, and governance users
python -m app.seed_regulations
```

### 4. Build the Frontend
The modern frontend is developed as a Vite React application under `/frontend`.
To build it for production serving:
```bash
cd frontend
npm install
npm run build
```
This builds monolithic client bundles directly into `app/static/assets` for FastAPI static serving.

### 5. Run the Application
Launch the FastAPI dev server:
```powershell
# Run from repository root
python -m uvicorn app.main:app --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser to explore the dashboard.

---

## 🧪 E2E Verification Testing

A full E2E audit testing script is provided to verify all models, constraints, and pipelines:
```powershell
python tests_verify.py
```
This script validates database schema instantiation, RAG ingestion, unique constraint deduplication, answer version history, and automated rule validations.

---

## 📄 License
This project is proprietary and confidential. Created for regulatory compliance auditing under the SFDR RTS framework.

import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import FieldAnswer, FieldEvidence, ValidationResult, RegulationField, ReportingProject

# =============================================================================
# Legal Consequence Maps — maps penalty tiers and rule names to legal text
# =============================================================================

CONSEQUENCE_BY_TIER = {
    "Critical": {
        "consequence_template": "Non-disclosure constitutes a material breach of {legal_basis}. Competent authorities may impose administrative sanctions, public censure, and order corrective measures.",
        "penalty_range": "Up to €5M or 10% of annual turnover (per Member State transposition); ESMA supervisory convergence action possible"
    },
    "High": {
        "consequence_template": "Failure to disclose this indicator violates {legal_basis}. Regulatory enforcement action may include administrative fines, suspension of marketing permissions, or mandatory corrective filing.",
        "penalty_range": "Administrative fines varying by Member State; potential fund marketing suspension under Art. 14 SFDR"
    },
    "Medium": {
        "consequence_template": "Incomplete disclosure under {legal_basis} may trigger supervisory review. While not immediately sanctionable, persistent gaps may escalate to formal enforcement.",
        "penalty_range": "Supervisory letter / compliance order; potential fines upon escalation"
    },
    "Low": {
        "consequence_template": "This is an optional or supplementary disclosure under {legal_basis}. Non-disclosure carries minimal direct regulatory risk, but may affect ESG ratings and investor confidence.",
        "penalty_range": "No direct regulatory penalty; reputational risk only"
    }
}

REMEDIATION_BY_RULE = {
    "mandatory_field_missing": (
        "1. Contact portfolio companies to request the specific data point via CDP questionnaires or direct engagement.\n"
        "2. If data is genuinely unavailable, invoke the 'best efforts' exception under SFDR RTS Art. 7(2) and provide:\n"
        "   - A written explanation of why the data is unavailable\n"
        "   - The steps taken to obtain it\n"
        "   - The timeline for future disclosure\n"
        "3. Assign internal ownership to the ESG Data team with a deadline aligned to the reporting cycle."
    ),
    "provenance_missing_evidence": (
        "1. Review the source document and re-run the extraction engine with expanded context windows.\n"
        "2. If automated extraction fails, manually locate the data point and enter it via the Reviewer Desk.\n"
        "3. Ensure the evidence citation includes a direct quote, page number, and document source for audit traceability.\n"
        "4. Consider supplementing with third-party data providers (e.g., MSCI, Sustainalytics, CDP)."
    ),
    "negative_esg_value": (
        "1. Verify the sign of the extracted value — negative values for GHG indicators typically indicate data entry errors.\n"
        "2. Cross-check against the original source document.\n"
        "3. If the negative value represents a genuine carbon credit offset, annotate it with an explanatory note in the narrative."
    ),
    "percentage_out_of_bounds": (
        "1. Verify the extracted percentage against the source document.\n"
        "2. Check whether the value was mis-extracted (e.g., 0.42 extracted instead of 42%).\n"
        "3. Correct the value in the Structured Values (JSON) editor and re-validate."
    ),
    "invalid_numeric_type": (
        "1. The field requires a numeric value but received text. Open the Reviewer Desk and correct the Structured Values.\n"
        "2. If the source contains a range (e.g., '14,000-16,000'), enter the midpoint or the lower bound and note the range in the narrative."
    ),
    "unit_mismatch": (
        "1. The extracted unit does not match the SFDR RTS expected unit. Perform unit conversion if necessary.\n"
        "2. Common conversions: tonnes → tCO2e, MtCO2 → tCO2e (multiply by 1,000,000).\n"
        "3. Update the unit in the Structured Values editor."
    ),
    "narrative_too_short": (
        "1. The disclosure narrative is insufficient for regulatory compliance. Expand to include:\n"
        "   - The methodology used for calculation\n"
        "   - Data coverage and limitations\n"
        "   - Year-on-year comparison where available\n"
        "2. Minimum recommended length: 3-5 sentences for audit adequacy."
    )
}


class ValidationService:
    @staticmethod
    def validate_project(db: Session, project_id: str) -> List[ValidationResult]:
        """
        Runs automated compliance validation checks over all extracted evidence and
        drafted answers in a project, saving results with full legal consequence metadata.
        """
        # Clear existing validation results for this project
        db.query(ValidationResult).filter(ValidationResult.project_id == project_id).delete()
        
        project = db.query(ReportingProject).filter(ReportingProject.id == project_id).first()
        if not project:
            return []

        # Get all relevant regulation fields for this project type
        fields = db.query(RegulationField).filter(RegulationField.disclosure_type == project.disclosure_type).all()
        
        validation_results = []
        
        for field in fields:
            # Get evidence and answers
            evidence = db.query(FieldEvidence).filter(
                FieldEvidence.project_id == project_id,
                FieldEvidence.regulation_field_id == field.id
            ).first()
            
            answer = db.query(FieldAnswer).filter(
                FieldAnswer.project_id == project_id,
                FieldAnswer.regulation_field_id == field.id,
                FieldAnswer.is_latest == True
            ).first()

            guidance = field.guidance or {}
            expected_unit = guidance.get("unit")
            rule_checks = guidance.get("rule_checks", [])

            # 1. Presence & Completeness Check
            if field.mandatory:
                if not answer or not answer.answer_text or answer.status == "Missing":
                    res = ValidationService._create_result(
                        project_id=project_id,
                        field=field,
                        rule_name="mandatory_field_missing",
                        severity="Error",
                        passed=False,
                        message=f"Mandatory field '{field.field_label}' has no drafted disclosure narrative."
                    )
                    db.add(res)
                    validation_results.append(res)
                    continue

            # If there is no answer or evidence, skip other rules
            if not answer or not evidence or answer.status == "Missing":
                continue

            # 2. Provenance Check (No evidence support)
            confidence = evidence.confidence or 0.0
            source_locator = evidence.source_locator or {}
            if answer.answer_text and (not source_locator.get("quote") or confidence < 0.3):
                res = ValidationService._create_result(
                    project_id=project_id,
                    field=field,
                    rule_name="provenance_missing_evidence",
                    severity="Warning",
                    passed=False,
                    message=f"Disclosure drafted with extremely low evidence confidence ({confidence * 100:.0f}%). Review citation."
                )
                db.add(res)
                validation_results.append(res)

            # 3. Numeric & Type Check
            extracted_val = evidence.extracted_value or {}
            value = extracted_val.get("value") if isinstance(extracted_val, dict) else None
            unit = extracted_val.get("unit") if isinstance(extracted_val, dict) else None

            if "numeric_only" in rule_checks or field.field_kind == "numeric":
                if value is not None:
                    try:
                        # Try parsing as float
                        numeric_val = float(value)
                        
                        # Positive value check
                        if "positive_value" in rule_checks and numeric_val < 0:
                            res = ValidationService._create_result(
                                project_id=project_id,
                                field=field,
                                rule_name="negative_esg_value",
                                severity="Warning",
                                passed=False,
                                message=f"Value ({numeric_val}) for '{field.field_label}' is negative, which is unusual for ESG indicators."
                            )
                            db.add(res)
                            validation_results.append(res)

                        # Percentage Range check
                        if "percentage_range" in rule_checks or unit == "%":
                            if not (0 <= numeric_val <= 100):
                                res = ValidationService._create_result(
                                    project_id=project_id,
                                    field=field,
                                    rule_name="percentage_out_of_bounds",
                                    severity="Error",
                                    passed=False,
                                    message=f"Percentage value ({numeric_val}%) for '{field.field_label}' lies outside allowed range [0-100%]."
                                )
                                db.add(res)
                                validation_results.append(res)
                                
                    except ValueError:
                        res = ValidationService._create_result(
                            project_id=project_id,
                            field=field,
                            rule_name="invalid_numeric_type",
                            severity="Error",
                            passed=False,
                            message=f"Value '{value}' is not a valid number, which is required for numeric field '{field.field_label}'."
                        )
                        db.add(res)
                        validation_results.append(res)

            # 4. Unit Normalization Check
            if expected_unit and unit:
                # Basic unit cleaning
                if unit.lower().replace(" ", "") != expected_unit.lower().replace(" ", ""):
                    res = ValidationService._create_result(
                        project_id=project_id,
                        field=field,
                        rule_name="unit_mismatch",
                        severity="Warning",
                        passed=False,
                        message=f"Extracted unit '{unit}' differs from standard SFDR RTS expected unit '{expected_unit}'."
                    )
                    db.add(res)
                    validation_results.append(res)

            # 5. Narrative Length Check
            if "narrative_length" in rule_checks and field.field_kind == "narrative":
                txt = answer.answer_text or ""
                if len(txt.split()) < 10:
                    res = ValidationService._create_result(
                        project_id=project_id,
                        field=field,
                        rule_name="narrative_too_short",
                        severity="Info",
                        passed=False,
                        message=f"The disclosure narrative is very brief. Consider expanding to meet compliance requirements."
                    )
                    db.add(res)
                    validation_results.append(res)

        # Commit validation outcomes
        db.commit()
        return db.query(ValidationResult).filter(ValidationResult.project_id == project_id).all()

    @staticmethod
    def _create_result(project_id: str, field: RegulationField, rule_name: str,
                       severity: str, passed: bool, message: str) -> ValidationResult:
        """
        Creates a ValidationResult with full legal consequence metadata derived
        from the RegulationField's legal_basis and penalty_tier.
        """
        penalty_tier = field.penalty_tier or "Medium"
        legal_basis = field.legal_basis or "SFDR RTS (unspecified article)"
        
        # Look up consequence text and penalty range from tier
        tier_data = CONSEQUENCE_BY_TIER.get(penalty_tier, CONSEQUENCE_BY_TIER["Medium"])
        legal_consequence = tier_data["consequence_template"].format(legal_basis=legal_basis)
        penalty_range = tier_data["penalty_range"]
        
        # Look up remediation playbook
        remediation = REMEDIATION_BY_RULE.get(rule_name, "Review the field and consult your compliance officer for remediation guidance.")
        
        # Determine escalation requirement
        escalation_required = penalty_tier in ("High", "Critical") and not passed

        return ValidationResult(
            id=str(uuid.uuid4()),
            project_id=project_id,
            regulation_field_id=field.id,
            rule_name=rule_name,
            severity=severity,
            passed=passed,
            details={"message": message},
            # Legal consequence metadata
            regulation_ref=legal_basis,
            legal_consequence=legal_consequence,
            penalty_range=penalty_range,
            remediation=remediation,
            escalation_required=escalation_required
        )

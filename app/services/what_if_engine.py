import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    WhatIfScenario, RegulationField, FieldAnswer, FieldEvidence,
    ReportingProject, Product
)
from app.seed_regulations import WHAT_IF_TEMPLATES

# =============================================================================
# Regulatory consequence knowledge base for what-if simulations
# =============================================================================

OBLIGATION_DATABASE = {
    "PAI_GHG_SCOPE3": {
        "regulation_articles": [
            "SFDR Art. 7(1)(a) — mandatory PAI disclosure",
            "RTS Annex I Table 1 Indicator 3 — Scope 3 emissions",
            "ESMA Q&A on PAI reporting — 'best efforts' exception scope"
        ],
        "legal_consequences": [
            {
                "type": "regulatory_sanction",
                "description": "National Competent Authority may issue a compliance order requiring disclosure within 90 days.",
                "severity": "High"
            },
            {
                "type": "marketing_restriction",
                "description": "ESMA may issue supervisory convergence guidance affecting the fund's ESG marketing claims under Art. 8/9.",
                "severity": "High"
            },
            {
                "type": "reputational",
                "description": "Greenwashing risk — investor complaints and potential ESG rating downgrades by MSCI, Sustainalytics, or Morningstar.",
                "severity": "Medium"
            }
        ],
        "precedents": [
            "2024: CSSF (Luxembourg) issued warnings to 3 funds for incomplete Scope 3 reporting.",
            "2025: BaFin (Germany) clarified that 'best efforts' exception requires documented evidence of data requests to portfolio companies."
        ],
        "required_disclosures": [
            "Written explanation of why Scope 3 data is unavailable",
            "Evidence of data collection efforts (e.g., CDP requests sent)",
            "Timeline for future Scope 3 disclosure"
        ]
    },
    "PAI_BOARD_GENDER_DIVERSITY": {
        "regulation_articles": [
            "SFDR Art. 7(1)(a) — mandatory PAI disclosure",
            "RTS Annex I Table 1 Indicator 13 — Board gender diversity",
            "EU Gender Balance Directive 2022/2381 — minimum 40% by 2026"
        ],
        "legal_consequences": [
            {
                "type": "regulatory_attention",
                "description": "A drop below 30% may trigger supervisory scrutiny under the EU Gender Balance Directive and SFDR social PAI reporting.",
                "severity": "Medium"
            },
            {
                "type": "investor_pressure",
                "description": "Institutional investors (CalPERS, Norges Bank) have minimum 30% diversity thresholds for proxy voting and engagement.",
                "severity": "Medium"
            },
            {
                "type": "index_exclusion",
                "description": "Risk of exclusion from gender-diversity-screened indices (e.g., Bloomberg Gender Equality Index).",
                "severity": "Medium"
            }
        ],
        "precedents": [
            "2024: Several UCITS funds received investor letters demanding corrective action after diversity metrics dropped below 30%.",
            "2025: ESMA published guidance linking PAI gender diversity to broader CSRD ESRS S1 social reporting."
        ],
        "required_disclosures": [
            "Updated board composition data with gender breakdown",
            "Action plan for improving diversity metrics",
            "Timeline for achieving minimum thresholds"
        ]
    }
}

RECLASSIFICATION_CONSEQUENCES = {
    "Article 8 -> Article 6": {
        "triggered_obligations": [
            "Regulatory notification to National Competent Authority under SFDR Art. 10",
            "Updated pre-contractual disclosures removing sustainability characteristics claims",
            "Investor notification within 30 days of reclassification decision",
            "Amendment to fund prospectus and KIID/KID documentation",
            "Removal from Article 8/9 fund registries and ESG marketing databases"
        ],
        "legal_consequences": [
            {
                "type": "investor_redemption_risk",
                "description": "ESG-mandated investors may be required to divest, triggering potential redemption waves.",
                "severity": "High"
            },
            {
                "type": "regulatory_scrutiny",
                "description": "Regulators may investigate whether the original Article 8 classification was substantiated (greenwashing probe).",
                "severity": "High"
            },
            {
                "type": "commercial_impact",
                "description": "Loss of ESG premium pricing, reduced distribution access to sustainability-focused platforms.",
                "severity": "Medium"
            }
        ],
        "precedents": [
            "2023-2024: Over 1,600 funds reclassified from Art. 9 to Art. 8 following ESMA guidance on '100% sustainable investment' interpretation.",
            "2024: Luxembourg CSSF required formal notification and investor communication for all reclassifications.",
            "2025: BaFin issued specific timelines for prospectus updates following reclassification."
        ],
        "required_disclosures": [
            "Formal reclassification notification to NCA",
            "Updated pre-contractual and website disclosures",
            "Investor communication with 30-day advance notice",
            "Updated periodic report template (switch from Annex IV to basic format)"
        ]
    }
}


class WhatIfEngine:
    """Service for running what-if legal risk simulations."""

    @classmethod
    def get_templates(cls) -> List[Dict[str, Any]]:
        """Returns the pre-built what-if scenario templates."""
        return WHAT_IF_TEMPLATES

    @classmethod
    def run_scenario(cls, db: Session, project_id: str,
                     scenario_name: str, scenario_description: str,
                     parameters: Dict[str, Any],
                     user_id: Optional[str] = None) -> WhatIfScenario:
        """
        Runs a what-if simulation and stores the result.
        """
        action = parameters.get("action", "")

        if action == "remove_field":
            result = cls._handle_field_removal(db, project_id, parameters)
        elif action == "threshold_change":
            result = cls._handle_threshold_change(db, project_id, parameters)
        elif action == "reclassify_article":
            result = cls._handle_reclassification(db, project_id, parameters)
        else:
            result = {
                "triggered_obligations": [{"description": "Unknown scenario type. No obligations triggered."}],
                "legal_consequences": [],
                "risk_score": 0.0
            }

        # Persist scenario
        scenario = WhatIfScenario(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scenario_name=scenario_name,
            scenario_description=scenario_description,
            parameters=parameters,
            triggered_obligations=result["triggered_obligations"],
            legal_consequences=result["legal_consequences"],
            risk_score=result["risk_score"],
            created_by=user_id
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)

        return scenario

    @classmethod
    def _handle_field_removal(cls, db: Session, project_id: str,
                              params: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate non-disclosure of a specific field."""
        field_code = params.get("field_code", "")
        
        field = db.query(RegulationField).filter(
            RegulationField.field_code == field_code
        ).first()

        if not field:
            return {
                "triggered_obligations": [{"description": f"Field '{field_code}' not found in regulatory database."}],
                "legal_consequences": [],
                "risk_score": 10.0
            }

        # Look up knowledge base
        knowledge = OBLIGATION_DATABASE.get(field_code, {})
        
        triggered_obligations = []
        for article in knowledge.get("regulation_articles", [field.legal_basis or "Unspecified regulation"]):
            triggered_obligations.append({
                "regulation_article": article,
                "description": f"Non-disclosure of '{field.field_label}' violates this obligation.",
                "field_code": field_code
            })

        for disclosure in knowledge.get("required_disclosures", []):
            triggered_obligations.append({
                "regulation_article": "Remediation requirement",
                "description": disclosure,
                "field_code": field_code
            })

        legal_consequences = knowledge.get("legal_consequences", [
            {
                "type": "regulatory_sanction",
                "description": f"Non-disclosure of mandatory field '{field.field_label}' under {field.legal_basis} may result in enforcement action.",
                "severity": field.penalty_tier or "Medium"
            }
        ])

        # Add precedents as a separate consequence entry
        precedents = knowledge.get("precedents", [])
        if precedents:
            legal_consequences.append({
                "type": "regulatory_precedent",
                "description": "Relevant enforcement precedents: " + " | ".join(precedents),
                "severity": "Info"
            })

        # Calculate risk score based on penalty tier and mandatory status
        tier_scores = {"Critical": 90, "High": 70, "Medium": 45, "Low": 20}
        base_score = tier_scores.get(field.penalty_tier, 45)
        if field.mandatory:
            base_score = min(100, base_score + 15)

        return {
            "triggered_obligations": triggered_obligations,
            "legal_consequences": legal_consequences,
            "risk_score": float(base_score)
        }

    @classmethod
    def _handle_threshold_change(cls, db: Session, project_id: str,
                                 params: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate a metric value dropping below a threshold."""
        field_code = params.get("field_code", "")
        new_value = params.get("new_value", 0)
        threshold = params.get("threshold", 0)

        field = db.query(RegulationField).filter(
            RegulationField.field_code == field_code
        ).first()

        if not field:
            return {
                "triggered_obligations": [],
                "legal_consequences": [],
                "risk_score": 10.0
            }

        knowledge = OBLIGATION_DATABASE.get(field_code, {})

        triggered_obligations = [
            {
                "regulation_article": field.legal_basis or "Unspecified",
                "description": f"'{field.field_label}' value of {new_value} breaches the {threshold} threshold.",
                "field_code": field_code
            }
        ]

        for article in knowledge.get("regulation_articles", []):
            triggered_obligations.append({
                "regulation_article": article,
                "description": f"Threshold breach triggers obligations under this article.",
                "field_code": field_code
            })

        for disclosure in knowledge.get("required_disclosures", []):
            triggered_obligations.append({
                "regulation_article": "Remediation requirement",
                "description": disclosure,
                "field_code": field_code
            })

        legal_consequences = knowledge.get("legal_consequences", [
            {
                "type": "threshold_breach",
                "description": f"'{field.field_label}' falling to {new_value} (below {threshold}) triggers additional disclosure and remediation requirements.",
                "severity": "Medium"
            }
        ])

        precedents = knowledge.get("precedents", [])
        if precedents:
            legal_consequences.append({
                "type": "regulatory_precedent",
                "description": "Relevant precedents: " + " | ".join(precedents),
                "severity": "Info"
            })

        # Risk score — severity scales with how far below threshold
        deviation_pct = ((threshold - new_value) / threshold * 100) if threshold > 0 else 50
        tier_scores = {"Critical": 85, "High": 65, "Medium": 40, "Low": 15}
        base_score = tier_scores.get(field.penalty_tier, 40)
        risk_score = min(100, base_score + deviation_pct * 0.3)

        return {
            "triggered_obligations": triggered_obligations,
            "legal_consequences": legal_consequences,
            "risk_score": round(risk_score, 1)
        }

    @classmethod
    def _handle_reclassification(cls, db: Session, project_id: str,
                                 params: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate fund reclassification between SFDR articles."""
        from_article = params.get("from_article", "Article 8")
        to_article = params.get("to_article", "Article 6")
        key = f"{from_article} -> {to_article}"

        knowledge = RECLASSIFICATION_CONSEQUENCES.get(key, {})

        triggered_obligations = []
        for obligation in knowledge.get("triggered_obligations", [f"Reclassification from {from_article} to {to_article} triggers regulatory notification requirements."]):
            triggered_obligations.append({
                "regulation_article": "SFDR Art. 10 / NCA Notification",
                "description": obligation,
                "field_code": "RECLASSIFICATION"
            })

        for disclosure in knowledge.get("required_disclosures", []):
            triggered_obligations.append({
                "regulation_article": "Mandatory disclosure update",
                "description": disclosure,
                "field_code": "RECLASSIFICATION"
            })

        legal_consequences = knowledge.get("legal_consequences", [
            {
                "type": "reclassification",
                "description": f"Reclassification from {from_article} to {to_article} carries regulatory and commercial consequences.",
                "severity": "High"
            }
        ])

        precedents = knowledge.get("precedents", [])
        if precedents:
            legal_consequences.append({
                "type": "regulatory_precedent",
                "description": "Relevant precedents: " + " | ".join(precedents),
                "severity": "Info"
            })

        # Reclassification from higher to lower article carries high risk
        risk_map = {
            "Article 8 -> Article 6": 75.0,
            "Article 9 -> Article 8": 60.0,
            "Article 9 -> Article 6": 90.0,
            "Article 6 -> Article 8": 25.0,
            "Article 8 -> Article 9": 30.0,
        }
        risk_score = risk_map.get(key, 50.0)

        return {
            "triggered_obligations": triggered_obligations,
            "legal_consequences": legal_consequences,
            "risk_score": risk_score
        }

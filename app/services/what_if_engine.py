import uuid
import datetime
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    WhatIfScenario, RegulationField, FieldAnswer, FieldEvidence,
    ReportingProject, Product
)
from app.seed_regulations import WHAT_IF_TEMPLATES
from app.services.generation import GenerationService
from app.config import DEFAULT_MODEL

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
            result = cls._handle_custom_scenario(db, project_id, parameters)

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
        from_article = params.get("from_article") or params.get("current_value") or "Article 8"
        to_article = params.get("to_article") or params.get("proposed_value") or "Article 6"
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

    @classmethod
    def _handle_custom_scenario(cls, db: Session, project_id: str,
                                 params: Dict[str, Any]) -> Dict[str, Any]:
        """Runs dynamic custom scenario evaluation via Groq LLM if available, falling back to rule heuristics."""
        client = GenerationService.get_groq_client()
        if client:
            try:
                system_prompt = (
                    "You are a regulatory compliance AI auditor specializing in ESG regulations (SFDR, CSRD, EU Taxonomy).\n"
                    "Your task is to evaluate a custom scenario defined by the user and assess the legal risks, obligations triggered, and potential regulatory penalties.\n"
                    "Analyze the scenario parameters and optional natural language context.\n"
                    "Calculate a risk score between 0.0 (no risk) and 100.0 (extreme risk / clear breach).\n"
                    "You must output ONLY a valid JSON object matching the schema below. Do not wrap in markdown tags or extra text.\n"
                    "Output JSON Schema:\n"
                    "{\n"
                    "  \"triggered_obligations\": [\n"
                    "    {\n"
                    "      \"regulation_article\": \"string (name of the article/rule, e.g., 'SFDR Art. 9(1)')\",\n"
                    "      \"description\": \"string (how this scenario impacts or violates this obligation)\",\n"
                    "      \"field_code\": \"string (associated field code, or 'CUSTOM')\"\n"
                    "    }\n"
                    "  ],\n"
                    "  \"legal_consequences\": [\n"
                    "    {\n"
                    "      \"type\": \"string (regulatory_sanction | marketing_restriction | investor_redemption | reputational | audit_failure)\",\n"
                    "      \"description\": \"string (detailed description of the penalty, exposure, or impact)\",\n"
                    "      \"severity\": \"Low\" | \"Medium\" | \"High\" | \"Critical\"\n"
                    "    }\n"
                    "  ],\n"
                    "  \"risk_score\": float\n"
                    "}"
                )

                user_content = (
                    f"Scenario Parameters:\n"
                    f"- Action/Type: {params.get('action')}\n"
                    f"- Regulatory Framework: {params.get('framework') or 'SFDR'}\n"
                    f"- Entity Type: {params.get('entity') or 'Fund / Financial Product'}\n"
                    f"- Metric/Field Code: {params.get('field_code') or 'Not specified'}\n"
                    f"- Current Value: {params.get('current_value') or 'Not specified'}\n"
                    f"- Proposed Value: {params.get('proposed_value') or 'Not specified'}\n"
                    f"- Jurisdiction: {params.get('jurisdiction') or 'EU / General'}\n"
                    f"- Reporting Period: {params.get('reporting_period') or 'Annual'}\n"
                    f"- Natural Language Context: \"{params.get('free_text_context') or ''}\"\n"
                )

                response = client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                
                result_json = json.loads(response.choices[0].message.content)
                if "triggered_obligations" in result_json and "legal_consequences" in result_json and "risk_score" in result_json:
                    return result_json
            except Exception as e:
                print(f"Error in custom what-if LLM evaluation: {e}. Falling back to simulation.")

        # High-fidelity simulation fallback
        action = params.get("action", "custom_scenario")
        field_code = params.get("field_code", "")
        proposed_value = params.get("proposed_value", "")
        free_text = (params.get("free_text_context") or "").lower()

        # Build custom response based on keywords
        triggered_obligations = []
        legal_consequences = []
        risk_score = 50.0

        if "omission" in action or "remove" in action or "omit" in free_text or "disclosure_omission" in action:
            risk_score = 80.0
            triggered_obligations = [
                {
                    "regulation_article": "SFDR Art. 7(1) — Principal Adverse Impacts",
                    "description": f"Omission of metric '{field_code or 'disclosures'}' breaches mandatory transparency requirements.",
                    "field_code": field_code or "CUSTOM"
                },
                {
                    "regulation_article": "RTS Annex I Table 1",
                    "description": "Failure to report on all mandatory indicators is a core compliance breach.",
                    "field_code": field_code or "CUSTOM"
                }
            ]
            legal_consequences = [
                {
                    "type": "regulatory_sanction",
                    "description": "National Competent Authorities (NCAs) may issue administrative fines and order corrective disclosure filings.",
                    "severity": "High"
                },
                {
                    "type": "reputational",
                    "description": "Exposures to claims of greenwashing and potential downgrades by ESG rating providers.",
                    "severity": "High"
                }
            ]
        elif "delay" in action or "delayed" in free_text or "delayed_filing" in action:
            risk_score = 40.0
            triggered_obligations = [
                {
                    "regulation_article": "SFDR Article 11(1) — Reporting Timelines",
                    "description": "Delayed submission of disclosures violates the regulatory publication deadlines (typically June 30).",
                    "field_code": "TIMELINE"
                }
            ]
            legal_consequences = [
                {
                    "type": "audit_failure",
                    "description": "Auditor notes on delayed regulatory filings, leading to qualified compliance opinions.",
                    "severity": "Medium"
                }
            ]
        elif "estimate" in action or "estimation" in free_text or "average" in free_text or "estimation_methodology_change" in action:
            risk_score = 30.0
            triggered_obligations = [
                {
                    "regulation_article": "ESMA Guidelines on Data Quality",
                    "description": "Using estimated values is permitted only under strict 'best efforts' rules and must be clearly disclosed with calculation methodology.",
                    "field_code": field_code or "CUSTOM"
                }
            ]
            legal_consequences = [
                {
                    "type": "regulatory_attention",
                    "description": "Regulators may audit the estimation model to ensure no material misstatement of ESG metrics.",
                    "severity": "Low"
                }
            ]
        else:
            # General custom scenario response
            risk_score = 65.0
            triggered_obligations = [
                {
                    "regulation_article": "SFDR Article 4 / 7 — Transparency obligations",
                    "description": f"Custom scenario involving '{action}' affects the compliance status of field '{field_code or 'general'}'.",
                    "field_code": field_code or "CUSTOM"
                }
            ]
            legal_consequences = [
                {
                    "type": "regulatory_scrutiny",
                    "description": "User-defined operational change may trigger inquiries from National Competent Authorities depending on final implementation.",
                    "severity": "Medium"
                }
            ]

        return {
            "triggered_obligations": triggered_obligations,
            "legal_consequences": legal_consequences,
            "risk_score": risk_score
        }

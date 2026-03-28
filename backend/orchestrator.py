"""
Pipeline orchestrator that runs all 5 agents in sequence,
handles failures, and builds an audit trail.
"""

import time
from dataclasses import asdict

from agents import (
    IntakeAgent,
    ExtractionAgent,
    ResearchAgent,
    ValidationAgent,
    ScoringAgent,
)


def run_pipeline(image_bytes: bytes, filename: str, mime_type: str, client) -> dict:
    """Execute the full 5-agent pipeline and return the final report."""

    total_start = time.time()
    agent_trail = []
    doc_id = filename.rsplit(".", 1)[0] if "." in filename else filename

    # --- Agent 1: Intake ---
    intake = IntakeAgent().run(image_bytes, filename)
    agent_trail.append(_trail_entry(intake))

    if intake.status == "fail":
        return _error_report(doc_id, agent_trail, total_start, intake.decision)

    # --- Agent 2: Extraction ---
    extraction = ExtractionAgent().run(image_bytes, mime_type, client)
    agent_trail.append(_trail_entry(extraction))

    if extraction.status == "fail":
        return _error_report(doc_id, agent_trail, total_start, extraction.decision)

    fields = extraction.data.get("fields", {})
    enrichment = extraction.data.get("enrichment", {})

    # --- Agent 3: Research ---
    research_result = ResearchAgent().run(fields, enrichment, client)
    agent_trail.append(_trail_entry(research_result))
    research = research_result.data

    # --- Agent 4: Validation ---
    validation_result = ValidationAgent().run(fields, enrichment, research)
    agent_trail.append(_trail_entry(validation_result))
    validation = validation_result.data

    # --- Agent 5: Scoring ---
    scoring_result = ScoringAgent().run(fields, enrichment, research, validation)
    agent_trail.append(_trail_entry(scoring_result))
    scoring = scoring_result.data

    total_time = round(time.time() - total_start, 2)

    return {
        "doc_id": doc_id,
        "fields": fields,
        "enrichment": enrichment,
        "research": research,
        "validation": validation,
        "scoring": scoring,
        "agent_trail": agent_trail,
        "processing_time_sec": total_time,
    }


def _trail_entry(result) -> dict:
    return {
        "agent": result.agent,
        "status": result.status,
        "time_sec": result.time_sec,
        "decision": result.decision,
    }


def _error_report(doc_id: str, trail: list, start: float, reason: str) -> dict:
    return {
        "doc_id": doc_id,
        "fields": {
            "dealer_name": "", "model_name": "", "horse_power": 0,
            "asset_cost": 0,
            "signature": {"present": False, "bbox": []},
            "stamp": {"present": False, "bbox": []},
        },
        "enrichment": {"language_detected": "", "state_detected": "", "document_type": ""},
        "research": {
            "model_hp_verified": False, "expected_hp": 0, "hp_source": "",
            "dealer_found_online": False, "dealer_search_summary": "",
        },
        "validation": {"warnings": [], "errors": [reason], "hp_match": False, "all_fields_present": False},
        "scoring": {
            "authenticity_score": 0, "compliance_status": "FAIL",
            "breakdown": {}, "summary": f"Pipeline failed: {reason}",
        },
        "agent_trail": trail,
        "processing_time_sec": round(time.time() - start, 2),
    }

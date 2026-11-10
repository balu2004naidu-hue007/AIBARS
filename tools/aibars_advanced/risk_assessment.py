"""Transparent risk triage score. It is a prioritisation heuristic, not a safety certification."""
from __future__ import annotations

SEVERITY = {"NORMAL": 1, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
CAUSE_TO_IMPACT = {
    "NO_FAULT_DETECTED": "NORMAL",
    "SENSOR_DATA_TIMEOUT": "SENSOR_TIMEOUT",
    "SENSOR_STUCK_AT": "SENSOR_STUCK",
    "SENSOR_VALUE_OUT_OF_RANGE": "SENSOR_OUT_OF_RANGE",
    "COMMUNICATION_HEARTBEAT_TIMEOUT": "COMMUNICATION_TIMEOUT",
    "TASK_PROGRESS_FAILURE": "TASK_HANG",
    "COMPOUND_FAULT": "COMPOUND_FAULT",
}


def assess_risk(primary_cause: str, severity: str, confidence: float, config: dict,
                fault_count: int = 1) -> dict:
    impact_map = config["risk"].get("impact", {})
    impact_key = CAUSE_TO_IMPACT.get(primary_cause, primary_cause)
    impact = float(impact_map.get(impact_key, 0.7))
    severity_factor = SEVERITY.get(severity.upper(), 2) / 4.0
    confidence_factor = max(0.0, min(1.0, float(confidence)))
    compound_factor = 1.0 if fault_count > 1 else 0.0
    score = 100.0 * max(severity_factor, compound_factor) * impact * max(0.65, confidence_factor)
    score = round(min(100.0, score), 1)
    limits = config["risk"]
    if score <= limits["low_max"]:
        level = "LOW"
    elif score <= limits["moderate_max"]:
        level = "MODERATE"
    elif score <= limits["high_max"]:
        level = "HIGH"
    else:
        level = "CRITICAL"
    return {
        "score": score, "level": level, "severity": severity,
        "impact_factor": impact, "classifier_confidence_factor": round(confidence_factor, 4),
        "formula": "100 * max(severity/4, compound_fault_override) * impact * max(0.65, confidence)",
        "interpretation": "Heuristic triage score for prioritising simulated incidents; not a calibrated failure probability or safety risk assessment.",
    }

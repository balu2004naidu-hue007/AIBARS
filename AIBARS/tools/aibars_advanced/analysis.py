"""Combine deterministic incident evidence, ML advisory diagnosis and risk triage."""
from __future__ import annotations
import json
from pathlib import Path
from .ml_classifier import GaussianNaiveBayes, classify_run, save_model_and_report
from .risk_assessment import assess_risk


def read_run(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    incident_path = run_dir / "incident.json"
    incident = json.loads(incident_path.read_text(encoding="utf-8")) if incident_path.exists() else None
    events_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"summary": summary, "incident": incident, "events": events, "run_id": run_dir.name}


def enrich_run(run: dict, model: GaussianNaiveBayes, profile: dict) -> dict:
    ml = classify_run(run, model, profile)
    incident = run.get("incident") or {}
    cause = incident.get("primary_cause", run["summary"].get("primary_cause", "NORMAL"))
    severity = incident.get("severity", "LOW" if cause == "NO_FAULT_DETECTED" else "HIGH")
    risk = assess_risk(cause, severity, ml["confidence"], profile,
                       fault_count=len(run["summary"].get("detected_faults", [])))
    return {"ml_advisory": ml, "risk_assessment": risk}


def analyze_runs(run_root: Path, artifacts_dir: Path, profile: dict) -> list[dict]:
    ml_report = save_model_and_report(artifacts_dir)
    model = GaussianNaiveBayes.from_dict(json.loads((artifacts_dir / "fault_classifier_model.json").read_text(encoding="utf-8")))
    records = []
    for run_dir in sorted(p for p in run_root.iterdir() if p.is_dir() and (p / "summary.json").exists()):
        run = read_run(run_dir)
        run.update(enrich_run(run, model, profile))
        (run_dir / "advanced_analysis.json").write_text(json.dumps({
            "ml_advisory": run["ml_advisory"], "risk_assessment": run["risk_assessment"]
        }, indent=2), encoding="utf-8")
        records.append(run)
    fleet = {
        "total_runs": len(records),
        "normal_runs": sum(r["summary"]["terminal_state"] == "NORMAL" and not r["summary"]["detected_faults"] for r in records),
        "verified_recoveries": sum(r["summary"]["recovery_status"] == "VERIFIED" for r in records),
        "safe_mode_runs": sum(r["summary"]["terminal_state"] == "SAFE_MODE" for r in records),
        "faulted_runs": sum(bool(r["summary"]["detected_faults"]) for r in records),
    }
    report = {"fleet": fleet, "machine_learning_evaluation": ml_report,
              "risk_distribution": {level: sum(r["risk_assessment"]["level"] == level for r in records)
                                     for level in ("LOW", "MODERATE", "HIGH", "CRITICAL")},
              "records": [{"run_id": r["run_id"], "summary": r["summary"],
                           "ml_advisory": r["ml_advisory"], "risk_assessment": r["risk_assessment"]}
                          for r in records]}
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "advanced_system_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return records

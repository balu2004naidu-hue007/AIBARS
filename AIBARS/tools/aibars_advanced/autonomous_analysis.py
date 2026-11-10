"""Enrich completed C++ autonomous-session incidents with advisory AI and risk triage."""
from __future__ import annotations

import json
from pathlib import Path

from .analysis import enrich_run
from .ml_classifier import GaussianNaiveBayes


def enrich_autonomous_session(session_dir: Path, model: GaussianNaiveBayes, profile: dict) -> dict:
    summary_path = session_dir / "session_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Autonomous session summary is missing: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    events_path = session_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    analyses: list[dict] = []
    for episode in summary.get("episodes", []):
        number = int(episode["episode"])
        prefix = f"episode_{number:02d}"
        incident_path = session_dir / "episodes" / f"{prefix}_incident.json"
        if not incident_path.is_file():
            raise FileNotFoundError(f"Incident record is missing for autonomous episode {number}")
        incident = json.loads(incident_path.read_text(encoding="utf-8"))
        start_tick, end_tick = int(episode["start_tick"]), int(episode["end_tick"])
        episode_events = [event for event in events if start_tick <= int(event.get("tick", -1)) <= end_tick]
        detected = [fault.get("code", "UNKNOWN_FAULT") for fault in incident.get("faults", [])]
        run = {
            "summary": {
                "scenario": episode["scenario"],
                "terminal_state": episode["terminal_state"],
                "detected_faults": detected,
                "primary_cause": episode["primary_cause"],
                "recovery_action": incident.get("recommended_action", "UNKNOWN"),
                "recovery_status": episode["recovery_status"],
                "recovery_attempts": episode["recovery_attempts"],
                "verified_cycles": episode["verified_cycles"],
                "total_ticks": episode["end_tick"],
            },
            "incident": incident,
            "events": episode_events,
            "run_id": prefix,
        }
        run.update(enrich_run(run, model, profile))
        analyses.append({
            "episode": episode,
            "summary": run["summary"],
            "incident": incident,
            "events": episode_events,
            "ml_advisory": run["ml_advisory"],
            "risk_assessment": run["risk_assessment"],
            "device_id": summary.get("device_id", "AIBARS-AUTO-ECU-01"),
        })

    status_path = session_dir / "session_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    payload = {"status": status, "summary": summary, "events": events, "episode_analysis": analyses}
    (session_dir / "autonomous_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload

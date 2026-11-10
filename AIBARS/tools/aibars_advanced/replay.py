"""Incident replay primitives for black-box JSONL records."""
from __future__ import annotations
import json
from pathlib import Path


def load_timeline(run_dir: Path) -> list[dict]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"No black-box timeline found: {path}")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sequences = [event["sequence"] for event in events]
    if sequences != sorted(sequences):
        raise ValueError("Black-box sequence numbers are not monotonic")
    return events


def replay_summary(events: list[dict]) -> dict:
    return {
        "event_count": len(events),
        "first_sequence": events[0]["sequence"] if events else None,
        "last_sequence": events[-1]["sequence"] if events else None,
        "components": sorted({event["component"] for event in events}),
        "fault_events": sum(event["event"] == "fault_detected" for event in events),
        "recovery_attempts": sum(event["event"] == "recovery_attempt_started" for event in events),
        "recovery_verified": any(event["event"] == "recovery_verified" for event in events),
        "safe_mode_entered": any(event["event"] == "safe_mode_entered" for event in events),
    }

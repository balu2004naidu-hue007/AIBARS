#!/usr/bin/env python3
"""Validate and summarize a recorded AIBARS JSONL black-box timeline."""
from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aibars_advanced.replay import load_timeline, replay_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=pathlib.Path, help="Folder containing events.jsonl")
    parser.add_argument("--json", action="store_true", help="Print machine-readable replay summary")
    args = parser.parse_args()
    try:
        events = load_timeline(args.run_directory)
        summary = replay_summary(events)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("AIBARS BLACK-BOX INCIDENT REPLAY")
        print(f"Events             : {summary['event_count']}")
        print(f"Sequence range     : {summary['first_sequence']} .. {summary['last_sequence']}")
        print(f"Components         : {', '.join(summary['components']) or 'none'}")
        print(f"Fault detections   : {summary['fault_events']}")
        print(f"Recovery attempts  : {summary['recovery_attempts']}")
        print(f"Recovery verified  : {summary['recovery_verified']}")
        print(f"Safe mode entered  : {summary['safe_mode_entered']}")
        print("\nTimeline:")
        for event in events:
            print(f"  #{event['sequence']:>3} T+{event['tick']:<3} {event['component']:<18} {event['event']}: {event['detail']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run a seeded concurrent fault/recovery regression campaign."""
from __future__ import annotations
import argparse
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from aibars_advanced.configuration import load_profile
from aibars_advanced.stress import run_stress_campaign


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=48)
    parser.add_argument("--seed", type=int, default=20261109)
    args = parser.parse_args()
    binary_candidates = [ROOT / "build" / "aibars_sim", ROOT / "build" / "aibars_sim.exe",
                         ROOT / "build" / "Release" / "aibars_sim.exe"]
    binary = next((p for p in binary_candidates if p.is_file()), None)
    if binary is None:
        parser.error("Build simulator first with python tools/run_advanced.py")
    result = run_stress_campaign(binary, load_profile(), ROOT / "artifacts" / "stress_campaign_report.json",
                                 args.iterations, args.seed)
    print(f"PASS: {result['completed_runs']} concurrent fault/recovery runs; "
          f"{result['duration_seconds']} seconds; max retries={result['max_recovery_attempts_observed']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

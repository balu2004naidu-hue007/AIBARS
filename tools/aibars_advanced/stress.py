"""Seeded randomized multi-run regression and recovery stress campaign."""
from __future__ import annotations
import concurrent.futures
import json
import pathlib
import random
import subprocess
import tempfile
import time
from collections import Counter

SCENARIOS = ["nominal", "sensor_timeout", "sensor_stuck", "sensor_out_of_range",
             "communication_timeout", "task_hang", "secondary_task_hang", "multiple_task_hangs",
             "multiple_faults", "recovery_failure"]


def run_stress_campaign(binary: pathlib.Path, profile: dict, output_report: pathlib.Path,
                        iterations: int = 48, seed: int = 20261109) -> dict:
    if iterations < 1 or iterations > 10000:
        raise ValueError("iterations must be between 1 and 10000")
    rng = random.Random(seed)
    sequence = [rng.choice(SCENARIOS) for _ in range(iterations)]
    det, rec = profile["detection"], profile["recovery"]
    args = [
        "--temp-min-c", str(det["minimum_temperature_c"]), "--temp-max-c", str(det["maximum_temperature_c"]),
        "--voltage-min-v", str(det["minimum_voltage_v"]), "--voltage-max-v", str(det["maximum_voltage_v"]),
        "--current-min-a", str(det["minimum_current_a"]), "--current-max-a", str(det["maximum_current_a"]),
        "--sensor-timeout-ticks", str(det["sensor_timeout_ticks"]),
        "--communication-timeout-ticks", str(det["communication_timeout_ticks"]),
        "--stuck-samples", str(det["stuck_sample_count"]), "--task-stall-ticks", str(det["task_stall_ticks"]),
        "--recovery-attempts", str(rec["maximum_attempts"]),
        "--verify-cycles", str(rec["required_healthy_cycles"]),
        "--retry-backoff-ticks", str(rec["retry_backoff_ticks"]),
    ]
    started = time.perf_counter()
    outcomes: list[dict | None] = [None] * iterations
    failures: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="aibars_stress_") as temp_root:
        root = pathlib.Path(temp_root)
        def run_one(index: int, scenario: str) -> tuple[int, dict]:
            output = root / f"run_{index:04d}"
            proc = subprocess.run([str(binary), "--scenario", scenario, "--out", str(output), *args],
                                  capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(f"run {index} {scenario}: {proc.stderr or proc.stdout}")
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            return index, summary
        with concurrent.futures.ThreadPoolExecutor(max_workers=profile["fleet"]["workers"]) as pool:
            future_map = {pool.submit(run_one, i, scenario): i for i, scenario in enumerate(sequence)}
            for future in concurrent.futures.as_completed(future_map):
                try:
                    index, summary = future.result()
                    outcomes[index] = summary
                except Exception as exc:
                    failures.append({"run_index": future_map[future], "error": str(exc)})
    for index, summary in enumerate(outcomes):
        if summary is None:
            continue
        if summary["recovery_attempts"] > rec["maximum_attempts"]:
            failures.append({"run_index": index, "error": "recovery-attempt bound violated"})
        if summary["recovery_status"] == "VERIFIED":
            if summary["terminal_state"] != "NORMAL" or summary["verified_cycles"] != rec["required_healthy_cycles"]:
                failures.append({"run_index": index, "error": "verified recovery invariant violated"})
        if summary["terminal_state"] == "SAFE_MODE" and summary["recovery_status"] != "SAFE_MODE_ENTERED":
            failures.append({"run_index": index, "error": "safe-mode status invariant violated"})
        if summary["scenario"] in ("multiple_faults", "multiple_task_hangs") and summary["terminal_state"] != "SAFE_MODE":
            failures.append({"run_index": index, "error": "compound fault did not enter safe mode"})
        if summary["scenario"] == "recovery_failure" and summary["terminal_state"] != "SAFE_MODE":
            failures.append({"run_index": index, "error": "persistent fault did not enter safe mode"})
    duration = time.perf_counter() - started
    result = {
        "campaign": "seeded randomized concurrent regression",
        "seed": seed, "iterations": iterations, "workers": profile["fleet"]["workers"],
        "duration_seconds": round(duration, 4),
        "scenario_distribution": dict(Counter(sequence)),
        "terminal_states": dict(Counter(s["terminal_state"] for s in outcomes if s)),
        "recovery_statuses": dict(Counter(s["recovery_status"] for s in outcomes if s)),
        "max_recovery_attempts_observed": max((s["recovery_attempts"] for s in outcomes if s), default=0),
        "completed_runs": sum(s is not None for s in outcomes),
        "failures": failures,
        "passed": not failures and all(s is not None for s in outcomes),
        "scope_note": "All runs are local simulator processes with synthetic fault injection; not physical hardware stress testing.",
    }
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result["passed"]:
        raise RuntimeError(f"Stress campaign found {len(failures)} invariant failure(s)")
    return result

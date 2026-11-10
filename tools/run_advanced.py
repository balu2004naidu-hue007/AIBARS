#!/usr/bin/env python3
"""Build AIBARS, run concurrent fault campaigns, train advisory ML, assess risk and build dashboard."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from aibars_advanced.configuration import load_profile, simulator_args
from aibars_advanced.analysis import analyze_runs
from aibars_advanced.stress import run_stress_campaign
from aibars_advanced.ml_classifier import GaussianNaiveBayes
from aibars_advanced.autonomous_analysis import enrich_autonomous_session
from build_advanced_dashboard import build_dashboard

SCENARIOS = ["nominal", "sensor_timeout", "sensor_stuck", "sensor_out_of_range",
             "communication_timeout", "task_hang", "secondary_task_hang", "multiple_task_hangs",
             "multiple_faults", "recovery_failure"]


def binary_path() -> pathlib.Path:
    candidates = [ROOT / "build" / "aibars_sim", ROOT / "build" / "aibars_sim.exe",
                  ROOT / "build" / "Release" / "aibars_sim.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("AIBARS simulator was not built")


def run_one(binary: pathlib.Path, scenario: str, output: pathlib.Path, args: list[str], device: str) -> dict:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    command = [str(binary), "--scenario", scenario, "--out", str(output), *args]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Scenario {scenario} failed:\n{completed.stdout}\n{completed.stderr}")
    relative_output = str(output.relative_to(ROOT))
    portable_stdout = completed.stdout.replace(str(output), relative_output)
    portable_stderr = completed.stderr.replace(str(output), relative_output)
    return {"device_id": device, "scenario": scenario, "return_code": completed.returncode,
            "stdout": portable_stdout.strip(), "stderr": portable_stderr.strip(),
            "output_dir": relative_output}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=pathlib.Path, default=ROOT / "config" / "default_profile.json")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    profile = load_profile(args.profile)
    if not args.skip_build:
        subprocess.run(["cmake", "-S", str(ROOT), "-B", str(ROOT / "build"), "-DCMAKE_BUILD_TYPE=Release"], check=True)
        subprocess.run(["cmake", "--build", str(ROOT / "build"), "--config", "Release", "--parallel"], check=True)
    binary = binary_path()
    run_root = ROOT / "examples" / "advanced_runs"
    artifacts = ROOT / "artifacts"
    run_root.mkdir(parents=True, exist_ok=True)
    device_ids = profile["fleet"].get("device_ids", [])
    if not device_ids:
        device_ids = [f"SIM-DEVICE-{i+1:02d}" for i in range(profile["fleet"]["workers"])]
    jobs = [(scenario, run_root / scenario, device_ids[i % len(device_ids)]) for i, scenario in enumerate(SCENARIOS)]
    print(f"Launching {len(jobs)} fault campaigns across {min(profile['fleet']['workers'], len(jobs))} concurrent workers...")
    fleet_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=profile["fleet"]["workers"]) as pool:
        futures = [pool.submit(run_one, binary, scenario, path, simulator_args(profile), device)
                   for scenario, path, device in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            fleet_results.append(result)
            print(f"[PASS] {result['device_id']} :: {result['scenario']}")
    fleet_results.sort(key=lambda item: SCENARIOS.index(item["scenario"]))
    (artifacts / "fleet_manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (artifacts / "fleet_manifest.json").write_text(json.dumps({
        "execution_mode": "concurrent laptop simulation",
        "workers": profile["fleet"]["workers"], "campaigns": fleet_results
    }, indent=2), encoding="utf-8")
    stress_result = run_stress_campaign(binary, profile, artifacts / "stress_campaign_report.json", iterations=48)
    print(f"[PASS] randomized stress campaign: {stress_result['completed_runs']} runs in {stress_result['duration_seconds']} s")
    records = analyze_runs(run_root, artifacts, profile)
    device_map = {item["scenario"]: item["device_id"] for item in fleet_results}
    for record in records:
        record["device_id"] = device_map.get(record["summary"]["scenario"], "SIM-DEVICE")
    # Generate a saved autonomous-session demonstration using the same persistent
    # C++ simulator mode exposed by the live dashboard. Faults are selected
    # internally by the seeded supervisor; no scenario is manually selected.
    autonomous_demo_dir = ROOT / "examples" / "autonomous_demo"
    if autonomous_demo_dir.exists():
        shutil.rmtree(autonomous_demo_dir)
    autonomous_demo_dir.mkdir(parents=True, exist_ok=True)
    auto_command = [str(binary), "--autonomous", "--out", str(autonomous_demo_dir),
                    "--session-cycles", "80", "--max-incidents", "3",
                    "--fault-interval-min", "20", "--fault-interval-max", "25",
                    "--seed", "20261110", "--tick-delay-ms", "100",
                    "--critical-fault-percent", "0", *simulator_args(profile)]
    subprocess.run(auto_command, check=True, text=True)
    model = GaussianNaiveBayes.from_dict(json.loads(
        (artifacts / "fault_classifier_model.json").read_text(encoding="utf-8")))
    autonomous_demo = enrich_autonomous_session(autonomous_demo_dir, model, profile)

    dashboard_path = ROOT / "examples" / "dashboard.html"
    build_dashboard(records, dashboard_path, profile, autonomous_demo)
    print(f"\nCompleted {len(records)} scenario campaigns and one autonomous session demo.")
    print(f"Dashboard: {dashboard_path}")
    print(f"Analysis report: {artifacts / 'advanced_system_report.json'}")
    print("Note: all devices and fault signals are simulated; ML evaluation uses generated synthetic data.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

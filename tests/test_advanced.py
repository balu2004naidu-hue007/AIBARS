from __future__ import annotations
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def simulator_binary() -> pathlib.Path:
    configured = os.environ.get("AIBARS_BINARY")
    if configured:
        return pathlib.Path(configured).resolve()
    candidates = [ROOT / "build" / "aibars_sim", ROOT / "build" / "aibars_sim.exe",
                  ROOT / "build" / "Release" / "aibars_sim.exe", ROOT / "build" / "Release" / "aibars_sim"]
    return next((path for path in candidates if path.is_file()), candidates[0])
from aibars_advanced.configuration import load_profile, simulator_args
from aibars_advanced.ml_classifier import GaussianNaiveBayes, train_and_evaluate, extract_features
from aibars_advanced.risk_assessment import assess_risk
from aibars_advanced.fleet import run_concurrently
from aibars_advanced.replay import replay_summary
from aibars_advanced.stress import run_stress_campaign
from launch_dashboard import normalize_autonomous_timing
import subprocess
import socket
import time
import urllib.request


class AdvancedAibarsTests(unittest.TestCase):
    def test_ml_training_has_held_out_evaluation_and_model(self):
        model, report = train_and_evaluate(samples_per_class=80)
        self.assertEqual(report["training_samples"] + report["test_samples"], report["samples_total"])
        self.assertGreater(report["accuracy"], 0.85)
        self.assertEqual(len(model.classes), 6)
        self.assertIn("synthetic", report["dataset"])

    def test_model_round_trip_preserves_predictions(self):
        model, _ = train_and_evaluate(samples_per_class=60)
        restored = GaussianNaiveBayes.from_dict(model.to_dict())
        vector = [6, 0, 0, 1, 20, 0, 0, 0, 0, 0]
        self.assertEqual(model.predict(vector), restored.predict(vector))

    def test_model_rejects_invalid_feature_vectors_and_model_schema(self):
        model, _ = train_and_evaluate(samples_per_class=40)
        with self.assertRaises(ValueError):
            model.predict([1.0, 2.0])
        payload = model.to_dict()
        payload["features"] = ["unexpected"]
        with self.assertRaises(ValueError):
            GaussianNaiveBayes.from_dict(payload)

    def test_feature_extraction_reads_black_box_age_and_stall_evidence(self):
        run = {
            "summary": {"detected_faults": ["SENSOR_TIMEOUT", "TASK_HANG"]},
            "events": [
                {"detail": "temperature freshness=stale, age=4 ticks, threshold=3 ticks"},
                {"detail": "communication status=lost, heartbeat age=5 ticks, threshold=3 ticks"},
                {"detail": "task=PRIMARY_CONTROL_LOOP progress stalled for 6 ticks"},
                {"detail": "task=SECONDARY_TELEMETRY_TASK progress stalled for 2 ticks"},
                {"detail": "temperature=150.000000 C, voltage=24.000000 V, current=4.000000 A"},
            ],
        }
        features = extract_features(run, load_profile())
        self.assertEqual(features[0], 4.0)
        self.assertEqual(features[1], 1.0)
        self.assertEqual(features[2], 5.0)
        self.assertEqual(features[3], 6.0)
        self.assertEqual(features[4], 25.0)
        self.assertEqual(features[9], 2.0)

    def test_profile_rejects_single_sample_stuck_threshold_and_duplicate_devices(self):
        profile = load_profile()
        with tempfile.TemporaryDirectory(prefix="aibars_invalid_profile_") as temp:
            path = pathlib.Path(temp) / "profile.json"
            invalid = json.loads(json.dumps(profile))
            invalid["detection"]["stuck_sample_count"] = 1
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(path)
            invalid = json.loads(json.dumps(profile))
            invalid["fleet"]["device_ids"] = ["DUPLICATE", "DUPLICATE"]
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(path)

    def test_profile_validates_and_maps_all_settings(self):
        profile = load_profile()
        args = simulator_args(profile)
        self.assertIn("--sensor-timeout-ticks", args)
        self.assertIn("--recovery-attempts", args)
        self.assertEqual(profile["recovery"]["required_healthy_cycles"], 3)

    def test_risk_assessment_prioritizes_compound_critical_faults(self):
        profile = load_profile()
        risk = assess_risk("COMPOUND_FAULT", "CRITICAL", 0.99, profile, fault_count=2)
        self.assertEqual(risk["level"], "CRITICAL")
        self.assertGreaterEqual(risk["score"], 75)

    def test_risk_assessment_uses_configured_impact_for_each_diagnosis_cause(self):
        profile = load_profile()
        mapping = {
            "SENSOR_DATA_TIMEOUT": "SENSOR_TIMEOUT",
            "SENSOR_STUCK_AT": "SENSOR_STUCK",
            "SENSOR_VALUE_OUT_OF_RANGE": "SENSOR_OUT_OF_RANGE",
            "COMMUNICATION_HEARTBEAT_TIMEOUT": "COMMUNICATION_TIMEOUT",
            "TASK_PROGRESS_FAILURE": "TASK_HANG",
            "NO_FAULT_DETECTED": "NORMAL",
        }
        for cause, category in mapping.items():
            with self.subTest(cause=cause):
                result = assess_risk(cause, "HIGH" if cause != "NO_FAULT_DETECTED" else "LOW", 0.9, profile)
                self.assertEqual(result["impact_factor"], profile["risk"]["impact"][category])

    def test_concurrent_fleet_runner_preserves_input_order(self):
        def fake(device: str, scenario: str) -> dict:
            return {"device": device, "scenario": scenario}
        results = run_concurrently([("D1", "nominal"), ("D2", "task_hang"), ("D3", "sensor_timeout")], 3, fake)
        self.assertEqual([r["device"] for r in results], ["D1", "D2", "D3"])


    def test_cli_threshold_override_is_applied_to_cpp_detector(self):
        binary = simulator_binary()
        self.assertTrue(binary.exists())
        with tempfile.TemporaryDirectory(prefix="aibars_custom_profile_") as temp:
            output = pathlib.Path(temp) / "run"
            proc = subprocess.run([str(binary), "--scenario", "nominal", "--out", str(output),
                                   "--temp-max-c", "30"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["detected_faults"], ["SENSOR_OUT_OF_RANGE"])


    def test_large_valid_timeout_threshold_is_honoured(self):
        binary = simulator_binary()
        with tempfile.TemporaryDirectory(prefix="aibars_large_timeout_") as temp:
            output = pathlib.Path(temp) / "run"
            proc = subprocess.run([str(binary), "--scenario", "sensor_timeout", "--out", str(output),
                                   "--sensor-timeout-ticks", "40"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["detected_faults"], ["SENSOR_TIMEOUT"])
            self.assertGreaterEqual(summary["total_ticks"], 47)

    def test_cli_rejects_non_finite_threshold_and_negative_tick_count(self):
        binary = simulator_binary()
        with tempfile.TemporaryDirectory(prefix="aibars_invalid_cli_") as temp:
            out = pathlib.Path(temp) / "out_nan"
            nan_result = subprocess.run([str(binary), "--out", str(out), "--temp-max-c", "nan"],
                                        capture_output=True, text=True)
            self.assertNotEqual(nan_result.returncode, 0)
            negative_result = subprocess.run([str(binary), "--out", str(out), "--sensor-timeout-ticks", "-1"],
                                             capture_output=True, text=True)
            self.assertNotEqual(negative_result.returncode, 0)

    def test_local_dashboard_serves_page_and_streams_simulator_events(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, str(ROOT / "tools" / "launch_dashboard.py"),
                                   "--host", "127.0.0.1", "--port", str(port)],
                                  cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.time() + 8
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(base + "/api/health", timeout=1) as response:
                        self.assertEqual(response.status, 200)
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("AIBARS dashboard server did not start")
            with urllib.request.urlopen(base + "/", timeout=3) as response:
                page = response.read()
                self.assertIn(b"AIBARS Operations Center", page)
                self.assertIn(b"Fixed interval", page)
                self.assertIn(b"Random interval", page)
                self.assertIn(b"Next fault schedule", page)
            invalid_request = urllib.request.Request(base + "/api/start", data=b'{"scenario":"../../bad"}',
                                                     headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
                                                     method="POST")
            try:
                urllib.request.urlopen(invalid_request, timeout=3)
                self.fail("Cross-origin scenario execution should be rejected")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 403)
            # Stateful execution is POST-only; GET must never start a process.
            try:
                urllib.request.urlopen(base + "/api/start?scenario=task_hang", timeout=3)
                self.fail("GET /api/start should not start a simulator")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 405)
            request = urllib.request.Request(base + "/api/start", data=json.dumps({"scenario": "task_hang"}).encode("utf-8"),
                                             headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=3) as response:
                run_id = json.loads(response.read())["run_id"]
            observed = 0
            deadline = time.time() + 12
            finished = None
            while time.time() < deadline:
                with urllib.request.urlopen(base + "/api/status?run_id=" + run_id, timeout=3) as response:
                    state = json.loads(response.read())
                observed = max(observed, state["event_count"])
                if state["done"]:
                    finished = state
                    break
                time.sleep(0.15)
            self.assertIsNotNone(finished, "live simulator did not finish")
            self.assertGreater(observed, 0, "dashboard did not expose live event records")
            self.assertEqual(finished["result"]["summary"]["recovery_status"], "VERIFIED")
            self.assertEqual(finished["result"]["ml_advisory"]["prediction"], "TASK_HANG")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


    def test_seeded_randomized_stress_campaign_preserves_recovery_invariants(self):
        binary = simulator_binary()
        with tempfile.TemporaryDirectory(prefix="aibars_stress_report_") as temp:
            report = pathlib.Path(temp) / "stress.json"
            result = run_stress_campaign(binary, load_profile(), report, iterations=12, seed=17)
            self.assertTrue(result["passed"])
            self.assertEqual(result["completed_runs"], 12)
            self.assertEqual(result["failures"], [])

    def test_replay_summary_counts_fault_and_recovery_events(self):
        events = [
            {"sequence": 1, "component": "supervisor", "event": "run_started"},
            {"sequence": 2, "component": "fault_detector", "event": "fault_detected"},
            {"sequence": 3, "component": "recovery", "event": "recovery_attempt_started"},
            {"sequence": 4, "component": "recovery", "event": "recovery_verified"},
        ]
        result = replay_summary(events)
        self.assertEqual(result["fault_events"], 1)
        self.assertEqual(result["recovery_attempts"], 1)
        self.assertTrue(result["recovery_verified"])


    def test_seconds_based_fixed_and_random_fault_scheduling_conversion(self):
        fixed = normalize_autonomous_timing({
            "interval_mode": "fixed", "interval_seconds": 2.0, "tick_delay_ms": 100
        })
        self.assertEqual(fixed["fault_interval_min"], 20)
        self.assertEqual(fixed["fault_interval_max"], 20)
        self.assertEqual(fixed["interval_mode"], "fixed")
        self.assertAlmostEqual(fixed["effective_min_seconds"], 2.0)

        random = normalize_autonomous_timing({
            "interval_mode": "random", "interval_min_seconds": 2.0,
            "interval_max_seconds": 5.0, "tick_delay_ms": 100
        })
        self.assertEqual(random["fault_interval_min"], 20)
        self.assertEqual(random["fault_interval_max"], 50)
        self.assertAlmostEqual(random["effective_min_seconds"], 2.0)
        self.assertAlmostEqual(random["effective_max_seconds"], 5.0)

    def test_seconds_scheduler_rounds_up_and_rejects_invalid_intervals(self):
        rounded = normalize_autonomous_timing({
            "interval_mode": "fixed", "interval_seconds": 2.01, "tick_delay_ms": 100
        })
        self.assertEqual(rounded["fault_interval_min"], 21)
        self.assertAlmostEqual(rounded["effective_min_seconds"], 2.1)
        with self.assertRaises(ValueError):
            normalize_autonomous_timing({
                "interval_mode": "random", "interval_min_seconds": 5.0,
                "interval_max_seconds": 2.0, "tick_delay_ms": 100
            })
        with self.assertRaises(ValueError):
            normalize_autonomous_timing({
                "interval_mode": "fixed", "interval_seconds": 2.0, "tick_delay_ms": 0
            })
        legacy = normalize_autonomous_timing({
            "fault_interval_min": 4, "fault_interval_max": 8, "tick_delay_ms": 0
        })
        self.assertEqual(legacy["fault_interval_min"], 4)
        self.assertEqual(legacy["fault_interval_max"], 8)
        self.assertEqual(legacy["timing_basis"], "legacy_cycles")

    def test_dashboard_exposes_autonomous_session_api_and_enriches_incidents(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, str(ROOT / "tools" / "launch_dashboard.py"),
                                   "--host", "127.0.0.1", "--port", str(port)],
                                  cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.time() + 8
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(base + "/api/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("AIBARS dashboard server did not start")
            body = json.dumps({"session_cycles": 30, "max_incidents": 1,
                               "interval_mode": "fixed", "interval_seconds": 0.4,
                               "tick_delay_ms": 100, "seed": 42}).encode("utf-8")
            request = urllib.request.Request(base + "/api/autonomous/start", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=3) as response:
                started = json.loads(response.read())
            self.assertTrue(started["started"])
            self.assertEqual(started["mode"], "AUTONOMOUS")
            self.assertEqual(started["config"]["interval_mode"], "fixed")
            self.assertEqual(started["config"]["fault_interval_min"], 4)
            self.assertEqual(started["config"]["fault_interval_max"], 4)
            self.assertAlmostEqual(started["config"]["effective_min_seconds"], 0.4)
            session_id = started["session_id"]
            completed = None
            deadline = time.time() + 20
            while time.time() < deadline:
                with urllib.request.urlopen(base + "/api/autonomous/status?session_id=" + session_id, timeout=3) as response:
                    snapshot = json.loads(response.read())
                if snapshot["done"]:
                    completed = snapshot
                    break
                time.sleep(0.1)
            self.assertIsNotNone(completed, "autonomous session did not finish")
            self.assertEqual(completed["summary"]["incidents"], 1)
            self.assertIn("interval_mode", completed["status"])
            self.assertIn("cycles_until_next_fault", completed["status"])
            self.assertIn("next_fault_in_seconds", completed["status"])
            self.assertEqual(len(completed["episode_analysis"]), 1)
            self.assertIn("prediction", completed["episode_analysis"][0]["ml_advisory"])
            self.assertIn("level", completed["episode_analysis"][0]["risk_assessment"])
            self.assertTrue(any(e["event"] == "monitoring_resumed" for e in completed["events"]))
            scheduled = next(e for e in completed["events"] if e["event"] == "fault_scheduled")
            self.assertIn("healthy_interval_cycles=4", scheduled["detail"])
            try:
                urllib.request.urlopen(base + "/api/autonomous/start", timeout=2)
                self.fail("GET should not start an autonomous session")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 405)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()



if __name__ == "__main__":
    unittest.main(verbosity=2)

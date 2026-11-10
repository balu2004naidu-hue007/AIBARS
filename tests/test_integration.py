import json
import os
import pathlib
import subprocess
import tempfile
import unittest


BINARY = pathlib.Path(os.environ.get("AIBARS_BINARY", "build/aibars_sim")).resolve()


class AibarsScenarioIntegrationTests(unittest.TestCase):
    def run_scenario(self, scenario: str):
        self.assertTrue(BINARY.exists(), f"AIBARS executable not found: {BINARY}")
        output = pathlib.Path(tempfile.mkdtemp(prefix=f"aibars_{scenario}_"))
        completed = subprocess.run(
            [str(BINARY), "--scenario", scenario, "--out", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (output / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        return output, summary, events

    def test_all_scenarios_have_expected_outcomes_and_valid_black_box(self):
        expected = {
            "nominal": ("NORMAL", "NOT_REQUIRED", []),
            "sensor_timeout": ("NORMAL", "VERIFIED", ["SENSOR_TIMEOUT"]),
            "sensor_stuck": ("NORMAL", "VERIFIED", ["SENSOR_STUCK"]),
            "sensor_out_of_range": ("NORMAL", "VERIFIED", ["SENSOR_OUT_OF_RANGE"]),
            "communication_timeout": ("NORMAL", "VERIFIED", ["COMMUNICATION_TIMEOUT"]),
            "task_hang": ("NORMAL", "VERIFIED", ["TASK_HANG"]),
            "secondary_task_hang": ("NORMAL", "VERIFIED", ["TASK_HANG"]),
            "multiple_task_hangs": ("SAFE_MODE", "SAFE_MODE_ENTERED", ["TASK_HANG", "TASK_HANG"]),
            "multiple_faults": ("SAFE_MODE", "SAFE_MODE_ENTERED", ["SENSOR_OUT_OF_RANGE", "COMMUNICATION_TIMEOUT"]),
            "recovery_failure": ("SAFE_MODE", "SAFE_MODE_ENTERED", ["TASK_HANG"]),
        }
        for scenario, (state, recovery, faults) in expected.items():
            with self.subTest(scenario=scenario):
                output, summary, events = self.run_scenario(scenario)
                self.assertEqual(summary["terminal_state"], state)
                self.assertEqual(summary["recovery_status"], recovery)
                self.assertEqual(summary["detected_faults"], faults)
                self.assertGreater(len(events), 0)
                sequences = [event["sequence"] for event in events]
                self.assertEqual(sequences, sorted(sequences))
                self.assertTrue((output / "events.jsonl").exists())
                if faults:
                    incident = json.loads((output / "incident.json").read_text(encoding="utf-8"))
                    self.assertEqual(incident["recovery_status"], recovery)
                    self.assertTrue(incident["rationale"])
                    self.assertTrue(incident["recovery_explanation"])

    def test_recovery_failure_is_bounded(self):
        _, summary, _ = self.run_scenario("recovery_failure")
        self.assertEqual(summary["recovery_attempts"], 2)
        _, _, events = self.run_scenario("recovery_failure")
        self.assertTrue(any(e["event"] == "retry_backoff_tick" for e in events))

    def test_recoverable_fault_requires_three_verification_cycles(self):
        _, summary, _ = self.run_scenario("task_hang")
        self.assertEqual(summary["verified_cycles"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class AibarsAutonomousSessionTests(unittest.TestCase):
    def test_autonomous_mode_schedules_faults_and_resumes_same_logical_device(self):
        self.assertTrue(BINARY.exists(), f"AIBARS executable not found: {BINARY}")
        output = pathlib.Path(tempfile.mkdtemp(prefix="aibars_autonomous_session_"))
        completed = subprocess.run(
            [str(BINARY), "--autonomous", "--out", str(output),
             "--session-cycles", "50", "--max-incidents", "3",
             "--fault-interval-min", "5", "--fault-interval-max", "5",
             "--seed", "42", "--tick-delay-ms", "0"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        summary = json.loads((output / "session_summary.json").read_text(encoding="utf-8"))
        status = json.loads((output / "session_status.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in (output / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(summary["session_state"], "COMPLETED")
        self.assertEqual(summary["device_id"], "AIBARS-AUTO-ECU-01")
        self.assertEqual(summary["incidents"], 3)
        self.assertEqual(summary["verified_recoveries"], 3)
        self.assertEqual(summary["safe_mode_entries"], 0)
        self.assertEqual(len(summary["episodes"]), 3)
        self.assertEqual(status["global_tick"], summary["global_ticks"])
        self.assertEqual([ep["recovery_status"] for ep in summary["episodes"]], ["VERIFIED"] * 3)
        names = [event["event"] for event in events]
        self.assertEqual(names.count("fault_scheduled"), 3)
        self.assertEqual(names.count("monitoring_resumed"), 3)
        self.assertIn("normal_sample_observed", names)
        ticks = [event["tick"] for event in events]
        self.assertEqual(ticks, sorted(ticks))
        self.assertTrue((output / "episodes" / "episode_01_incident.json").exists())

    def test_autonomous_critical_fault_enters_safe_mode_and_stops_session(self):
        self.assertTrue(BINARY.exists(), f"AIBARS executable not found: {BINARY}")
        output = pathlib.Path(tempfile.mkdtemp(prefix="aibars_autonomous_safe_mode_"))
        completed = subprocess.run(
            [str(BINARY), "--autonomous", "--out", str(output),
             "--session-cycles", "30", "--max-incidents", "3",
             "--fault-interval-min", "4", "--fault-interval-max", "4",
             "--seed", "42", "--critical-fault-percent", "100", "--tick-delay-ms", "0"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        summary = json.loads((output / "session_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["session_state"], "SAFE_MODE")
        self.assertEqual(summary["safe_mode_entries"], 1)
        self.assertEqual(summary["incidents"], 1)
        self.assertLess(summary["session_cycles"], 30)

    def test_autonomous_stop_file_stops_cleanly(self):
        self.assertTrue(BINARY.exists(), f"AIBARS executable not found: {BINARY}")
        output = pathlib.Path(tempfile.mkdtemp(prefix="aibars_autonomous_stop_"))
        stop_file = output / "stop.request"
        stop_file.touch()
        completed = subprocess.run(
            [str(BINARY), "--autonomous", "--out", str(output / "run"),
             "--session-cycles", "40", "--max-incidents", "2",
             "--fault-interval-min", "5", "--fault-interval-max", "7",
             "--seed", "5", "--stop-file", str(stop_file), "--tick-delay-ms", "0"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        summary = json.loads(((output / "run") / "session_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["session_state"], "STOPPED")
        self.assertEqual(summary["incidents"], 0)

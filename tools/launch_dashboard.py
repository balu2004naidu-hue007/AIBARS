#!/usr/bin/env python3
"""Start AIBARS' local interactive dashboard with live simulator progress polling."""
from __future__ import annotations
import argparse
import json
import math
import pathlib
import subprocess
import sys
import threading
import time
import shutil
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from aibars_advanced.configuration import load_profile, simulator_args
from aibars_advanced.analysis import read_run, enrich_run
from aibars_advanced.ml_classifier import GaussianNaiveBayes, save_model_and_report
from aibars_advanced.autonomous_analysis import enrich_autonomous_session

ACTIVE_RUNS: dict[str, dict] = {}
ACTIVE_AUTONOMOUS: dict[str, dict] = {}
RUN_LOCK = threading.Lock()
MAX_ACTIVE_RUNS = 4
MAX_RETAINED_RUNS = 24
MAX_RUN_SECONDS = 60
PROFILE_PATH = ROOT / "config" / "default_profile.json"


def normalize_autonomous_timing(payload: dict) -> dict:
    """Convert user-facing seconds into simulator monitoring cycles.

    Intervals are healthy monitoring time after a recovery completes. Detection and
    recovery duration is additional elapsed time and is intentionally not hidden.
    Legacy cycle-based requests remain accepted for existing automated tests.
    """
    def bounded_int(key: str, default: int, minimum: int, maximum: int) -> int:
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
        return value

    tick_delay_ms = bounded_int("tick_delay_ms", 100, 0, 1000)
    mode = payload.get("interval_mode")
    if mode is None:
        # Backward-compatible interface used by v2.2.0 clients and tests.
        minimum_cycles = bounded_int("fault_interval_min", 8, 4, 10000)
        maximum_cycles = bounded_int("fault_interval_max", 16, minimum_cycles, 10000)
        mode = "fixed" if minimum_cycles == maximum_cycles else "random"
        if tick_delay_ms > 0:
            minimum_seconds = minimum_cycles * tick_delay_ms / 1000.0
            maximum_seconds = maximum_cycles * tick_delay_ms / 1000.0
        else:
            minimum_seconds = maximum_seconds = None
        return {
            "interval_mode": mode,
            "fault_interval_min": minimum_cycles,
            "fault_interval_max": maximum_cycles,
            "tick_delay_ms": tick_delay_ms,
            "requested_min_seconds": minimum_seconds,
            "requested_max_seconds": maximum_seconds,
            "effective_min_seconds": minimum_seconds,
            "effective_max_seconds": maximum_seconds,
            "timing_basis": "legacy_cycles" if tick_delay_ms == 0 else "monitoring_seconds",
        }

    if mode not in ("fixed", "random"):
        raise ValueError("interval_mode must be 'fixed' or 'random'")
    if tick_delay_ms < 20:
        raise ValueError("tick_delay_ms must be between 20 and 1000 for seconds-based scheduling")

    def bounded_seconds(key: str, default: float) -> float:
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number of seconds")
        value = float(value)
        if not 0.4 <= value <= 120.0:
            raise ValueError(f"{key} must be between 0.4 and 120 seconds")
        return value

    if mode == "fixed":
        fixed_seconds = bounded_seconds("interval_seconds", 2.0)
        requested_min = requested_max = fixed_seconds
    else:
        requested_min = bounded_seconds("interval_min_seconds", 2.0)
        requested_max = bounded_seconds("interval_max_seconds", 5.0)
        if requested_max < requested_min:
            raise ValueError("interval_max_seconds must be greater than or equal to interval_min_seconds")

    # The scheduler counts healthy monitoring cycles. Round up so it never injects
    # the next fault earlier than the requested minimum healthy-operation interval.
    minimum_cycles = max(4, math.ceil(requested_min * 1000.0 / tick_delay_ms))
    maximum_cycles = max(4, math.ceil(requested_max * 1000.0 / tick_delay_ms))
    if maximum_cycles > 10000:
        raise ValueError("Selected interval is too long for the simulator's 10000-cycle scheduling limit")
    if mode == "fixed":
        maximum_cycles = minimum_cycles
    return {
        "interval_mode": mode,
        "fault_interval_min": minimum_cycles,
        "fault_interval_max": maximum_cycles,
        "tick_delay_ms": tick_delay_ms,
        "requested_min_seconds": requested_min,
        "requested_max_seconds": requested_max,
        "effective_min_seconds": minimum_cycles * tick_delay_ms / 1000.0,
        "effective_max_seconds": maximum_cycles * tick_delay_ms / 1000.0,
        "timing_basis": "healthy_monitoring_time_after_recovery",
    }
ALLOWED = {"nominal", "sensor_timeout", "sensor_stuck", "sensor_out_of_range",
           "communication_timeout", "task_hang", "secondary_task_hang", "multiple_task_hangs",
           "multiple_faults", "recovery_failure"}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AIBARS-Dashboard/2.3"

    def log_message(self, fmt: str, *args) -> None:
        print("[AIBARS WEB] " + fmt % args)

    def _json(self, value: dict, status: int = 200) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _binary_and_profile(self):
        profile = load_profile(PROFILE_PATH)
        candidates = [ROOT / "build" / "aibars_sim", ROOT / "build" / "aibars_sim.exe",
                      ROOT / "build" / "Release" / "aibars_sim.exe"]
        binary = next((p for p in candidates if p.is_file()), None)
        if binary is None:
            raise FileNotFoundError("Simulator not built. Run python tools/run_advanced.py first.")
        return binary, profile

    def _load_enriched_run(self, output: pathlib.Path) -> dict:
        artifacts = ROOT / "artifacts"
        model_path = artifacts / "fault_classifier_model.json"
        if not model_path.exists():
            save_model_and_report(artifacts)
        profile = load_profile(PROFILE_PATH)
        try:
            model_payload = json.loads(model_path.read_text(encoding="utf-8"))
            model = GaussianNaiveBayes.from_dict(model_payload)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            # Regenerate stale/corrupt model artifacts when project feature schema changes.
            save_model_and_report(artifacts)
            model = GaussianNaiveBayes.from_dict(json.loads(model_path.read_text(encoding="utf-8")))
        run = read_run(output)
        run.update(enrich_run(run, model, profile))
        run["device_id"] = "LIVE-SIMULATOR"
        return run

    def _load_enriched_autonomous_session(self, output: pathlib.Path) -> dict:
        artifacts = ROOT / "artifacts"
        model_path = artifacts / "fault_classifier_model.json"
        if not model_path.exists():
            save_model_and_report(artifacts)
        try:
            model = GaussianNaiveBayes.from_dict(json.loads(model_path.read_text(encoding="utf-8")))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            save_model_and_report(artifacts)
            model = GaussianNaiveBayes.from_dict(json.loads(model_path.read_text(encoding="utf-8")))
        return enrich_autonomous_session(output, model, load_profile(PROFILE_PATH))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path in ("/", "/index.html"):
            path = ROOT / "examples" / "dashboard.html"
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/health":
            profile = load_profile(PROFILE_PATH)
            return self._json({"status": "ok", "service": "AIBARS local dashboard",
                               "simulation_only": True, "profile_name": profile.get("profile_name", "AIBARS profile")})
        if parsed.path == "/api/start":
            return self._json({"error": "Scenario execution uses POST /api/start; GET requests do not start processes."}, 405)
        if parsed.path == "/api/autonomous/status":
            session_id = query.get("session_id", [""])[0]
            with RUN_LOCK:
                session = ACTIVE_AUTONOMOUS.get(session_id)
            if not session:
                return self._json({"error": "Unknown or expired autonomous session_id"}, 404)
            process: subprocess.Popen = session["process"]
            if process.poll() is None and time.monotonic() - session["started_at"] > 600:
                stop_file: pathlib.Path = session["stop_file"]
                stop_file.touch(exist_ok=True)
            output: pathlib.Path = session["output"]
            status_path = output / "session_status.json"
            summary_path = output / "session_summary.json"
            events_path = output / "events.jsonl"
            status = {}
            if status_path.exists():
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    status = {}
            events = []
            if events_path.exists():
                for line in events_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            done = process.poll() is not None
            response = {"session_id": session_id, "done": done, "status": status,
                        "event_count": len(events), "events": events[-600:]}
            if summary_path.exists():
                try:
                    response["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            if done and not session.get("finalized"):
                if not session["console"].closed:
                    session["console"].close()
                session["finalized"] = True
                if process.returncode == 0 and summary_path.exists():
                    try:
                        enriched = self._load_enriched_autonomous_session(output)
                        response.update(enriched)
                        session["enriched"] = enriched
                    except Exception as exc:
                        response["error"] = f"Unable to enrich autonomous session: {exc}"
                elif process.returncode != 0:
                    log = output / "session_console.log"
                    response["error"] = log.read_text(encoding="utf-8", errors="replace") if log.exists() else "Autonomous simulator exited unsuccessfully."
            elif done and session.get("enriched"):
                response.update(session["enriched"])
            return self._json(response)
        if parsed.path == "/api/autonomous/start":
            return self._json({"error": "Autonomous session execution uses POST /api/autonomous/start."}, 405)
        if parsed.path == "/api/autonomous/stop":
            return self._json({"error": "Autonomous session stop uses POST /api/autonomous/stop."}, 405)
        if parsed.path == "/api/status":
            run_id = query.get("run_id", [""])[0]
            with RUN_LOCK:
                run = ACTIVE_RUNS.get(run_id)
            if not run:
                return self._json({"error": "Unknown or expired run_id"}, 404)
            output: pathlib.Path = run["output"]
            process: subprocess.Popen = run["process"]
            if process.poll() is None and time.monotonic() - run["started_at"] > MAX_RUN_SECONDS:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            events_path = output / "events.jsonl"
            events = []
            if events_path.exists():
                for line in events_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            # A partially written final line is skipped and retried on the next poll.
                            continue
            done = process.poll() is not None
            response = {"run_id": run_id, "scenario": run["scenario"], "done": done,
                        "event_count": len(events), "events": events}
            if done:
                if not run.get("finalized"):
                    run["log_stream"].close()
                    run["finalized"] = True
                    run["completed_at"] = time.time()
                if process.returncode != 0:
                    log = output / "simulator_console.log"
                    response["error"] = log.read_text(encoding="utf-8", errors="replace") if log.exists() else "Simulator exited unsuccessfully."
                else:
                    try:
                        response["result"] = self._load_enriched_run(output)
                    except Exception as exc:
                        response["error"] = f"Unable to load simulator result: {exc}"
                        return self._json(response, 500)
            return self._json(response)
        return self._json({"error": "Not found"}, 404)


    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/start", "/api/autonomous/start", "/api/autonomous/stop"):
            return self._json({"error": "Not found"}, 404)

        origin = self.headers.get("Origin")
        if origin:
            allowed_origins = {
                f"http://127.0.0.1:{self.server.server_address[1]}",
                f"http://localhost:{self.server.server_address[1]}",
                f"http://[::1]:{self.server.server_address[1]}",
            }
            if origin not in allowed_origins:
                return self._json({"error": "Cross-origin scenario execution is not allowed."}, 403)

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 0 or content_length > 4096:
                return self._json({"error": "Request body must be between 0 and 4096 bytes."}, 413)
            raw = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return self._json({"error": "Request body must be a JSON object."}, 400)

            if parsed.path == "/api/autonomous/stop":
                session_id = payload.get("session_id", "")
                with RUN_LOCK:
                    session = ACTIVE_AUTONOMOUS.get(session_id)
                if not session:
                    return self._json({"error": "Unknown autonomous session_id"}, 404)
                stop_file = session["stop_file"]
                stop_file.touch(exist_ok=True)
                return self._json({"session_id": session_id, "stop_requested": True})

            if parsed.path == "/api/autonomous/start":
                binary, profile = self._binary_and_profile()
                def bounded_int(key: str, default: int, minimum: int, maximum: int) -> int:
                    value = payload.get(key, default)
                    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                        raise ValueError(f"{key} must be an integer between {minimum} and {maximum}")
                    return value
                session_cycles = bounded_int("session_cycles", 120, 10, 10000)
                max_incidents = bounded_int("max_incidents", 3, 1, 20)
                timing = normalize_autonomous_timing(payload)
                interval_min = timing["fault_interval_min"]
                interval_max = timing["fault_interval_max"]
                tick_delay_ms = timing["tick_delay_ms"]
                seed = bounded_int("seed", 20261110, 0, 4294967295)
                critical_percent = bounded_int("critical_fault_percent", 0, 0, 30)

                with RUN_LOCK:
                    current = next(iter(ACTIVE_AUTONOMOUS.values()), None)
                    if current and current["process"].poll() is None:
                        return self._json({"error": "An autonomous session is already running. Stop or finish it before starting another."}, 409)
                    session_id = f"aibars_auto_{time.time_ns()}"
                    output = ROOT / "runs" / "autonomous" / session_id
                    output.mkdir(parents=True, exist_ok=False)
                    stop_file = output / "stop.request"
                    console = (output / "session_console.log").open("w", encoding="utf-8")
                    command = [str(binary), "--autonomous", "--out", str(output),
                               "--session-cycles", str(session_cycles), "--max-incidents", str(max_incidents),
                               "--fault-interval-min", str(interval_min), "--fault-interval-max", str(interval_max),
                               "--tick-delay-ms", str(tick_delay_ms), "--seed", str(seed),
                               "--critical-fault-percent", str(critical_percent), "--stop-file", str(stop_file),
                               *simulator_args(profile)]
                    try:
                        process = subprocess.Popen(command, cwd=ROOT, stdout=console,
                                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
                    except Exception:
                        console.close()
                        shutil.rmtree(output, ignore_errors=True)
                        raise
                    ACTIVE_AUTONOMOUS.clear()
                    ACTIVE_AUTONOMOUS[session_id] = {"output": output, "process": process,
                        "console": console, "stop_file": stop_file, "started_at": time.monotonic(),
                        "started_wall": time.time(), "config": {"session_cycles": session_cycles,
                        "max_incidents": max_incidents, **timing,
                        "seed": seed, "critical_fault_percent": critical_percent}}
                return self._json({"session_id": session_id, "started": True, "mode": "AUTONOMOUS",
                                   "simulation_only": True, "config": ACTIVE_AUTONOMOUS[session_id]["config"]})

            scenario = payload.get("scenario", "nominal")
            if scenario not in ALLOWED:
                return self._json({"error": "Unknown scenario. Choose one of the documented AIBARS scenarios."}, 400)

            binary, profile = self._binary_and_profile()
            with RUN_LOCK:
                active = sum(1 for item in ACTIVE_RUNS.values() if item["process"].poll() is None)
                if active >= MAX_ACTIVE_RUNS:
                    return self._json({"error": f"The local simulator is at capacity ({MAX_ACTIVE_RUNS} active runs). Wait for a run to finish."}, 429)

                # Keep recent run metadata bounded. Older completed runs are pruned
                # from disk as well as memory so repeated dashboard sessions do not
                # grow the local runs directory forever.
                completed = sorted(
                    ((key, item) for key, item in ACTIVE_RUNS.items() if item["process"].poll() is not None),
                    key=lambda pair: pair[1].get("completed_at", pair[1]["started_wall"]),
                )
                while len(ACTIVE_RUNS) >= MAX_RETAINED_RUNS and completed:
                    old_key, old_item = completed.pop(0)
                    ACTIVE_RUNS.pop(old_key, None)
                    shutil.rmtree(old_item["output"], ignore_errors=True)
                if len(ACTIVE_RUNS) >= MAX_RETAINED_RUNS:
                    return self._json({"error": "Too many retained runs. Restart the local dashboard server to clear run metadata."}, 429)

                run_id = f"{scenario}_{time.time_ns()}"
                output = ROOT / "runs" / "live" / run_id
                output.mkdir(parents=True, exist_ok=False)
                log_stream = (output / "simulator_console.log").open("w", encoding="utf-8")
                command = [str(binary), "--scenario", scenario, "--out", str(output),
                           *simulator_args(profile), "--tick-delay-ms", "120"]
                try:
                    process = subprocess.Popen(command, cwd=ROOT, stdout=log_stream,
                                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
                except Exception:
                    log_stream.close()
                    shutil.rmtree(output, ignore_errors=True)
                    raise
                ACTIVE_RUNS[run_id] = {"scenario": scenario, "output": output,
                                       "process": process, "log_stream": log_stream,
                                       "started_at": time.monotonic(), "started_wall": time.time(),
                                       "finalized": False}
            return self._json({"run_id": run_id, "scenario": scenario, "started": True,
                               "simulation_only": True})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return self._json({"error": f"Invalid request: {exc}"}, 400)
        except Exception as exc:
            return self._json({"error": str(exc)}, 500)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true",
                        help="Open the dashboard in the default browser after the local server starts")
    parser.add_argument("--profile", type=pathlib.Path, default=ROOT / "config" / "default_profile.json",
                        help="JSON operating profile to apply to live simulator runs")
    args = parser.parse_args()
    global PROFILE_PATH
    PROFILE_PATH = args.profile.resolve()
    try:
        load_profile(PROFILE_PATH)
    except Exception as exc:
        parser.error(f"Invalid profile: {exc}")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        parser.error("For security, the dashboard server only permits loopback host bindings.")
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    server.daemon_threads = True
    dashboard_url = f"http://{args.host}:{args.port}"
    print(f"AIBARS dashboard: {dashboard_url}", flush=True)
    print("Press Ctrl+C to stop. API starts manual test runs or continuous autonomous simulation sessions only.", flush=True)
    if args.open_browser:
        def _open_dashboard() -> None:
            try:
                opened = webbrowser.open(dashboard_url, new=2, autoraise=True)
                if not opened:
                    print("Could not open a browser automatically. Copy this address into Chrome or Edge:", dashboard_url, flush=True)
            except Exception as exc:
                print(f"Automatic browser opening failed ({exc}). Open this address manually: {dashboard_url}", flush=True)
        # Wait briefly so the HTTP server is already accepting requests before
        # the browser navigates to it. A daemon timer will not block shutdown.
        browser_timer = threading.Timer(1.0, _open_dashboard)
        browser_timer.daemon = True
        browser_timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AIBARS dashboard.")
    finally:
        server.server_close()
        with RUN_LOCK:
            for session in ACTIVE_AUTONOMOUS.values():
                process = session["process"]
                if process.poll() is None:
                    session["stop_file"].touch(exist_ok=True)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
                try:
                    if not session["console"].closed:
                        session["console"].close()
                except Exception:
                    pass
            for run in ACTIVE_RUNS.values():
                process = run["process"]
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                try:
                    if not run.get("log_stream").closed:
                        run["log_stream"].close()
                except Exception:
                    pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# AIBARS — Artificial Intelligence Black Box and Autonomous Recovery System

**Release:** 2.3.2 — Time-configurable autonomous operations and fault-injection platform  
**Domain:** Embedded-system resilience, explainable diagnostics, AI-assisted fault classification and autonomous recovery  
**Execution:** Laptop/desktop; no physical hardware required  
**Core:** C++17 simulator and recovery engine + Python standard-library analytics/dashboard

AIBARS is a reproducible software platform for observing a simulated embedded system, recording the pre-fault history, detecting and diagnosing faults, prioritising incidents, selecting bounded recovery actions, and verifying whether the simulated system has returned to a healthy state.

The end-to-end lifecycle is:

**Monitor → Record → Detect → Diagnose → Assess Risk → Decide → Recover → Verify → Replay**

This release expands the original C++ baseline with a trained Gaussian Naive Bayes advisory classifier, a transparent risk-triage engine, editable operating profiles, concurrent multi-device fault campaigns, incident replay, a local interactive dashboard and live scenario-execution API.

## 1. What is implemented in v2.3.2

### C++ embedded-system simulation and recovery core

- Deterministic simulated sensor, communication and task-health telemetry.
- Temperature freshness timeout, stuck-value detection, engineering-range checks for temperature/voltage/current, communication heartbeat timeout and primary/secondary task-progress monitoring.
- Sensor and communication timeouts are declared only after their configured age window is reached; one missed update does not immediately become a timeout.
- Observation duration expands automatically to honour accepted thresholds up to 1,000 ticks.
- Configurable detection thresholds through CLI arguments and `config/default_profile.json` (the Python campaign runner maps the profile to the C++ simulator).
- Explainable deterministic diagnostic rules with fault evidence, primary cause, severity and recommended action.
- Component-specific recovery actions for simulated sensor reinitialisation/restart/quarantine, communication restart, primary-task restart and secondary-task restart; an action only repairs its target subsystem.
- Bounded recovery attempts, configurable healthy verification cycles and retry backoff.
- Compound fault containment and persistent-fault escalation to safe mode.
- Recovery is not declared successful until the configured consecutive healthy-cycle requirement is satisfied.


### Persistent autonomous operations session (v2.2.0 foundation; seconds-based timing controls in v2.3.2)

- A single `EmbeddedSystemSimulator` object and global tick counter remain active for the full session; fault episodes do not create a new logical device or reset its session clock.
- After a configurable interval of healthy monitoring, a seeded automatic scheduler selects one fault from the recoverable sensor, communication and task fault pool. The dashboard supports fixed intervals (for example, one fault after every 2.0 seconds of healthy monitoring) and random intervals (for example, a seeded selection between 2.0 and 5.0 seconds). No scenario selection is required after the session starts.
- The supervisor logs normal telemetry, schedules the fault, observes the fault episode, runs the existing deterministic detector and diagnosis engine, performs bounded component-specific recovery, and verifies consecutive healthy cycles.
- After verified recovery, the same logical device returns to normal monitoring and the scheduler can select another fault. This repeats until the cycle limit, incident limit, operator stop request or a safe-mode condition.
- Optional critical-test injection can select compound or persistent faults; these are expected to enter safe mode and terminate the session. It is off by default.
- The session writes a continuously flushed root `events.jsonl`, live `session_status.json`, final `session_summary.json`, and per-episode incident records under `episodes/`.
- Python enriches completed autonomous episodes with the advisory ML classification and risk-triage report. The AI remains advisory and is not allowed to authorise C++ recovery actions.
- The dashboard presents an **Autonomous Operations Session** panel with seconds-based fixed/random scheduling, live next-fault countdown, telemetry update interval and session controls. A separate **Fault Injection Test Bench** remains available for manually selected, repeatable tests.

### Manual fault-injection test bench

- The ten predefined scenarios remain as deterministic verification cases. They are useful for regression tests and focused demonstrations, but are not the main autonomous operating mode.
- Live manual scenario runs use `POST /api/start`; the autonomous session uses a different API and a C++ `--autonomous` execution path.

### Black-box event recording and incident reconstruction

- Fixed-capacity in-memory circular history (default 128 recent events).
- Sequential append-only JSON Lines event stream for each run, including sensor values, data ages, communication status and both task-progress monitors.
- Incident report captures diagnosis, evidence, recovery decision and retained event history.
- Run summary JSON and per-run event timeline.
- Replay utility validates sequence ordering and reconstructs a concise incident timeline summary.

### AI-assisted fault classification

- Python implementation of Gaussian Naive Bayes using only the standard library.
- Reproducible labelled synthetic telemetry generation for six classes: normal, sensor timeout, sensor stuck, sensor out-of-range, communication timeout and task hang.
- Stratified 80/20 hold-out evaluation with confusion matrix, per-class precision, recall and F1.
- Persisted model parameters in `artifacts/fault_classifier_model.json`.
- Per-run feature extraction and advisory class probabilities in `advanced_analysis.json`.
- Compound-fault logic overrides single-label ML advice.
- **Safety boundary:** the ML model is advisory only. It cannot authorise or execute recovery. The deterministic C++ diagnosis and bounded recovery policy remain authoritative.

### Risk assessment and recovery governance

- Configurable impact weights and risk bands.
- Transparent incident-prioritisation score based on deterministic severity, impact and advisory classifier confidence.
- Compound-fault override to the highest risk band.
- Bounded retry and safe-mode escalation guardrails.
- The risk score is a triage heuristic, not a calibrated failure probability, functional-safety risk assessment or certification result.

### Multi-device campaigns and interactive dashboard

- Ten reproducible fault scenarios execute concurrently as separate simulator processes across configurable logical device identities.
- A seeded 48-run randomized concurrent regression campaign checks retry bounds, recovery invariants, compound-fault containment and persistent-fault escalation.
- Campaign manifest records device assignment and outputs.
- Dashboard includes campaign metrics, a saved autonomous-session preview, autonomous session start/stop controls, live telemetry and event streaming, automatically enriched autonomous incident analysis, the separate manual test bench, deterministic rule evidence, ML advisory, risk assessment, step-by-step black-box playback and CSV/JSON exports.
- Local dashboard server exposes loopback-only POST APIs for manual scenario execution and continuous autonomous sessions. It validates session limits, checks request Origin, limits retained runs and supports controlled autonomous stop requests.
- Dashboard and server use Python standard library; no third-party web framework is required.

## 2. Architecture

```text
                     +-------------------------------+
                     | Configurable System Profile   |
                     | thresholds / retry / risk     |
                     +---------------+---------------+
                                     |
                                     v
+---------------------+   +----------+----------+   +----------------------+
| Concurrent Device   |-->| C++ Telemetry       |-->| Black Box Recorder   |
| Simulators / Faults  |   | Simulation          |   | ring + JSONL         |
+---------------------+   +----------+----------+   +----------+-----------+
                                     |                         |
                                     v                         v
                           +---------+---------+      +--------+---------+
                           | Deterministic     |      | Incident Replay  |
                           | Fault Detection   |      | / Event History  |
                           +---------+---------+      +------------------+
                                     |
                                     v
                           +---------+---------+
                           | Explainable       |<---- ML Advisory Classifier
                           | Rule Diagnosis    |      (Gaussian NB)
                           +---------+---------+
                                     |
                                     v
                           +---------+---------+
                           | Risk Triage       |
                           | + Recovery Policy |
                           +---------+---------+
                                     |
                                     v
                           +---------+---------+
                           | Bounded Recovery  |
                           | + Retry Backoff   |
                           +---------+---------+
                                     |
                                     v
                           +---------+---------+
                           | Healthy-Cycle     |
                           | Verification      |
                           +----+----------+---+
                                |          |
                             NORMAL     SAFE MODE
                                \          /
                                 v        v
                           +----+--------+-----+
                           | Reports + Local   |
                           | Interactive UI    |
                           +-------------------+
```

## 3. Repository layout

```text
AIBARS/
├── CMakeLists.txt
├── README.md
├── VERSION
├── config/
│   ├── default_profile.json
│   └── strict_profile.json
├── include/aibars/          # C++ public interfaces
├── src/                     # C++ simulator, detection, diagnosis, recovery, logger
├── tests/                   # C++ core and Python advanced/integration tests
├── scripts/                 # Cross-platform validation runner
├── tools/
│   ├── aibars_advanced/     # ML, risk, configuration, fleet, replay modules
│   ├── run_advanced.py      # Full build, concurrent campaign and report workflow
│   ├── launch_dashboard.py  # Local interactive dashboard server
│   ├── replay_incident.py   # Black-box replay CLI
│   └── build_advanced_dashboard.py
├── docs/                    # Architecture, model, configuration, validation, limits
├── examples/
│   ├── advanced_runs/       # Ten reproducible scenario outputs
│   └── dashboard.html       # Standalone interactive report/dashboard
└── artifacts/               # Model, evaluation, fleet and aggregate JSON reports
```

## 4. Requirements

- C++17 compiler: GCC, Clang or MSVC.
- CMake 3.16 or newer.
- Python 3.10 or newer.
- No third-party Python packages are required.

### Windows (recommended first run)

Install/configure Python 3.10+, CMake and a C++17 toolchain (Visual Studio Build Tools/MSVC or MSYS2 UCRT64 GCC). The easiest first run is to double-click `RUN_AIBARS_WINDOWS.bat` from the extracted project folder. It runs the full test suite, regenerates the scenario/evaluation reports, and starts the dashboard. Keep its terminal window open and visit `http://127.0.0.1:8765`.

Alternatively, open PowerShell in the extracted `AIBARS` folder:

```powershell
python tools/run_advanced.py
```

This command configures and builds the C++ core, runs the ten concurrent fault campaigns, trains/evaluates the advisory model, creates risk and fleet reports, and generates `examples/dashboard.html`.

### Linux / macOS / MSYS2

```bash
python3 tools/run_advanced.py
```

## 5. View the dashboard

### Open the saved dashboard

Open `examples/dashboard.html` in a browser. It contains the recorded scenario campaigns, searchable results, diagnosis/risk information and event timelines. This mode is offline playback of the saved run records.

### Launch the interactive local dashboard server

From the project root:

```bash
python tools/launch_dashboard.py
```

Then open `http://127.0.0.1:8765`. In the **Autonomous Operations Session** panel, press **Start autonomous session**. AIBARS will automatically schedule faults after normal monitoring intervals, perform detection/diagnosis/recovery/verification, then resume monitoring. You do not need to select a scenario. Use the separate **Fault Injection Test Bench** only when you want to run one known scenario deliberately.

To use another operating profile, pass it explicitly:

```powershell
python tools/run_advanced.py --profile config/strict_profile.json
python tools/launch_dashboard.py --profile config/strict_profile.json
```

Then open:

```text
http://127.0.0.1:8765
```

Select a scenario and click **Run selected scenario** to launch a fresh local C++ simulator run and load its diagnosis, risk assessment and event timeline. Stop the server with Ctrl+C.

The server binds to `127.0.0.1` by default and is intended for local development. Do not expose it to an untrusted network.

## 6. Run autonomous mode directly from the command line

```bash
./build/aibars_sim --autonomous --out runs/autonomous_demo \
  --session-cycles 120 --max-incidents 3 \
  --fault-interval-min 8 --fault-interval-max 16 \
  --seed 20261110 --tick-delay-ms 60
```

On Windows, use the executable under `build\Release\aibars_sim.exe` if using a Visual Studio generator. Add `--critical-fault-percent 10` to include a 10% chance per scheduled episode of selecting a critical test fault that can enter safe mode. Use `--stop-file PATH` to support controlled stop requests from a supervising process. The session ends when its monitoring-cycle limit or incident limit is reached, a critical fault enters safe mode, or the stop file appears.

The autonomous session keeps one logical simulated device and global tick counter. It does not physically connect to any sensor, ECU, FPGA or industrial machine.

## 7. Re-run tests

```bash
python scripts/run_tests.py
```

The validation script configures/builds C++, runs CTest, and discovers all Python test modules. The current suite contains nine focused C++ core checks within the CTest executable and 24 Python advanced/integration test methods. It validates timeout age windows, component-specific recovery, event ordering, bounded recovery, recovery verification, model evaluation and schema validation, risk scoring, configuration mapping, fleet ordering, replay, API restrictions and custom C++ threshold overrides.

## 8. Run a single scenario manually

```bash
./build/aibars_sim --scenario task_hang --out runs/task_hang
```

On Windows, the executable will normally be `build\\aibars_sim.exe` or `build\\Release\\aibars_sim.exe`.

Available scenarios:

| Scenario | Injected fault | Expected response |
|---|---|---|
| `nominal` | No fault | Normal operation |
| `sensor_timeout` | Stale temperature data | Sensor restart and verification |
| `sensor_stuck` | Repeated unchanged temperature | Sensor reinitialisation and verification |
| `sensor_out_of_range` | Temperature above engineering range | Quarantine/reinitialise path and verification |
| `communication_timeout` | Missing communication heartbeat | Interface restart and verification |
| `task_hang` | Primary control-loop progress stops | Task restart and verification |
| `secondary_task_hang` | Secondary telemetry task stalls | Secondary task restart and verification |
| `multiple_task_hangs` | Two independent task monitors stall | Compound diagnosis and safe mode |
| `multiple_faults` | Independent temperature and communication faults | Compound diagnosis and safe mode |
| `recovery_failure` | Task hang persists through recovery | Bounded retry/backoff then safe mode |

## 9. Configuration

Edit `config/default_profile.json`. It contains detection limits, timeout windows, stuck-sample threshold, maximum recovery attempts, healthy verification cycles, retry-backoff ticks, risk-band thresholds, impact weights and concurrent fleet settings.

The campaign runner validates the profile and passes detector/recovery values to the C++ simulator. Fail-safe requirements—safe mode on compound faults and recovery exhaustion—are mandatory guardrails and cannot be disabled through the profile.

See [docs/configuration.md](docs/configuration.md).

## 10. AI model and measured results

The model is trained and evaluated on a generated synthetic telemetry dataset. The current generated evaluation report is in `artifacts/ml_evaluation.json`. Its accuracy, confusion matrix and class metrics describe only the synthetic hold-out split. They must not be represented as accuracy on real sensors, ECUs or industrial equipment.

The model is an advisory diagnostic component. The C++ rule diagnosis and recovery manager remain in control. See [docs/ai_model.md](docs/ai_model.md).

## 11. Final validation report

See [docs/final_validation.md](docs/final_validation.md), [docs/artifacts_guide.md](docs/artifacts_guide.md) and `artifacts/final_validation_report.json` for the recorded compiler versions, test counts, scenario outcomes, stress regression and live API checks.

## 12. Validation status and limitations

The package includes reproducible local test commands and generated evidence. Validation is for software simulation only. This project does not claim:

- physical sensor, ECU, vehicle, industrial plant or FPGA testing;
- certified real-time behaviour or deterministic wall-clock deadlines;
- calibrated field ML accuracy or production-trained fault models;
- functional-safety compliance, SIL/ASIL certification or a certified safety case;
- actual hardware resets, bus recovery or actuator isolation—the recovery operations are simulator state transitions;
- formal verification, HIL testing, timing closure or production deployment readiness.

The logical multi-device fleet consists of separate local simulator processes; it is not a distributed network of physical devices. The dashboard live-run API is a local development service only.

See [docs/safety_and_limitations.md](docs/safety_and_limitations.md) and [docs/validation.md](docs/validation.md).

## 13. Portfolio-safe project summary

**AIBARS — Artificial Intelligence Black Box and Autonomous Recovery System:** Developed a laptop-based embedded-system resilience platform using a C++17 fault-injection simulator and Python analytics. Implemented a rolling black-box recorder with telemetry/event history, configurable age-based fault detection, component-specific recovery, explainable rule diagnosis, an advisory Gaussian Naive Bayes classifier, risk triage, bounded retry/backoff, healthy-cycle verification, safe-mode escalation and incident replay. Executed ten fault scenarios concurrently across logical simulated devices, added seeded stress regression and built a live local dashboard with incident timelines. Verified through automated C++ and Python software tests; no physical hardware validation claimed.

## Automatic browser launch on Windows

`RUN_AIBARS_WINDOWS.bat` starts the local dashboard server with `--open-browser`. After the server is listening, it asks Windows to open the dashboard in the default browser. If Windows has no default browser handler or blocks this request, the command window prints `http://127.0.0.1:8765` for manual opening. The server remains running until Ctrl+C.

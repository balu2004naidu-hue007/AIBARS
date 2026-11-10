# AIBARS v2.3.2 Validation

## Reproducible validation command

```bash
python scripts/run_tests.py
```

This command configures and builds the C++17 core, runs CTest, then discovers the Python integration and advanced-module test suites.

## Autonomous session validation

The persistent C++ autonomous mode is exercised in the integration suite. It starts with normal monitoring, uses a seeded scheduler to choose fault episodes internally, performs diagnosis and component-specific recovery, verifies consecutive healthy cycles, and resumes monitoring on the same logical device with a monotonic global tick. Critical-fault and controlled-stop paths are also covered. The dashboard API test validates live start/status, event streaming and per-episode AI/risk enrichment.

## Seconds-based autonomous interval validation

- Fixed mode: 2.0 seconds at 100 ms per telemetry tick maps to 20 healthy monitoring cycles.
- Random mode: 2.0–5.0 seconds at 100 ms per telemetry tick maps to 20–50 cycles using the session seed.
- Conversion rounds upward; it never schedules earlier than the requested interval.
- The interval is healthy monitoring time after recovery. Detection/recovery time and the five-sample fault-activation warm-up are additional.
- The live dashboard exposes a next-fault-schedule countdown during normal monitoring.

## Advanced campaign

```bash
python tools/run_advanced.py
```

The campaign executes ten independent simulator scenarios concurrently across the configured number of logical device workers, runs a seeded 48-iteration concurrent fault/recovery regression, trains/evaluates the synthetic-data classifier, enriches runs with advisory diagnosis and risk scores, writes the fleet manifest and generates the offline dashboard.

## Test coverage

- C++ ring-buffer retention and chronological ordering.
- Sensor and communication timeout age windows (verify no early trigger before the configured threshold).
- Sensor stuck-value sample windows and sustained primary/secondary task stalls.
- Component-specific recovery: sensor restart does not repair communication, and task restart targets the affected task.
- Sustained task-hang detection.
- Compound-fault containment.
- Bounded retry, safe-mode escalation and healthy-cycle verification.
- Ten end-to-end simulator scenario outcomes.
- Monotonic black-box event sequence and incident reports.
- Gaussian Naive Bayes training, stratified hold-out evaluation, feature extraction from real simulator event fields, model serialization and model-schema/inference-input validation.
- Configuration validation and mapping to C++ CLI options.
- Custom detector-threshold override through the compiled simulator.
- Risk score/compound-fault prioritisation.
- Concurrent fleet job ordering, randomized stress invariants and incident replay summary.
- Local dashboard health, POST-only launch API, cross-origin rejection, event polling and completed-run enrichment are exercised by automated tests.

The current suite includes nine C++ core checks inside the CTest executable and 24 Python advanced/integration test methods, including seconds-based fixed/random interval conversion, validation and dashboard API checks. A separate full 48-run randomized concurrent stress campaign is executed by `python tools/run_advanced.py`.

## Evidence files

- `artifacts/ml_evaluation.json`
- `artifacts/fault_classifier_model.json`
- `artifacts/advanced_system_report.json`
- `artifacts/fleet_manifest.json`
- `examples/advanced_runs/*/summary.json`
- `examples/advanced_runs/*/incident.json` where faults are detected
- `examples/advanced_runs/*/events.jsonl`

Metrics from the ML evaluation are based on generated synthetic samples. They do not represent measured fault classification accuracy on real equipment.

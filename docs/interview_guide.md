# AIBARS v2.3.2 Interview Guide

## 30-second explanation

AIBARS is a laptop-based embedded-system resilience platform. A C++17 simulator produces sensor, communication and task-health telemetry; a rolling black box records the event history; deterministic rules detect and explain faults; an advisory Gaussian Naive Bayes model ranks single-fault classes; a transparent risk engine prioritises incidents; and a bounded recovery manager performs simulated recovery with retry backoff and healthy-cycle verification. Compound or persistent faults enter safe mode. Python tooling runs concurrent simulated devices, performs seeded stress regression, replays incidents and provides a local interactive dashboard.

## How autonomous operation works

In Autonomous Operations Mode, the operator starts a bounded session once. A seeded internal scheduler chooses faults after configurable fixed or random intervals entered in seconds. The C++ simulator retains one logical device and a monotonic session clock across episodes. AIBARS detects and diagnoses each episode, executes bounded component-specific recovery, verifies healthy cycles, and resumes normal monitoring. The manual Fault Injection Test Bench remains separate for reproducible one-fault verification.

## Key architectural decisions

**Why split ML from the recovery authority?**  
The ML model is trained on generated synthetic telemetry and is advisory. Deterministic rule diagnosis, explicit recovery policy and fail-safe containment are easier to inspect and test. The model cannot directly issue a recovery command.

**What does the model's accuracy mean?**  
It measures performance on a generated synthetic hold-out set with known signatures. It is not field accuracy and does not show how the classifier would perform on a real ECU, industrial machine or sensor dataset.

**Why use a black-box circular buffer and JSONL?**  
The circular buffer retains a bounded recent history in memory; JSONL records the complete ordered event stream for a run. The incident report includes the retained pre-fault and post-fault context.

**How is a timeout different from a stuck sensor?**  
A timeout means the data is stale or absent. A stuck sensor continues to provide fresh samples but repeats an unchanged value for the configured sample window.

**Why require healthy-cycle verification?**  
A recovery action being issued does not prove service has resumed. AIBARS requires consecutive healthy telemetry samples before returning to normal mode.

**Why use retry backoff and bounded retries?**  
A backoff interval prevents immediate repeated retries; the attempt limit prevents an endless recovery loop. If the simulated fault persists, the supervisor enters safe mode.

**Why does a compound fault enter safe mode?**  
Several independent fault rules firing in one observation window can indicate interacting failures. The baseline policy contains the system instead of attempting isolated recoveries that might not restore a coherent state.

**What does risk score represent?**  
It is an explicit prioritisation heuristic using severity, configured impact and advisory classifier confidence. It is not a calibrated failure probability or certified safety assessment.

**What does the multi-device test prove?**  
It launches independent simulator processes concurrently under logical device identities. It demonstrates concurrent software fault campaigns, not a distributed physical device network.

**Is it tested on an ECU, MCU or FPGA?**  
No. It is a laptop-based simulation and software test platform. Recovery actions change simulator state only.

## Suggested demonstration sequence

1. Open the dashboard and explain the architecture and metrics.
2. Start Autonomous Operations in Fixed mode at 2.0 seconds; show normal telemetry, the next-schedule countdown, automatic fault scheduling, diagnosis, recovery, verification and resumed monitoring.
3. Repeat in Random mode (for example, 2.0–5.0 seconds) and explain the seeded interval selection.
4. Use the manual Fault Injection Test Bench for `sensor_stuck` and `task_hang` to explain deterministic fault-evidence checks.
5. Run `recovery_failure`; show retry backoff, bounded attempts and safe-mode escalation.
6. Run `multiple_faults` and `multiple_task_hangs`; explain why compound faults trigger containment.
7. Open an event timeline and run `python tools/replay_incident.py examples/advanced_runs/task_hang`.
8. Show `artifacts/ml_evaluation.json`, explicitly identify its synthetic data source and explain why its metrics are not field accuracy.
9. Run `python tools/run_stress_campaign.py --iterations 48` and inspect the invariant report.

## Resume-safe project summary

Developed a laptop-based C++17/Python embedded-system resilience platform with a rolling black-box recorder, configurable fault detection, explainable rule diagnosis, an advisory Gaussian Naive Bayes classifier, heuristic risk triage, bounded recovery with retry backoff, post-recovery verification and safe-mode escalation. Added concurrent simulated-device campaigns, seeded recovery stress tests, event replay and an interactive local dashboard. Validated through automated software tests; no physical hardware validation claimed.

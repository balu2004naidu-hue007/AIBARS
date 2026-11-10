# AIBARS Demonstration Script

## Goal

Demonstrate that AIBARS can supervise a simulated embedded device without the operator selecting individual fault types, recover supported faults, verify health and resume normal monitoring. Then use the separate manual test bench to prove deterministic fault handling.

## Live demonstration (5–8 minutes)

1. **Introduce the problem.** An embedded controller may experience stale sensors, communication loss or a task that stops progressing. A useful fault-management system needs to detect, diagnose, recover and verify—not only raise an alert.
2. **Start the autonomous session.** In Autonomous Operations Session, use a bounded example such as 120 monitoring cycles, three incidents, a normal-cycle interval of 8–16, a fixed seed and no critical fault injection. Click Start. Do not select a scenario.
3. **Show normal operation.** Point to changing telemetry, the device identity and the MONITORING state.
4. **Show automatic scheduling.** Explain that the seeded scheduler selects a supported fault internally after a normal-monitoring interval. The operator does not choose the fault.
5. **Show detection and diagnosis.** Use the event stream and incident panel to explain the actual telemetry evidence and the deterministic diagnosis.
6. **Explain AI's role.** The Gaussian Naive Bayes model provides an advisory class and scores after the episode; it does not command recovery. The deterministic C++ diagnosis and recovery policy remain authoritative.
7. **Show recovery verification.** Explain bounded attempts and the consecutive healthy-cycle rule. A recovery command alone is not considered success.
8. **Show monitoring resumes.** Confirm that the same logical device returns to MONITORING and the session tick count continues increasing after successful recovery.
9. **Show the black box.** Inspect the event sequence and export the session/incidents.
10. **Use the manual test bench separately.** Select a compound fault or persistent recovery-failure scenario to demonstrate safe-mode escalation under a repeatable test.

## What to say about results

- `VERIFIED` means the simulated component passed the configured consecutive healthy-cycle check.
- `SAFE_MODE_ENTERED` means the simulator escalated a compound or unrecovered condition to a contained state.
- Risk scores are prioritisation heuristics, not probabilities or certified safety levels.
- AI metrics are measured on synthetic generated telemetry only; they are not field accuracy.
- The autonomous session keeps one logical simulator and monotonic session tick across episodes. The separate concurrent fleet campaign runs multiple local simulator processes.

## 60-second project explanation

AIBARS is a laptop-based embedded-system fault-management platform. Its main mode is a persistent autonomous simulation: it monitors normal sensor, communication and task telemetry, schedules faults internally, detects and explains the fault, applies bounded component-specific recovery, verifies consecutive healthy cycles and resumes monitoring on the same logical device. A black-box event stream preserves the session history. A Gaussian Naive Bayes classifier provides advisory fault classification, while deterministic C++ rules retain authority over recovery. A separate manual fault-injection test bench supports repeatable validation of compound and persistent failures. The project demonstrates the full fault-management lifecycle in software; it is not a physical ECU or industrial controller validation.

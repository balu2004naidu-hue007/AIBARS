# Autonomous Operations Mode

## Purpose

The Autonomous Operations Session demonstrates the AIBARS lifecycle without asking the operator to choose each fault. The operator starts a bounded session once. AIBARS then monitors a simulated device, internally schedules fault episodes, diagnoses the resulting telemetry, executes bounded recovery, verifies the outcome and resumes monitoring when recovery succeeds.

## Runtime model

The autonomous path is implemented in the C++ simulator, not as a Python chain of separate one-shot scenarios.

- One `EmbeddedSystemSimulator` object represents `AIBARS-AUTO-ECU-01` for the entire session.
- Its global tick counter continues increasing across normal monitoring, fault detection, recovery and post-recovery monitoring.
- The scheduler waits a configured healthy-monitoring interval between episodes. In Fixed mode, each interval is the same. In Random mode, a seeded generator selects an interval uniformly between the configured minimum and maximum. Intervals are entered in seconds in the dashboard and converted to whole monitoring cycles using the telemetry tick delay. Conversion rounds up to avoid injecting a fault before the requested interval. The interval timer begins after the previous recovery completes; detection and recovery time is additional elapsed time.
- It automatically chooses from six recoverable fault types: sensor timeout, sensor stuck, sensor out of range, communication timeout, primary task hang and secondary task hang.
- The selected fault is activated internally by the simulator after five warm-up samples. The countdown measures time until the scheduler selects/starts the next episode; fault-signal activation follows those five samples. No fault type is sent by the dashboard in autonomous mode.
- The C++ detector evaluates real simulator telemetry. The explainable diagnosis engine identifies the cause and recommends an action.
- The recovery manager executes a component-specific action, applies configured retry limits/backoff and requires configured consecutive healthy cycles.
- After successful verification, `beginScenario(Nominal)` clears episode-local fault state but preserves the simulator object and global tick. Normal monitoring resumes and the scheduler may select another fault.
- A compound or persistent critical-test episode enters safe mode and ends the session. Critical-test injection is disabled by default; the dashboard checkbox enables a 10% critical selection chance per scheduled episode.

The session is bounded by the earlier of the monitoring-cycle limit, incident limit, safe-mode entry or controlled stop request. This makes demonstrations and regression runs finite and reproducible. Use larger limits for longer unattended observation sessions.

## Dashboard operation

1. Run `RUN_AIBARS_WINDOWS.bat` or `python tools/launch_dashboard.py` after building the project.
2. Open `http://127.0.0.1:8765`.
3. In **Autonomous Operations Session**, choose **Fixed interval** or **Random interval**, set the fault interval in seconds, set the telemetry tick interval and select the session/incident limits and random seed.
4. Press **Start autonomous session**. Do not select a scenario; the internal scheduler selects it.
5. Observe telemetry, the next-fault countdown, scheduler mode, current state, scheduled episode, detector/diagnosis/recovery events and recovery verification in the event stream.
6. When recovery is verified, the state returns to `MONITORING`; the same logical device and global tick continue.
7. Use **Stop session** for a controlled stop. The supervisor honours the stop at an episode boundary so it does not cut off recovery verification.
8. Review the automatically enriched episode table after the session ends. It contains the deterministic incident, advisory ML prediction and risk-triage result for each episode.

The **Fault Injection Test Bench** is intentionally separate. Use it only to reproduce one known fault for focused validation, such as a compound fault or persistent recovery failure.

## Seconds-based dashboard examples

- Fixed fault interval: Fixed mode, 2.0 seconds, telemetry tick 100 ms → 20 healthy monitoring cycles between fault episodes.
- Random fault interval: Random mode, 2.0–5.0 seconds, telemetry tick 100 ms → seeded selection from 20 to 50 healthy monitoring cycles.

The timer measures healthy monitoring time after recovery completes. Time spent detecting and recovering a fault is additional. The scheduler starts an episode when the countdown reaches zero; the injected signal becomes active after five simulator warm-up samples. In the live dashboard, the next-fault-schedule countdown is shown while the system is in `MONITORING`; it is replaced by the current fault/recovery state while an incident is active.

## CLI example

```bash
./build/aibars_sim --autonomous --out runs/autonomous_demo \
  --session-cycles 120 --max-incidents 3 \
  --fault-interval-min 20 --fault-interval-max 50 \
  --seed 20261110 --tick-delay-ms 100
```

Add `--critical-fault-percent 10` to opt into occasional critical test faults. `--stop-file PATH` lets the local server request a controlled stop by creating the specified file.

## Files generated

| File | Purpose |
|---|---|
| `events.jsonl` | Full session-wide black-box event stream, flushed after each event |
| `session_status.json` | Current status and telemetry snapshot for live dashboard polling |
| `session_summary.json` | Final state, counters, seed and per-episode outcomes |
| `incident.json` | Most recent incident report |
| `episodes/episode_NN.json` | Episode summary and tick range |
| `episodes/episode_NN_incident.json` | Per-episode fault evidence and recovery report |
| `autonomous_analysis.json` | Post-session ML advisory and risk-triage enrichment, generated by the Python layer |

## AI and risk roles

The C++ deterministic detector and recovery policy remain authoritative for recovery. After the autonomous C++ session completes, the Python analysis layer enriches each episode with the Gaussian Naive Bayes advisory and configured risk-triage score. These explainability/triage outputs do not command or override the C++ recovery policy. The classifier is trained and evaluated on generated synthetic fault signatures only.

## Scope and limitation

The device, sensor signals, task progress, communication link and recovery operations are simulated. AIBARS demonstrates continuous supervisory logic and fault-management workflow in software. It does not connect to or recover physical sensors, ECUs, vehicles or industrial machines, and does not claim real-time, hardware-in-the-loop, FPGA or functional-safety validation.

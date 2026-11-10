# AIBARS Architecture

AIBARS v2.2 separates deterministic embedded fault management from advisory machine learning and presentation, and adds a persistent autonomous supervisor that keeps one logical simulated device active across multiple fault episodes.

1. **Profile loader:** validates numeric detection limits, recovery limits, retry backoff, risk bands, impact factors and fleet size.
2. **Autonomous supervisor:** maintains one persistent `EmbeddedSystemSimulator`, global tick counter and normal-monitoring loop. A seeded scheduler selects faults internally after configurable normal intervals; after verified recovery the supervisor resumes monitoring on the same logical device.
3. **Manual campaign runner:** starts independent simulator processes under logical device identities for repeatable regression and focused fault-injection testing.
4. **C++ simulator:** emits deterministic sensor, communication and task telemetry; supports both autonomous fault scheduling and a manual scenario mode.
5. **Black-box recorder:** stores a fixed-size in-memory recent-history buffer and a sequential JSONL record for the complete autonomous session or a manual test run.
6. **Fault detector:** evaluates data freshness, stuck readings, engineering-range limits, heartbeat age and sustained task stalls.
7. **Explainable rule diagnosis:** creates named fault hypotheses, evidence, severity, rationale and recovery recommendation.
8. **ML advisory:** Gaussian Naive Bayes ranks a single-fault category using extracted telemetry features; compound cases bypass single-class selection.
9. **Risk triage:** combines severity, configurable impact and model advisory confidence into a transparent prioritisation score.
10. **Recovery policy:** performs a bounded simulator action, inserts configured retry backoff and requires consecutive healthy samples.
11. **Safe-mode containment:** compound faults or exhausted recovery attempts enter the simulated safe state.
12. **Dashboard and replay:** inspect campaign summaries, ML advisory, risk, event histories and fresh local simulator runs.

Machine learning and risk scores do not command recovery. Deterministic diagnosis, configured retry limits and containment rules remain authoritative.

## Operating modes

- **Autonomous Operations Session:** start once; normal telemetry is monitored continuously, the internal scheduler selects faults automatically, and the same simulated device resumes normal monitoring after verified recovery. The bounded session stops on its cycle/incident limit, a requested stop or safe-mode entry.
- **Manual Fault Injection Test Bench:** choose a known fault scenario to reproduce a specific expected condition. This is a verification tool and is not required for automatic fault scheduling.
- **Campaign/regression mode:** run the fixed ten-case fleet and stress suite for repeatable validation.

The autonomous scheduler is deterministic for a given seed. The default pool contains recoverable single-fault cases. Optional critical-fault injection can exercise compound/persistent safe-mode paths.

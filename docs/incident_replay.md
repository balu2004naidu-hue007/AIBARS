# Black-Box Incident Replay

Each simulator run writes `events.jsonl` with monotonically increasing sequence numbers. It records run start, telemetry samples, fault injection, detected fault evidence, diagnosis, recovery attempts, retry backoff, verification samples, safe-mode entry and terminal outcome where applicable.

Run a replay summary:

```bash
python tools/replay_incident.py examples/advanced_runs/task_hang
```

Replay validates event ordering and reports the observed components, fault events, recovery attempts, recovery verification and safe-mode events. The dashboard displays the complete recorded sequence for inspection.

## Randomized stress campaign

Run a concurrent seeded campaign of fault/recovery cases:

```bash
python tools/run_stress_campaign.py --iterations 48 --seed 20261109
```

The campaign validates retry bounds, healthy-cycle verification invariants, compound-fault containment and persistent-fault escalation. The default full run also produces `artifacts/stress_campaign_report.json`. This is software-simulator regression, not physical hardware stress testing.

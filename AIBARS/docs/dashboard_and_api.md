# Dashboard and Local API

## Offline dashboard

Open `examples/dashboard.html` in a browser. It is a self-contained view of the generated campaign data and supports scenario selection, result filtering, risk/ML detail, and black-box event timelines.

## Interactive local mode

Run `python tools/launch_dashboard.py` and browse to `http://127.0.0.1:8765`.

- `GET /` serves the dashboard.
- `GET /api/health` reports local service status.
- `POST /api/autonomous/start` accepts bounded session settings. The v2.3 seconds-based interface accepts `interval_mode` (`fixed` or `random`), `interval_seconds` for fixed mode or `interval_min_seconds`/`interval_max_seconds` for random mode, plus `tick_delay_ms`, `session_cycles`, `max_incidents`, `seed` and `critical_fault_percent`. The server converts seconds to whole monitoring cycles using ceiling rounding. Legacy cycle-based fields remain supported for compatibility. Fault selection happens inside the C++ supervisor; the client does not send a scenario name.
- `GET /api/autonomous/status?session_id=<id>` returns live status, device telemetry, the continuously appended black-box events and, after completion, the session summary plus per-episode ML/risk enrichment.
- `POST /api/autonomous/stop` accepts `{"session_id":"..."}` and creates a controlled stop request that the C++ supervisor honours at an episode boundary.
- `POST /api/start` accepts a JSON body such as `{"scenario":"task_hang"}` and starts one allowlisted manual C++ test-bench scenario.
- `GET /api/status?run_id=<id>` returns the manual run event timeline and, after the child process exits, the summary, incident, ML advisory and risk triage.
- GET requests to either start endpoint are rejected with HTTP 405; execution is not triggered by a simple cross-site GET.

The server binds to loopback only. It validates Origin when supplied, limits active and retained runs, bounds run duration, and rejects unknown scenarios. It has no authentication because it is intended for local development on the user's own machine. Do not bind it to a public interface or expose it to an untrusted network.

## Dashboard investigation and exports

- The campaign table can be filtered by scenario, diagnosis, device identity and recovery state.
- Selecting a campaign loads the deterministic rule evidence, incident severity, rule match score, AI class probabilities, risk-triage inputs and recovery outcome.
- The black-box timeline has Play, Pause, Next Event and Reset controls for step-by-step incident reconstruction. The same controls work in offline saved-result mode and with results returned by a live run.
- Export Campaign CSV produces a spreadsheet-friendly summary of all currently loaded runs.
- Download Selected Incident JSON exports the selected enriched run, including the event timeline, ML advisory and risk assessment.

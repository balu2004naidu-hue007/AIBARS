# AIBARS Configuration

Edit `config/default_profile.json` before running `python tools/run_advanced.py`.

| Section | Setting | Purpose |
|---|---|---|
| detection | minimum/maximum temperature, voltage, current | Engineering-range boundaries for simulator telemetry |
| detection | sensor timeout ticks | Maximum permitted age of temperature data |
| detection | communication timeout ticks | Maximum heartbeat age |
| detection | stuck sample count | Number of unchanged fresh samples used for stuck detection (2–1000) |
| detection | task stall ticks | Sustained task-progress stall window |
| recovery | maximum attempts | Bounded retry count |
| recovery | required healthy cycles | Consecutive healthy samples required to verify recovery |
| recovery | retry backoff ticks | Wait interval before later retry attempts; later waits scale with attempt number |
| risk | low/moderate/high bands | Risk-score band boundaries |
| risk | impact weights | Incident impact multiplier by fault category |
| fleet | workers | Maximum concurrent simulator processes |
| fleet | device_ids | Logical identities assigned to concurrent simulated campaigns |

The Python configuration loader validates finite numeric sensor ranges, supported timeout windows (1–1000 ticks), stuck sample count (2–1000), recovery limits, risk bands, impact weights and unique logical device IDs. The C++ detector and CLI apply matching validation, and the simulator observation window expands to honour accepted large thresholds. The loader rejects attempts to disable mandatory safe-mode containment guardrails.

The C++ executable also supports direct override flags. Run `build/aibars_sim --help` for the available flags.

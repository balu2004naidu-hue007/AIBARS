# AIBARS User Guide

## What AIBARS does

AIBARS simulates an embedded controller, continuously monitors telemetry, automatically schedules simulated fault episodes, records events, diagnoses conditions, estimates incident priority, performs bounded simulated recovery and verifies the result. It is a laptop-only engineering simulation. Manual fault injection remains available as a separate test bench.

## First run on Windows

1. Extract the project ZIP into a folder with a short path, for example `C:\AIBARS`.
2. Install Python 3.10+, CMake 3.16+ and a C++17 toolchain such as Visual Studio Build Tools or MSYS2 UCRT64 GCC.
3. Open the extracted folder and double-click `RUN_AIBARS_WINDOWS.bat`.
4. The launcher runs the full C++/Python test suite, generates the ten-scenario campaign, produces a saved autonomous-session preview and starts the local dashboard.
5. Open `http://127.0.0.1:8765` in Chrome or Edge.
6. Keep the terminal window open while using live mode. Press Ctrl+C in that window to stop the server.

## First run from PowerShell

Open PowerShell in the extracted `AIBARS` folder and run:

```powershell
python --version
cmake --version
python scripts/run_tests.py
python tools/run_advanced.py
python tools/launch_dashboard.py
```

Open `http://127.0.0.1:8765` after the last command.

## Offline and live dashboard modes

- **Offline:** Open `examples/dashboard.html`. This displays the saved campaign results and supports report exports. It does not start new simulations. It does include saved-run selection, incident explainability, event-by-event timeline playback and report exports.
- **Live:** Start `python tools/launch_dashboard.py` and open the local URL. Use **Autonomous Operations Session → Start autonomous session** to run continuous monitoring with internally scheduled faults. AIBARS will resume normal monitoring after verified recovery. Use **Stop session** for a controlled stop. The separate **Fault Injection Test Bench** lets you select one scenario for repeatable validation.

## Recommended final demonstration sequence

1. Start with **Autonomous Operations Session**. Do not select a fault scenario. Let the automatic scheduler introduce faults after normal monitoring periods.
2. Watch telemetry continue during normal operation, the scheduler announce an episode, fault detection and diagnosis events appear, recovery execute, and healthy-cycle verification complete.
3. Confirm the same logical device returns to `MONITORING` and the global tick count continues increasing after recovery.
4. Inspect the automatically diagnosed incident table for ML advisory and risk-triage results.
5. Use the event stream to explain the sequence and export the session summary.
6. Then open the separate manual **Fault Injection Test Bench** to demonstrate a compound fault or persistent recovery failure entering safe mode.

## Understand the results

- `VERIFIED` means the simulated system passed the configured number of consecutive healthy cycles after recovery.
- `SAFE_MODE_ENTERED` means AIBARS withheld isolated recovery for a compound fault or entered containment after the retry limit was exhausted.
- ML class scores are advisory rankings from a model trained on generated synthetic data; they are not field-calibrated probabilities.
- Risk score is a configurable prioritisation heuristic, not a probability of failure or a safety certification.
- The logical fleet is a set of local simulator processes, not a network of real devices. The autonomous operations mode keeps one logical simulated device alive across its internally scheduled episodes.
- The autonomous scheduler chooses faults automatically from its configured pool; the optional manual test bench is for deterministic, user-selected validation cases.

## Change the operating profile

Edit `config/default_profile.json` or use `config/strict_profile.json`. Profiles set detection ranges, timeout windows, recovery limits, retry backoff, risk thresholds and logical fleet settings. Keep mandatory safe-mode guardrails enabled. To generate and serve results with a selected profile, use:

```powershell
python tools/run_advanced.py --profile config/strict_profile.json
python tools/launch_dashboard.py --profile config/strict_profile.json
```

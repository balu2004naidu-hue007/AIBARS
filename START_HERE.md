# AIBARS v2.3.2 — Start Here

AIBARS is a laptop-only embedded-system resilience simulator. The main demonstration is **Autonomous Operations Session**: start one bounded session and let AIBARS monitor telemetry, schedule fault episodes internally, diagnose them, attempt controlled recovery, verify health, and resume monitoring. You do not have to choose each fault.

## Windows quick start

1. Extract the ZIP to a short folder path, for example `C:\AIBARS`.
2. Install:
   - Python 3.10 or newer
   - CMake 3.16 or newer
   - A C++17 compiler (Visual Studio Build Tools with the C++ workload, or MSYS2 UCRT64 GCC)
3. Open the extracted `AIBARS` folder.
4. Double-click `RUN_AIBARS_WINDOWS.bat`.
5. Wait for the build, tests and demo campaign to finish. The local dashboard server starts and automatically opens the dashboard in your default browser.
6. If the browser does not open automatically, open `http://127.0.0.1:8765` in Chrome or Edge.
7. Under **Autonomous Operations Session**, choose **Fixed interval** (e.g. 2.0 seconds) or **Random interval** (e.g. 2.0–5.0 seconds), then click **Start autonomous session**. Do not select a fault. The scheduler selects faults internally.
8. Watch normal telemetry, the next-fault countdown, automatic fault scheduling, detection, diagnosis, recovery, healthy-cycle verification and return to monitoring. The interval is counted as healthy monitoring time after a recovery; detection/recovery time is additional.
9. Use the separate **Fault Injection Test Bench** only when you want to demonstrate one specific known fault.
10. To stop the dashboard server, focus the command window and press `Ctrl+C`.

## PowerShell alternative

Open PowerShell in the extracted project folder and run:

```powershell
python --version
cmake --version
python scripts/run_tests.py
python tools/run_advanced.py
python tools/launch_dashboard.py --open-browser
```

Then open `http://127.0.0.1:8765`.

## Offline dashboard

Open `examples/dashboard.html` in a browser to inspect the saved campaign results and saved autonomous-session demonstration. Offline mode cannot start a new simulation. Use the local server for live sessions.

## What a successful autonomous session looks like

- Status moves from `IDLE` to `MONITORING`.
- Normal telemetry is observed before any fault is scheduled.
- The internal scheduler announces a fault episode without operator selection.
- AIBARS detects and diagnoses the fault.
- The recovery manager attempts a bounded, component-specific action.
- The required consecutive healthy cycles are observed.
- Status returns to `MONITORING`; the same logical device and global tick continue.
- The session ends at its configured cycle/incident limit, on an operator stop, or after safe-mode escalation.

## Important scope note

All devices, sensors, task activity and recovery actions are simulated. The AI classifier is trained and evaluated on generated synthetic telemetry and is advisory only. AIBARS has not been connected to an ECU, FPGA, physical sensor or industrial machine. Your Windows laptop run is the final local acceptance check; the included recorded validation was performed in the development environment.

For a fuller explanation, read `README.md`, `docs/autonomous_mode.md` and `docs/user_guide.md`.

## Dashboard browser does not open automatically?

The Windows batch launcher starts the local service with `--open-browser` and waits one second before asking Windows to open the default browser. The command window must stay open while the dashboard is in use. If no default browser is registered or Windows blocks the handoff, copy `http://127.0.0.1:8765` from the command window into Chrome or Edge.

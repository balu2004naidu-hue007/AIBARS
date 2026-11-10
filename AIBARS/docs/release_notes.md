# AIBARS Release Notes

## v2.3.2 — Automatic dashboard browser launch

- The Windows launcher now starts the local dashboard server with `--open-browser`.
- The dashboard server waits briefly until it is accepting requests, then opens `http://127.0.0.1:8765` in the operating system's default browser.
- If automatic browser launch is unavailable or blocked, the command window prints the address for manual opening.
- The dashboard server remains active until the user presses Ctrl+C in the command window.
- The underlying simulator, autonomous scheduler, AI advisory, recovery policy and manual test bench are unchanged from v2.3.1.
- GCC 14.2 build, CTest and all 24 Python tests pass after the launcher change. Windows default-browser opening must be confirmed on the user's laptop.


## v2.3.1 — MSVC standard-header portability fix

- Added the direct `<sstream>` include to `src/main.cpp`, which defines and uses `std::ostringstream` for telemetry-event formatting.
- This removes reliance on transitive standard-library includes and addresses the MSVC compile diagnostic reported at the telemetry detail stream expression.
- GCC 14.2 and Clang 17 builds, CTest and all 24 Python tests pass after the change.
- MSVC compilation on the target Windows laptop remains to be confirmed by rerunning `RUN_AIBARS_WINDOWS.bat`.


## v2.3.0 — Seconds-based autonomous scheduling and dashboard refinement

- Added user-facing fixed and random fault interval modes in seconds.
- Fixed mode schedules faults after one configured healthy-monitoring interval.
- Random mode selects a seeded interval within the configured range.
- Seconds are converted to monitoring cycles using the telemetry tick interval and rounded up.
- Added next-fault countdown and scheduler interval details to live status.
- Clarified that time spent detecting/recovering is additional to the healthy interval.
- Retained the manual Fault Injection Test Bench for deterministic verification.
- Added unit and API tests for fixed/random intervals, rounding, validation and legacy API compatibility.

## v2.2.0

- Added the persistent autonomous monitoring session, automatic fault scheduler, repeated recovery/verification and resume-monitoring workflow.
- Added separate autonomous and manual test-bench dashboard panels.

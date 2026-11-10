# AIBARS v2.3.2 — Final Validation Summary

**Release:** 2.3.2 — Seconds-Based Autonomous Scheduling and Operations Platform  
**Validation date:** 10 November 2026  
**Scope:** Laptop-only C++/Python software simulation. No physical-hardware validation is claimed.

## Automated software checks

- C++17 core: CTest target passed (nine focused checks inside the core executable).
- Python advanced/integration suite: 24 test methods passed.
- GCC build and test suite passed.
- Clang 17 build, CTest and Python test suite passed.
- Windows-specific path was corrected in v2.1.1; final v2.3.2 acceptance on the user's Windows laptop remains a separate check.

## Autonomous session checks

The C++ `--autonomous` mode was verified with a seeded session that automatically selected three recoverable fault episodes. All three incidents were detected and diagnosed, each recovery passed three consecutive healthy cycles, and normal monitoring resumed between incidents on the same logical simulated device. The global tick counter remained monotonic across monitoring, fault episodes and recovery.

Additional regression cases verified:

- Automatic scheduler selection without a user-supplied scenario name.
- Multiple recoverable episodes in a single session.
- Component-specific task/sensor/communication recovery and continued monitoring.
- Optional critical fault injection and safe-mode session termination.
- Controlled stop-file handling.
- Live dashboard start/status API and streaming black-box events.
- Post-session per-episode AI advisory and risk-triage enrichment.
- GET start rejection and cross-origin launch rejection.

## Manual test-bench and stress campaign

The ten deterministic verification scenarios remain available separately: nominal, sensor timeout, sensor stuck, sensor out of range, communication timeout, primary task hang, secondary task hang, multiple task hangs, multiple faults and recovery failure.

The seeded randomized concurrent recovery regression completed 48 runs with zero invariant failures.

## Saved autonomous dashboard preview

The generated offline dashboard includes a saved autonomous-session run with three internally scheduled fault episodes. In the recorded run, communication timeout, sensor stuck and task hang were each recovered and verified. The same logical simulator session resumed normal monitoring between episodes. AI and risk reports are shown per completed episode.

## AI evaluation qualification

The Gaussian Naive Bayes advisory model was evaluated using generated synthetic labelled telemetry with a stratified 80/20 hold-out split. The reported accuracy is a measure of separation within those generated signatures only. It is not field accuracy and does not establish real-world fault prediction performance. The ML classifier remains advisory; deterministic C++ rules control recovery.

## Seconds-based automatic scheduling checks

- Dashboard supports **Fixed interval** and **Random interval** modes with values entered in seconds.
- Fixed mode maps one interval to equal minimum/maximum monitoring cycles.
- Random mode maps the requested interval range to a seeded uniform cycle range.
- Conversion rounds up to a whole monitoring tick, preventing earlier-than-requested scheduling.
- At a 100 ms telemetry tick, fixed 2.0 seconds maps to 20 healthy monitoring cycles; random 2.0–5.0 seconds maps to 20–50 cycles.
- A dedicated fixed-2.0-second smoke test passed: the scheduler recorded a 20-cycle / 2.000-second healthy interval at a 100 ms tick, then activated the fault after the documented five-sample warm-up and verified recovery after three healthy cycles. The complete process took approximately 3.115 seconds including warm-up, detection and recovery.
- The interval is measured as healthy monitoring time after recovery completion. Fault detection and recovery duration is additional elapsed time.
- Status snapshots report interval mode, configured/effective interval, next fault cycle and estimated time remaining.
- Python unit tests cover fixed/random conversions, rounding, invalid values and legacy cycle-based API compatibility.

## Dashboard and API checks

- Dashboard HTML generated with a professional Autonomous Operations Session, seconds-based Fixed/Random scheduling controls, next-fault countdown and a separate manual Fault Injection Test Bench.
- Inline JavaScript syntax checked with Node.js.
- Local dashboard health endpoint and autonomous session start/status flow tested.
- Live autonomous events streamed from the C++ `events.jsonl` file.
- Session completion returned per-episode ML advisory and risk-triage data.
- Controlled stop endpoint and origin validation covered by tests.

## Acceptance items still requiring the user's machine

1. Run `RUN_AIBARS_WINDOWS.bat` on the target Windows laptop.
2. Open the live dashboard in Chrome or Edge and start an autonomous session.
3. Confirm that automatic fault scheduling, recovery and monitoring resumption appear correctly on that machine.
4. Resolve any local compiler or PATH differences if they arise.

## Explicit non-claims

No physical sensors, ECU, FPGA, HIL rig, vehicle, industrial machine, real labelled fault dataset, functional-safety certification or production deployment has been tested. All device and fault behaviour is simulated. The logical single-device autonomous session preserves simulator state and ticks; the separate fleet campaign uses concurrent local simulator processes, not a physical distributed system.
## MSVC portability patch (v2.3.2)

The Windows screenshot showed an MSVC overload-resolution failure at the `std::ostringstream` telemetry formatting expression in `src/main.cpp`. The translation unit used `std::ostringstream` without directly including its defining `<sstream>` header, relying on transitive includes that are not portable across standard-library implementations. A direct `#include <sstream>` was added. GCC 14.2 and Clang 17 builds, CTest and all 24 Python tests pass with this change. MSVC itself is not available in the development environment used for this release, so the user's Windows rebuild is still required to confirm the fix with their installed MSVC toolset.

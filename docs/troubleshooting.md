# AIBARS Troubleshooting

## `python` is not recognized

Install Python 3.10 or newer and enable the option to add Python to PATH. Reopen PowerShell after installation.

## `cmake` is not recognized

Install CMake 3.16 or newer and add it to PATH. Check with `cmake --version`.

## CMake cannot find a C++ compiler

Install a C++17 toolchain. On Windows, Visual Studio Build Tools with **Desktop development with C++** or MSYS2 UCRT64 GCC can be used. Reopen the terminal configured for that toolchain before running the launcher.

## CTest says "Test not available without configuration" on Visual Studio

Visual Studio uses a multi-configuration CMake generator. Build with `--config Release` and run CTest with `-C Release`. The supplied `scripts/run_tests.py` includes both options. If you run CTest manually, use:

```powershell
ctest --test-dir build -C Release --output-on-failure
```

## Build directory seems stale

Close any active AIBARS dashboard server. Delete the generated `build` folder and run `python scripts/run_tests.py` again. Do not delete `src`, `include`, `tests`, `config`, `docs` or `artifacts`.

## Port 8765 is already in use

Stop the older dashboard server with Ctrl+C. Alternatively start AIBARS on another local port:

```powershell
python tools/launch_dashboard.py --port 8766
```

Then open `http://127.0.0.1:8766`.

## Dashboard shows only saved results

The offline file opened with `file://` is a read-only playback view. To execute new scenarios, start the local Python server and open its `http://127.0.0.1` address.

## The dashboard says the simulator is not built

Run `python tools/run_advanced.py` from the project root. This configures and builds the C++ simulator and regenerates the campaign artifacts.

## Tests fail after editing a profile

Restore `config/default_profile.json` and rerun the tests. Confirm timeout windows are integers from 1 to 1000, stuck sample count is from 2 to 1000, ranges are finite and ordered, device IDs are unique, and mandatory safe-mode guardrails remain true.

## Safety and deployment boundary

All device signals, task faults, communication failures and recovery actions are simulated. The local server is loopback-only and intended for local development. The system is not a certified safety controller and must not be connected to real actuators or relied on for machine protection.

## C++ test fails while removing `aibars_cpp_test_recovery` on Windows

Use the v2.1.1 package. In v2.1.0, the test removed its output directory while the black-box logger still had `events.jsonl` open. Windows correctly refused to delete the open file. v2.1.1 uses a unique temporary directory per test and closes the logger before directory cleanup. Do not try to fix this by repeatedly deleting the Temp folder or disabling antivirus.

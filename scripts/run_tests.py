#!/usr/bin/env python3
"""Configure, build and run AIBARS C++ and Python integration tests."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def run(command: list[str], *, cwd: pathlib.Path = ROOT, env=None) -> None:
    print("\n> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    try:
        run(["cmake", "-S", str(ROOT), "-B", str(BUILD), "-DCMAKE_BUILD_TYPE=Release"])
        run(["cmake", "--build", str(BUILD), "--config", "Release", "--parallel"])
        run(["ctest", "--test-dir", str(BUILD), "-C", "Release", "--output-on-failure"])
        candidates = [BUILD / "aibars_sim", BUILD / "aibars_sim.exe", BUILD / "Release" / "aibars_sim.exe", BUILD / "Release" / "aibars_sim"]
        binary = next((path for path in candidates if path.is_file()), None)
        if binary is None:
            raise FileNotFoundError("Could not locate the built aibars_sim executable")
        env = os.environ.copy()
        env["AIBARS_BINARY"] = str(binary)
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], env=env)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"TEST FAILURE: {error}", file=sys.stderr)
        return 1
    print("\nAIBARS VALIDATION: ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

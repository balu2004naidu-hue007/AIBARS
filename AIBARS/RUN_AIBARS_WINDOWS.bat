@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo AIBARS v2.3.2 - MSVC portability fix and autonomous operations
echo ==============================================
python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or newer is required'"
if errorlevel 1 (
  echo Python is not available on PATH.
  pause
  exit /b 1
)
cmake --version
if errorlevel 1 (
  echo CMake is not available on PATH.
  pause
  exit /b 1
)
echo.
echo [1/3] Building and running the complete automated test suite...
python scripts\run_tests.py
if errorlevel 1 (
  echo AIBARS test suite failed. Review the output above.
  pause
  exit /b 1
)
echo.
echo [2/3] Running manual test campaigns, autonomous demo, AI evaluation and dashboard generation...
python tools\run_advanced.py
if errorlevel 1 (
  echo AIBARS campaign failed. Review the output above.
  pause
  exit /b 1
)
echo.
echo [3/3] Starting the local dashboard with autonomous session controls...
python tools\launch_dashboard.py --open-browser
pause

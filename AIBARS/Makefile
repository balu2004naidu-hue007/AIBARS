PYTHON ?= python3
CMAKE ?= cmake

.PHONY: test demo dashboard clean

test:
	$(PYTHON) scripts/run_tests.py

demo:
	$(PYTHON) tools/run_advanced.py

dashboard:
	$(PYTHON) tools/launch_dashboard.py

clean:
	$(CMAKE) -E rm -rf build runs/live

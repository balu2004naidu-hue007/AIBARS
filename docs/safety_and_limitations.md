# Safety Scope and Limitations

AIBARS is a software engineering and verification project, not a certified safety controller.

- All telemetry, devices and fault events are simulated.
- Sensor/communication/task recovery operations are simulated state transitions.
- Logical device fleet runs are independent local processes, not physical network nodes.
- The local dashboard API is for loopback development only and has no authentication.
- The Gaussian Naive Bayes classifier is trained and tested on generated synthetic telemetry signatures. Hold-out metrics are not field performance.
- Model scores are not calibrated probabilities; rule-based diagnosis remains authoritative.
- Risk scores are triage heuristics, not quantitative safety analysis or calibrated failure probability.
- Thresholds are illustrative and must be engineered and validated for a real target.
- No physical hardware, ECU, FPGA, HIL, industrial system, formal-methods, real-time deadline, SIL/ASIL or safety-certification validation is claimed.
- Real deployment would require target-specific drivers, concurrency/resource analysis, independent validation, security review, safe-state design and applicable functional-safety processes.

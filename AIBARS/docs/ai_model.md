# AI Advisory Fault Classifier

## Purpose

The classifier assists diagnosis by ranking six possible system states: NORMAL, SENSOR_TIMEOUT, SENSOR_STUCK, SENSOR_OUT_OF_RANGE, COMMUNICATION_TIMEOUT and TASK_HANG. It does not command recovery. The C++ rule-based diagnosis and recovery policy remain authoritative.

## Algorithm

A Gaussian Naive Bayes classifier is implemented using Python's standard library. The ten input features are extracted from JSONL telemetry and fault evidence: temperature age, temperature stale flag, communication heartbeat age, primary task stall duration, temperature range deviation, stuck-sensor flag, voltage range deviation, current range deviation, communication-loss flag and secondary task stall duration. Engineering-range deviation uses the active profile limits rather than fixed sensor constants.

## Dataset and evaluation

`ml_classifier.py` deterministically generates labelled synthetic telemetry signatures for each class. Training validates class labels and finite feature values; inference validates vector size and finite inputs; loading a persisted model validates feature schema, dimensions, positive variances and class-prior totals. The default profile trains on 80% of the samples and reports results on a stratified 20% hold-out set. The seed and sample counts are recorded in `artifacts/ml_evaluation.json`. Model parameters are saved in `artifacts/fault_classifier_model.json`.

The model metrics currently represent separation of this generated synthetic dataset only. Because the dataset is synthetic and generated from predefined fault signatures, strong or perfect test performance is not evidence of field accuracy. No physical telemetry dataset is included, and no field accuracy claim is justified.

## Safety boundary

- ML probabilities are advisory ranking scores, not calibrated probabilities.
- Deterministic C++ rules validate fault evidence.
- Compound-fault logic overrides single-class ML advice.
- Recovery actions are selected by the deterministic policy, not by the ML model.
- If used with real devices in the future, the model must be retrained and independently evaluated on representative labelled data; false-positive/negative analysis, drift checks and a safety review are required.

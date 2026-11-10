"""Reproducible Gaussian Naive Bayes classifier using Python standard library only.

Training/evaluation data are synthetic and generated from documented fault signatures.
The model is an advisory diagnostic aid; deterministic C++ safety rules govern recovery.
"""
from __future__ import annotations
import csv
import json
import math
import random
import re
from pathlib import Path
from typing import Iterable

FEATURES = [
    "temperature_age_ticks", "temperature_stale_flag", "communication_age_ticks",
    "primary_task_stall_ticks", "temperature_range_deviation_c", "temperature_stuck_flag",
    "voltage_range_deviation_v", "current_range_deviation_a", "communication_loss_flag",
    "secondary_task_stall_ticks",
]
CLASSES = ["NORMAL", "SENSOR_TIMEOUT", "SENSOR_STUCK", "SENSOR_OUT_OF_RANGE", "COMMUNICATION_TIMEOUT", "TASK_HANG"]
FAULT_TO_CLASS = {
    "SENSOR_TIMEOUT": "SENSOR_TIMEOUT", "SENSOR_STUCK": "SENSOR_STUCK",
    "SENSOR_OUT_OF_RANGE": "SENSOR_OUT_OF_RANGE",
    "COMMUNICATION_TIMEOUT": "COMMUNICATION_TIMEOUT", "TASK_HANG": "TASK_HANG",
}


def _sample(label: str, rng: random.Random) -> list[float]:
    # Feature distributions intentionally overlap. They are synthetic engineering
    # signatures for exercising the advisory pipeline, not calibrated sensor data.
    means = {
        "NORMAL": [0.2, 0.0, 0.2, 0.1, 0.4, 0.0, 0.1, 0.1, 0.0, 0.1],
        "SENSOR_TIMEOUT": [3.8, 1.0, 0.2, 0.1, 0.4, 0.0, 0.1, 0.1, 0.0, 0.1],
        "SENSOR_STUCK": [0.2, 0.0, 0.2, 0.1, 0.4, 1.0, 0.1, 0.1, 0.0, 0.1],
        "SENSOR_OUT_OF_RANGE": [0.2, 0.0, 0.2, 0.1, 25.0, 0.0, 2.0, 8.0, 0.0, 0.1],
        "COMMUNICATION_TIMEOUT": [0.2, 0.0, 3.8, 0.1, 0.4, 0.0, 0.1, 0.1, 1.0, 0.1],
        "TASK_HANG": [0.2, 0.0, 0.2, 3.8, 0.4, 0.0, 0.1, 0.1, 0.0, 2.0],
    }
    spreads = [0.75, 0.12, 0.75, 0.9, 5.0, 0.12, 0.8, 2.5, 0.12, 1.0]
    out = []
    for idx, (mean, spread) in enumerate(zip(means[label], spreads)):
        value = rng.gauss(mean, spread)
        value = max(0.0, value)
        out.append(value)
    return out

def generate_dataset(samples_per_class: int = 240, seed: int = 20261109) -> list[tuple[str, list[float]]]:
    rng = random.Random(seed)
    rows = [(label, _sample(label, rng)) for label in CLASSES for _ in range(samples_per_class)]
    rng.shuffle(rows)
    return rows


class GaussianNaiveBayes:
    def __init__(self) -> None:
        self.classes: list[str] = []
        self.means: dict[str, list[float]] = {}
        self.variances: dict[str, list[float]] = {}
        self.priors: dict[str, float] = {}

    def fit(self, rows: Iterable[tuple[str, list[float]]]) -> None:
        data = list(rows)
        if not data:
            raise ValueError("Cannot train classifier on an empty dataset")
        grouped: dict[str, list[list[float]]] = {}
        for label, vector in data:
            if label not in CLASSES:
                raise ValueError(f"Unsupported classifier label: {label}")
            if len(vector) != len(FEATURES):
                raise ValueError("Feature vector has incorrect length")
            if any(not math.isfinite(float(value)) for value in vector):
                raise ValueError("Feature vector values must be finite")
            grouped.setdefault(label, []).append([float(value) for value in vector])
        self.classes = sorted(grouped)
        total = len(data)
        for label, vectors in grouped.items():
            self.priors[label] = len(vectors) / total
            means = [sum(row[i] for row in vectors) / len(vectors) for i in range(len(FEATURES))]
            variances = []
            for i, mean in enumerate(means):
                variance = sum((row[i] - mean) ** 2 for row in vectors) / max(1, len(vectors) - 1)
                variances.append(max(variance, 1e-4))
            self.means[label] = means
            self.variances[label] = variances

    def predict_proba(self, vector: list[float]) -> dict[str, float]:
        if not self.classes:
            raise RuntimeError("Classifier has not been trained")
        if len(vector) != len(FEATURES):
            raise ValueError(f"Expected {len(FEATURES)} features, received {len(vector)}")
        if any(not math.isfinite(float(value)) for value in vector):
            raise ValueError("Prediction features must be finite")
        log_scores: dict[str, float] = {}
        for label in self.classes:
            score = math.log(self.priors[label])
            for i, value in enumerate(vector):
                mean = self.means[label][i]
                variance = self.variances[label][i]
                score += -0.5 * math.log(2.0 * math.pi * variance) - ((value - mean) ** 2) / (2.0 * variance)
            log_scores[label] = score
        peak = max(log_scores.values())
        exps = {label: math.exp(score - peak) for label, score in log_scores.items()}
        total = sum(exps.values())
        return {label: value / total for label, value in exps.items()}

    def predict(self, vector: list[float]) -> str:
        probabilities = self.predict_proba(vector)
        return max(probabilities, key=probabilities.get)

    def to_dict(self) -> dict:
        return {"algorithm": "Gaussian Naive Bayes", "features": FEATURES, "classes": self.classes,
                "means": self.means, "variances": self.variances, "priors": self.priors,
                "training_data": "synthetic_fault_signatures", "safety_role": "advisory_only"}

    @classmethod
    def from_dict(cls, data: dict) -> "GaussianNaiveBayes":
        if data.get("features") != FEATURES or data.get("algorithm") != "Gaussian Naive Bayes":
            raise ValueError("Model feature schema or algorithm does not match this AIBARS version")
        classes = data.get("classes")
        means, variances, priors = data.get("means"), data.get("variances"), data.get("priors")
        if not isinstance(classes, list) or not classes or any(c not in CLASSES for c in classes):
            raise ValueError("Model contains an invalid class list")
        if not all(isinstance(x, dict) and set(x) == set(classes) for x in (means, variances, priors)):
            raise ValueError("Model parameters do not match the class list")
        for label in classes:
            if len(means[label]) != len(FEATURES) or len(variances[label]) != len(FEATURES):
                raise ValueError(f"Model parameters for {label} have an invalid feature count")
            if any(not math.isfinite(float(v)) for v in means[label]):
                raise ValueError(f"Model means for {label} must be finite")
            if any(not math.isfinite(float(v)) or float(v) <= 0.0 for v in variances[label]):
                raise ValueError(f"Model variances for {label} must be finite and positive")
            if not math.isfinite(float(priors[label])) or not 0.0 < float(priors[label]) <= 1.0:
                raise ValueError(f"Model prior for {label} is invalid")
        if abs(sum(float(priors[label]) for label in classes) - 1.0) > 1e-6:
            raise ValueError("Model class priors must sum to one")
        model = cls()
        model.classes = list(classes)
        model.means = {k: [float(v) for v in means[k]] for k in classes}
        model.variances = {k: [float(v) for v in variances[k]] for k in classes}
        model.priors = {k: float(priors[k]) for k in classes}
        return model


def train_and_evaluate(samples_per_class: int = 240, seed: int = 20261109) -> tuple[GaussianNaiveBayes, dict]:
    rows = generate_dataset(samples_per_class, seed)
    rng = random.Random(seed + 1)
    grouped: dict[str, list[list[float]]] = {}
    for label, vector in rows:
        grouped.setdefault(label, []).append(vector)
    train: list[tuple[str, list[float]]] = []
    test: list[tuple[str, list[float]]] = []
    for label, vectors in grouped.items():
        rng.shuffle(vectors)
        cut = int(len(vectors) * 0.8)
        train.extend((label, v) for v in vectors[:cut])
        test.extend((label, v) for v in vectors[cut:])
    model = GaussianNaiveBayes()
    model.fit(train)
    matrix = {actual: {predicted: 0 for predicted in CLASSES} for actual in CLASSES}
    correct = 0
    for actual, vector in test:
        predicted = model.predict(vector)
        matrix[actual][predicted] += 1
        correct += int(actual == predicted)
    per_class = {}
    for label in CLASSES:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in CLASSES if other != label)
        fn = sum(matrix[label][other] for other in CLASSES if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[label].values())}
    report = {
        "algorithm": "Gaussian Naive Bayes",
        "feature_names": FEATURES,
        "classes": CLASSES,
        "dataset": "synthetic labelled fault telemetry; generated deterministically",
        "samples_total": len(rows), "training_samples": len(train), "test_samples": len(test),
        "split": "stratified 80/20 hold-out", "seed": seed,
        "accuracy": correct / len(test), "confusion_matrix": matrix,
        "per_class_metrics": per_class,
        "limitations": ["Metrics measure separation of generated synthetic signatures only.",
                        "They are not field accuracy and do not establish real-world fault prediction performance.",
                        "Classifier output is advisory; deterministic C++ policy controls recovery."],
    }
    return model, report


def save_model_and_report(output: Path, samples_per_class: int = 240) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    model, report = train_and_evaluate(samples_per_class)
    dataset = generate_dataset(samples_per_class)
    with (output / "synthetic_fault_dataset.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["label", *FEATURES])
        for label, vector in dataset:
            writer.writerow([label, *vector])
    (output / "fault_classifier_model.json").write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")
    (output / "ml_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def extract_features(run: dict, profile: dict | None = None) -> list[float]:
    events = run.get("events", [])
    fault_codes = set(run.get("summary", {}).get("detected_faults", []))
    text = "\n".join(str(e.get("detail", "")) for e in events)

    def max_match(pattern: str) -> float:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        values: list[float] = []
        for match in matches:
            if isinstance(match, tuple):
                values.extend(float(value) for value in match if value)
            elif match:
                values.append(float(match))
        return max(values, default=0.0)

    detection = (profile or {}).get("detection", {})
    t_min = float(detection.get("minimum_temperature_c", -40.0))
    t_max = float(detection.get("maximum_temperature_c", 125.0))
    v_min = float(detection.get("minimum_voltage_v", 9.0))
    v_max = float(detection.get("maximum_voltage_v", 36.0))
    i_min = float(detection.get("minimum_current_a", 0.0))
    i_max = float(detection.get("maximum_current_a", 100.0))

    temp_age = max_match(r"temperature freshness=[^,]+,\s*age=([0-9.]+)|temperature_age=([0-9.]+)")
    stale_flag = 1.0 if re.search(r"temperature freshness=stale", text, flags=re.IGNORECASE) else 0.0
    comm_age = max_match(r"communication status=[^,]+,\s*heartbeat age=([0-9.]+)|communication_age=([0-9.]+)")
    primary_stall = max_match(r"task=PRIMARY_CONTROL_LOOP progress stalled for\s+([0-9.]+)|primary_task_stall=([0-9.]+)")
    secondary_stall = max_match(r"task=SECONDARY_TELEMETRY_TASK progress stalled for\s+([0-9.]+)|secondary_task_stall=([0-9.]+)")
    temps = [float(v) for v in re.findall(r"temperature=([-+]?[0-9]*\.?[0-9]+)\s*C", text)]
    volts = [float(v) for v in re.findall(r"voltage=([-+]?[0-9]*\.?[0-9]+)\s*V", text)]
    currents = [float(v) for v in re.findall(r"current=([-+]?[0-9]*\.?[0-9]+)\s*A", text)]
    temp_deviation = max((max(t_min - v, v - t_max, 0.0) for v in temps), default=0.0)
    voltage_deviation = max((max(v_min - v, v - v_max, 0.0) for v in volts), default=0.0)
    current_deviation = max((max(i_min - v, v - i_max, 0.0) for v in currents), default=0.0)
    return [temp_age, stale_flag, comm_age, primary_stall, temp_deviation,
            1.0 if "SENSOR_STUCK" in fault_codes else 0.0,
            voltage_deviation, current_deviation,
            1.0 if "COMMUNICATION_TIMEOUT" in fault_codes else 0.0,
            secondary_stall]

def classify_run(run: dict, model: GaussianNaiveBayes, profile: dict | None = None) -> dict:
    faults = run.get("summary", {}).get("detected_faults", [])
    if len(faults) > 1:
        return {"prediction": "COMPOUND_FAULT", "confidence": 1.0, "probabilities": {},
                "features": dict(zip(FEATURES, extract_features(run, profile))),
                "explanation": "Multiple deterministic fault rules fired; compound-fault handling overrides single-class ML advice."}
    vector = extract_features(run, profile)
    probabilities = model.predict_proba(vector)
    prediction = max(probabilities, key=probabilities.get)
    return {"prediction": prediction, "confidence": probabilities[prediction],
            "probabilities": probabilities, "features": dict(zip(FEATURES, vector)),
            "explanation": "Advisory Gaussian Naive Bayes classification from extracted telemetry features; recovery remains governed by deterministic policy."}

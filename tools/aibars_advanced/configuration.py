"""Validated JSON configuration and simulator argument mapping."""
from __future__ import annotations
import json
import math
from pathlib import Path

DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "config" / "default_profile.json"


def load_profile(path: Path | str | None = None) -> dict:
    source = Path(path) if path else DEFAULT_PROFILE
    data = json.loads(source.read_text(encoding="utf-8"))
    required = {"detection", "recovery", "risk", "fleet"}
    missing = required.difference(data)
    if missing:
        raise ValueError(f"Configuration missing sections: {sorted(missing)}")
    detection = data["detection"]
    numeric_detection = [
        "minimum_temperature_c", "maximum_temperature_c", "minimum_voltage_v",
        "maximum_voltage_v", "minimum_current_a", "maximum_current_a",
        "sensor_timeout_ticks", "communication_timeout_ticks", "stuck_sample_count",
        "task_stall_ticks",
    ]
    for key in numeric_detection:
        value = detection.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"detection.{key} must be finite and numeric")
    for low, high in (("minimum_temperature_c", "maximum_temperature_c"),
                      ("minimum_voltage_v", "maximum_voltage_v"),
                      ("minimum_current_a", "maximum_current_a")):
        if detection[low] >= detection[high]:
            raise ValueError(f"detection.{low} must be less than {high}")
    for key in ("sensor_timeout_ticks", "communication_timeout_ticks", "task_stall_ticks"):
        if not isinstance(detection[key], int) or detection[key] < 1 or detection[key] > 1000:
            raise ValueError(f"detection.{key} must be an integer from 1 to 1000")
    if not isinstance(detection["stuck_sample_count"], int) or not 2 <= detection["stuck_sample_count"] <= 1000:
        raise ValueError("detection.stuck_sample_count must be an integer from 2 to 1000")
    recovery = data["recovery"]
    for guardrail in ("safe_mode_on_compound_fault", "safe_mode_on_recovery_exhaustion"):
        if recovery.get(guardrail) is not True:
            raise ValueError(f"recovery.{guardrail} is a mandatory containment guardrail and must remain true")
    for key in ("maximum_attempts", "required_healthy_cycles"):
        if not isinstance(recovery.get(key), int) or recovery[key] < 1:
            raise ValueError(f"recovery.{key} must be a positive integer")
    if recovery["maximum_attempts"] > 20 or recovery["required_healthy_cycles"] > 1000:
        raise ValueError("recovery attempt/cycle limits exceed supported bounds")
    if not isinstance(recovery.get("retry_backoff_ticks"), int) or not 0 <= recovery["retry_backoff_ticks"] <= 1000:
        raise ValueError("recovery.retry_backoff_ticks must be an integer from 0 to 1000")
    risk = data["risk"]
    if not (0 <= risk["low_max"] < risk["moderate_max"] < risk["high_max"] <= 100):
        raise ValueError("risk bands must be ordered between 0 and 100")
    for key in ("low_max", "moderate_max", "high_max"):
        if isinstance(risk.get(key), bool) or not isinstance(risk.get(key), (int, float)):
            raise ValueError(f"risk.{key} must be numeric")
    impact_weights = risk.get("impact", {})
    if not isinstance(impact_weights, dict) or not impact_weights:
        raise ValueError("risk.impact must be a non-empty object")
    for cause, impact in impact_weights.items():
        if isinstance(impact, bool) or not isinstance(impact, (int, float)) or not math.isfinite(float(impact)) or not 0.0 <= float(impact) <= 1.0:
            raise ValueError(f"risk.impact.{cause} must be finite and between 0 and 1")
    workers = data["fleet"].get("workers", 1)
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1 or workers > 32:
        raise ValueError("fleet.workers must be an integer between 1 and 32")
    device_ids = data["fleet"].get("device_ids", [])
    if not isinstance(device_ids, list) or any(not isinstance(x, str) or not x.strip() for x in device_ids):
        raise ValueError("fleet.device_ids must be a list of non-empty strings")
    if len(set(device_ids)) != len(device_ids):
        raise ValueError("fleet.device_ids must be unique")
    if device_ids and len(device_ids) < workers:
        raise ValueError("fleet.device_ids must contain at least as many IDs as fleet.workers")
    return data


def simulator_args(profile: dict) -> list[str]:
    det = profile["detection"]
    rec = profile["recovery"]
    mapping = {
        "--temp-min-c": det["minimum_temperature_c"],
        "--temp-max-c": det["maximum_temperature_c"],
        "--voltage-min-v": det["minimum_voltage_v"],
        "--voltage-max-v": det["maximum_voltage_v"],
        "--current-min-a": det["minimum_current_a"],
        "--current-max-a": det["maximum_current_a"],
        "--sensor-timeout-ticks": det["sensor_timeout_ticks"],
        "--communication-timeout-ticks": det["communication_timeout_ticks"],
        "--stuck-samples": det["stuck_sample_count"],
        "--task-stall-ticks": det["task_stall_ticks"],
        "--recovery-attempts": rec["maximum_attempts"],
        "--verify-cycles": rec["required_healthy_cycles"],
        "--retry-backoff-ticks": rec["retry_backoff_ticks"],
    }
    return [item for pair in mapping.items() for item in (pair[0], str(pair[1]))]

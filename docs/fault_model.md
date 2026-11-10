# Fault Model and Detection Rules

AIBARS v2.3.2 provides deterministic fault injection in a simulated embedded environment. The C++ detector evaluates each telemetry sample and can report more than one independent fault in the same observation window.

| Fault code | Detection rule | Evidence recorded | Default severity |
|---|---|---|---|
| `SENSOR_TIMEOUT` | Temperature data age reaches the configured timeout ticks; a single missed update is tolerated until the age window expires | Fresh/stale state and data age | High |
| `SENSOR_STUCK` | Configured number of consecutive fresh samples carry the same temperature within 0.0001 °C | Repeated-value window | Medium |
| `SENSOR_OUT_OF_RANGE` | Temperature, voltage or current is outside configured engineering limits | Actual telemetry values | High |
| `COMMUNICATION_TIMEOUT` | Communication heartbeat age reaches the configured timeout; an initial missed heartbeat is not immediately declared a timeout | Heartbeat age | High |
| `TASK_HANG` | Any monitored task progress is not advancing and its accumulated stall age reaches configured threshold | Task identity and stall age | High |

The profile is in `config/default_profile.json`. The example limits are demonstration values, not calibrated electrical or thermal operating limits. They must not be reused for a real device without target-specific requirements and validation.

## Compound conditions

When more than one independent fault rule fires on the same sample, the diagnosis engine creates `COMPOUND_FAULT`, assigns Critical severity and recommends safe mode. This is a deliberate containment policy: the platform avoids attempting independent resets while the overall condition may be interacting or uncertain.

## Detector state

The detector maintains prior temperature and repeated-sample count for the stuck-sensor rule. Its state is reset before post-recovery verification so pre-fault samples do not contaminate the healthy-cycle window.

## Detection versus ML classification

The C++ detector is authoritative for whether a configured fault condition has been observed. The Python Gaussian Naive Bayes classifier provides an advisory ranking among known single-fault classes based on extracted telemetry features. The model cannot replace the detector or authorise recovery.

## Multiple task health monitors

The simulator models a primary control-loop task and a secondary telemetry task. A single task stall can be diagnosed and recovered independently. If both task monitors stall in the same observation window, the detector reports two task-fault records and the diagnosis engine escalates to `COMPOUND_FAULT` safe mode. These are simulated task-health signals, not operating-system threads running on a target RTOS.

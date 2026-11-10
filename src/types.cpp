#include "aibars/types.hpp"

namespace aibars {

std::string toString(Scenario value) {
    switch (value) {
        case Scenario::Nominal: return "nominal";
        case Scenario::SensorTimeout: return "sensor_timeout";
        case Scenario::SensorStuck: return "sensor_stuck";
        case Scenario::SensorOutOfRange: return "sensor_out_of_range";
        case Scenario::CommunicationTimeout: return "communication_timeout";
        case Scenario::TaskHang: return "task_hang";
        case Scenario::SecondaryTaskHang: return "secondary_task_hang";
        case Scenario::MultipleTaskHangs: return "multiple_task_hangs";
        case Scenario::MultipleFaults: return "multiple_faults";
        case Scenario::RecoveryFailure: return "recovery_failure";
    }
    return "unknown";
}

std::string toString(FaultCode value) {
    switch (value) {
        case FaultCode::SensorTimeout: return "SENSOR_TIMEOUT";
        case FaultCode::SensorStuck: return "SENSOR_STUCK";
        case FaultCode::SensorOutOfRange: return "SENSOR_OUT_OF_RANGE";
        case FaultCode::CommunicationTimeout: return "COMMUNICATION_TIMEOUT";
        case FaultCode::TaskHang: return "TASK_HANG";
    }
    return "UNKNOWN_FAULT";
}

std::string toString(Severity value) {
    switch (value) {
        case Severity::Low: return "LOW";
        case Severity::Medium: return "MEDIUM";
        case Severity::High: return "HIGH";
        case Severity::Critical: return "CRITICAL";
    }
    return "UNKNOWN";
}

std::string toString(SystemMode value) {
    switch (value) {
        case SystemMode::Normal: return "NORMAL";
        case SystemMode::Recovering: return "RECOVERING";
        case SystemMode::Degraded: return "DEGRADED";
        case SystemMode::SafeMode: return "SAFE_MODE";
    }
    return "UNKNOWN";
}

std::string toString(RecoveryAction value) {
    switch (value) {
        case RecoveryAction::None: return "NONE";
        case RecoveryAction::RestartSensor: return "RESTART_SENSOR";
        case RecoveryAction::ReinitializeSensor: return "REINITIALIZE_SENSOR";
        case RecoveryAction::QuarantineSensor: return "QUARANTINE_SENSOR";
        case RecoveryAction::RestartCommunication: return "RESTART_COMMUNICATION";
        case RecoveryAction::RestartTask: return "RESTART_TASK";
        case RecoveryAction::EnterSafeMode: return "ENTER_SAFE_MODE";
    }
    return "UNKNOWN";
}

std::string toString(RecoveryStatus value) {
    switch (value) {
        case RecoveryStatus::NotRequired: return "NOT_REQUIRED";
        case RecoveryStatus::Verified: return "VERIFIED";
        case RecoveryStatus::Failed: return "FAILED";
        case RecoveryStatus::SafeModeEntered: return "SAFE_MODE_ENTERED";
    }
    return "UNKNOWN";
}

} // namespace aibars

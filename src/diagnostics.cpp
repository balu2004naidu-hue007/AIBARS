#include "aibars/diagnostics.hpp"

namespace aibars {

Diagnosis ExplainableDiagnosisEngine::diagnose(const std::vector<Fault>& faults) const {
    Diagnosis result;
    result.faults = faults;
    if (faults.empty()) {
        result.primary_cause = "NO_FAULT_DETECTED";
        result.rationale = "No configured fault rule was triggered by the observed telemetry.";
        return result;
    }

    if (faults.size() > 1U) {
        result.primary_cause = "COMPOUND_FAULT";
        result.severity = Severity::Critical;
        result.rule_match_score = 0.97;
        result.recommended_action = RecoveryAction::EnterSafeMode;
        result.rationale = "More than one independent fault rule fired in the same observation window; "
                           "the system chooses containment instead of attempting isolated recovery.";
        return result;
    }

    const Fault& fault = faults.front();
    result.severity = fault.severity;
    switch (fault.code) {
        case FaultCode::SensorTimeout:
            result.primary_cause = "SENSOR_DATA_TIMEOUT";
            result.rule_match_score = 0.94;
            result.recommended_action = RecoveryAction::RestartSensor;
            result.rationale = "Temperature-data age reached the configured freshness timeout; "
                               "restart the simulated sensor interface and verify fresh samples.";
            break;
        case FaultCode::SensorStuck:
            result.primary_cause = "SENSOR_STUCK_AT";
            result.rule_match_score = 0.90;
            result.recommended_action = RecoveryAction::ReinitializeSensor;
            result.rationale = "The temperature value remained unchanged across the configured number "
                               "of consecutive fresh samples; reinitialize the simulated sensor.";
            break;
        case FaultCode::SensorOutOfRange:
            result.primary_cause = "SENSOR_VALUE_OUT_OF_RANGE";
            result.rule_match_score = 0.99;
            result.recommended_action = RecoveryAction::QuarantineSensor;
            result.rationale = "At least one telemetry value exceeded its configured engineering range; "
                               "quarantine the invalid input and reinitialize the simulated sensor path.";
            break;
        case FaultCode::CommunicationTimeout:
            result.primary_cause = "COMMUNICATION_HEARTBEAT_TIMEOUT";
            result.rule_match_score = 0.95;
            result.recommended_action = RecoveryAction::RestartCommunication;
            result.rationale = "The communication heartbeat age reached the configured timeout; "
                               "restart the simulated communication interface and verify heartbeat recovery.";
            break;
        case FaultCode::TaskHang:
            result.primary_cause = "TASK_PROGRESS_FAILURE";
            result.rule_match_score = 0.95;
            result.recommended_action = RecoveryAction::RestartTask;
            result.rationale = "The task progress indicator has not advanced within the configured "
                               "monitoring window; restart the simulated task.";
            break;
    }
    return result;
}

} // namespace aibars

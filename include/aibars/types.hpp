#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace aibars {

enum class Scenario {
    Nominal,
    SensorTimeout,
    SensorStuck,
    SensorOutOfRange,
    CommunicationTimeout,
    TaskHang,
    SecondaryTaskHang,
    MultipleTaskHangs,
    MultipleFaults,
    RecoveryFailure
};

enum class FaultCode {
    SensorTimeout,
    SensorStuck,
    SensorOutOfRange,
    CommunicationTimeout,
    TaskHang
};

enum class Severity { Low, Medium, High, Critical };
enum class SystemMode { Normal, Recovering, Degraded, SafeMode };
enum class RecoveryAction {
    None,
    RestartSensor,
    ReinitializeSensor,
    QuarantineSensor,
    RestartCommunication,
    RestartTask,
    EnterSafeMode
};

enum class RecoveryStatus { NotRequired, Verified, Failed, SafeModeEntered };

struct Telemetry {
    std::uint64_t tick{0};
    double temperature_c{0.0};
    double voltage_v{0.0};
    double current_a{0.0};
    std::uint32_t temperature_age_ticks{0};
    std::uint32_t communication_age_ticks{0};
    std::uint32_t task_stall_ticks{0};
    std::uint32_t secondary_task_stall_ticks{0};
    bool temperature_fresh{true};
    bool communication_ok{true};
    bool task_progressing{true};
    bool secondary_task_progressing{true};
};

struct Fault {
    FaultCode code;
    Severity severity;
    std::string evidence;
};

struct Diagnosis {
    std::string primary_cause;
    Severity severity{Severity::Low};
    double rule_match_score{0.0};
    RecoveryAction recommended_action{RecoveryAction::None};
    std::string rationale;
    std::vector<Fault> faults;
};

struct RecoveryResult {
    RecoveryStatus status{RecoveryStatus::NotRequired};
    RecoveryAction action{RecoveryAction::None};
    std::uint32_t attempts{0};
    std::uint32_t verified_cycles{0};
    std::string explanation;
};

struct RunSummary {
    std::string scenario;
    std::string terminal_state;
    std::vector<std::string> detected_faults;
    std::string primary_cause;
    std::string recovery_action;
    std::string recovery_status;
    std::uint32_t recovery_attempts{0};
    std::uint32_t verified_cycles{0};
    std::uint64_t total_ticks{0};
};

std::string toString(Scenario value);
std::string toString(FaultCode value);
std::string toString(Severity value);
std::string toString(SystemMode value);
std::string toString(RecoveryAction value);
std::string toString(RecoveryStatus value);

} // namespace aibars

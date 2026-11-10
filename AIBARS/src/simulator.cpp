#include "aibars/simulator.hpp"

#include <chrono>
#include <thread>

namespace aibars {

EmbeddedSystemSimulator::EmbeddedSystemSimulator(Scenario scenario, std::uint32_t tick_delay_ms)
    : scenario_(scenario), tick_delay_ms_(tick_delay_ms) {}

Telemetry EmbeddedSystemSimulator::step() {
    if (tick_delay_ms_ > 0U) std::this_thread::sleep_for(std::chrono::milliseconds(tick_delay_ms_));
    ++tick_;
    Telemetry t;
    t.tick = tick_;
    // Deterministic, changing baseline values make the demo and tests reproducible.
    t.temperature_c = 34.0 + static_cast<double>(tick_ % 9U) * 0.35;
    t.voltage_v = 24.0 + static_cast<double>(tick_ % 5U) * 0.08;
    t.current_a = 4.0 + static_cast<double>(tick_ % 7U) * 0.12;

    constexpr std::uint64_t injection_tick = 5;
    const std::uint64_t episode_tick = tick_ - episode_start_tick_ + 1U;
    if (episode_tick < injection_tick) {
        return t;
    }

    const auto age = static_cast<std::uint32_t>(episode_tick - injection_tick + 1U);
    switch (scenario_) {
        case Scenario::Nominal:
            break;
        case Scenario::SensorTimeout:
            if (!sensor_recovered_) {
                t.temperature_fresh = false;
                t.temperature_age_ticks = age;
            }
            break;
        case Scenario::SensorStuck:
            if (!sensor_recovered_) t.temperature_c = 42.0;
            break;
        case Scenario::SensorOutOfRange:
            if (!sensor_recovered_) t.temperature_c = 150.0;
            break;
        case Scenario::CommunicationTimeout:
            if (!communication_recovered_) {
                t.communication_ok = false;
                t.communication_age_ticks = age;
            }
            break;
        case Scenario::TaskHang:
            if (!primary_task_recovered_) {
                t.task_progressing = false;
                t.task_stall_ticks = age;
            }
            break;
        case Scenario::SecondaryTaskHang:
            if (!secondary_task_recovered_) {
                t.secondary_task_progressing = false;
                t.secondary_task_stall_ticks = age;
            }
            break;
        case Scenario::MultipleTaskHangs:
            if (!primary_task_recovered_) {
                t.task_progressing = false;
                t.task_stall_ticks = age;
            }
            if (!secondary_task_recovered_) {
                t.secondary_task_progressing = false;
                t.secondary_task_stall_ticks = age;
            }
            break;
        case Scenario::MultipleFaults:
            if (!sensor_recovered_) t.temperature_c = 150.0;
            if (!communication_recovered_) {
                t.communication_ok = false;
                // This scenario injects a communication fault that has already
                // exceeded any supported timeout threshold so both faults are
                // observable in the same diagnostic window.
                t.communication_age_ticks = age + 1000U;
            }
            break;
        case Scenario::RecoveryFailure:
            t.task_progressing = false;
            t.task_stall_ticks = age;
            break;
    }
    return t;
}

void EmbeddedSystemSimulator::beginScenario(Scenario scenario) noexcept {
    scenario_ = scenario;
    episode_start_tick_ = tick_ + 1U;
    sensor_recovered_ = false;
    communication_recovered_ = false;
    primary_task_recovered_ = false;
    secondary_task_recovered_ = false;
    mode_ = SystemMode::Normal;
}

void EmbeddedSystemSimulator::executeRecovery(RecoveryAction action) {
    // Recovery is component-specific: a sensor restart must not silently repair
    // a communication link or an unrelated task. RecoveryFailure deliberately
    // models a fault that persists despite a correctly issued restart request.
    if (scenario_ == Scenario::RecoveryFailure) return;

    switch (action) {
        case RecoveryAction::RestartSensor:
        case RecoveryAction::ReinitializeSensor:
        case RecoveryAction::QuarantineSensor:
            if (scenario_ == Scenario::SensorTimeout || scenario_ == Scenario::SensorStuck ||
                scenario_ == Scenario::SensorOutOfRange || scenario_ == Scenario::MultipleFaults) {
                sensor_recovered_ = true;
            }
            break;
        case RecoveryAction::RestartCommunication:
            if (scenario_ == Scenario::CommunicationTimeout || scenario_ == Scenario::MultipleFaults) {
                communication_recovered_ = true;
            }
            break;
        case RecoveryAction::RestartTask:
            if (scenario_ == Scenario::TaskHang) primary_task_recovered_ = true;
            if (scenario_ == Scenario::SecondaryTaskHang) secondary_task_recovered_ = true;
            break;
        case RecoveryAction::None:
        case RecoveryAction::EnterSafeMode:
            break;
    }
}

void EmbeddedSystemSimulator::enterSafeMode() noexcept {
    mode_ = SystemMode::SafeMode;
}

} // namespace aibars

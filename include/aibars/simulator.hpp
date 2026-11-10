#pragma once

#include "aibars/types.hpp"

#include <cstdint>

namespace aibars {

class EmbeddedSystemSimulator {
public:
    explicit EmbeddedSystemSimulator(Scenario scenario, std::uint32_t tick_delay_ms = 0U);

    Telemetry step();
    void executeRecovery(RecoveryAction action);
    // Begin a new fault episode on the same logical simulated device. Global ticks
    // continue; only episode-local fault state is reset.
    void beginScenario(Scenario scenario) noexcept;
    void enterSafeMode() noexcept;
    void setRecovering() noexcept { mode_ = SystemMode::Recovering; }
    void setNormal() noexcept { mode_ = SystemMode::Normal; }

    Scenario scenario() const noexcept { return scenario_; }
    SystemMode mode() const noexcept { return mode_; }
    std::uint64_t tickCount() const noexcept { return tick_; }

private:
    Scenario scenario_;
    SystemMode mode_{SystemMode::Normal};
    std::uint64_t tick_{0};
    std::uint64_t episode_start_tick_{1};
    std::uint32_t tick_delay_ms_{0};
    bool sensor_recovered_{false};
    bool communication_recovered_{false};
    bool primary_task_recovered_{false};
    bool secondary_task_recovered_{false};
};

} // namespace aibars

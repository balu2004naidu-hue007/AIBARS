#pragma once

#include "aibars/black_box.hpp"
#include "aibars/detector.hpp"
#include "aibars/simulator.hpp"
#include "aibars/types.hpp"

namespace aibars {

class AutonomousRecoveryManager {
public:
    explicit AutonomousRecoveryManager(std::uint32_t max_attempts = 2,
                                       std::uint32_t required_healthy_cycles = 3,
                                       std::uint32_t retry_backoff_ticks = 1);

    RecoveryResult execute(const Diagnosis& diagnosis,
                           EmbeddedSystemSimulator& simulator,
                           FaultDetectionEngine& detector,
                           BlackBoxLogger& logger);

private:
    std::uint32_t max_attempts_;
    std::uint32_t required_healthy_cycles_;
    std::uint32_t retry_backoff_ticks_;
};

} // namespace aibars

#include "aibars/recovery.hpp"

#include <sstream>
#include <stdexcept>

namespace aibars {

AutonomousRecoveryManager::AutonomousRecoveryManager(std::uint32_t max_attempts,
                                                     std::uint32_t required_healthy_cycles,
                                                     std::uint32_t retry_backoff_ticks)
    : max_attempts_(max_attempts), required_healthy_cycles_(required_healthy_cycles),
      retry_backoff_ticks_(retry_backoff_ticks) {
    if (max_attempts_ == 0U || max_attempts_ > 20U || required_healthy_cycles_ == 0U ||
        required_healthy_cycles_ > 1000U || retry_backoff_ticks_ > 1000U) {
        throw std::invalid_argument("Recovery limits are outside supported bounds");
    }
}

RecoveryResult AutonomousRecoveryManager::execute(const Diagnosis& diagnosis,
                                                  EmbeddedSystemSimulator& simulator,
                                                  FaultDetectionEngine& detector,
                                                  BlackBoxLogger& logger) {
    RecoveryResult result;
    result.action = diagnosis.recommended_action;

    if (diagnosis.faults.empty() || diagnosis.recommended_action == RecoveryAction::None) {
        result.status = RecoveryStatus::NotRequired;
        result.explanation = "No recovery action was required.";
        return result;
    }

    if (diagnosis.recommended_action == RecoveryAction::EnterSafeMode) {
        simulator.enterSafeMode();
        result.status = RecoveryStatus::SafeModeEntered;
        result.explanation = "Multiple independent faults were present; automatic recovery was withheld "
                             "and the simulated system entered safe mode.";
        logger.record(simulator.tickCount(), "recovery", "safe_mode_entered", result.explanation);
        return result;
    }

    simulator.setRecovering();
    for (std::uint32_t attempt = 1U; attempt <= max_attempts_; ++attempt) {
        if (attempt > 1U && retry_backoff_ticks_ > 0U) {
            const std::uint32_t backoff = retry_backoff_ticks_ * (attempt - 1U);
            for (std::uint32_t tick = 0U; tick < backoff; ++tick) {
                const Telemetry wait_sample = simulator.step();
                logger.record(wait_sample.tick, "recovery", "retry_backoff_tick",
                              "waiting before bounded retry; backoff tick " + std::to_string(tick + 1U) +
                              " of " + std::to_string(backoff));
            }
        }
        result.attempts = attempt;
        logger.record(simulator.tickCount(), "recovery", "recovery_attempt_started",
                      "attempt=" + std::to_string(attempt) + ", action=" + toString(result.action));
        simulator.executeRecovery(result.action);
        detector.reset();

        std::uint32_t healthy_streak = 0U;
        result.verified_cycles = 0U;
        for (std::uint32_t cycle = 1U; cycle <= required_healthy_cycles_; ++cycle) {
            const Telemetry telemetry = simulator.step();
            std::ostringstream snapshot;
            snapshot << "temperature=" << telemetry.temperature_c
                     << " C, voltage=" << telemetry.voltage_v
                     << " V, current=" << telemetry.current_a << " A";
            logger.record(telemetry.tick, "verification", "health_sample", snapshot.str());

            const auto remaining_faults = detector.evaluate(telemetry);
            if (remaining_faults.empty()) {
                ++healthy_streak;
                ++result.verified_cycles;
                logger.record(telemetry.tick, "verification", "healthy_cycle",
                              "consecutive healthy cycle " + std::to_string(healthy_streak) +
                              " of " + std::to_string(required_healthy_cycles_));
            } else {
                std::string evidence;
                for (const auto& fault : remaining_faults) {
                    if (!evidence.empty()) evidence += "; ";
                    evidence += toString(fault.code) + ": " + fault.evidence;
                }
                logger.record(telemetry.tick, "verification", "fault_persists", evidence);
                break;
            }
        }

        if (healthy_streak >= required_healthy_cycles_) {
            simulator.setNormal();
            result.status = RecoveryStatus::Verified;
            result.explanation = "Recovery passed " + std::to_string(healthy_streak) +
                                 " consecutive healthy verification cycles.";
            logger.record(simulator.tickCount(), "recovery", "recovery_verified", result.explanation);
            return result;
        }

        logger.record(simulator.tickCount(), "recovery", "recovery_attempt_failed",
                      "Fault condition remained observable during verification.");
    }

    simulator.enterSafeMode();
    result.status = RecoveryStatus::SafeModeEntered;
    result.explanation = "The fault persisted after " + std::to_string(max_attempts_) +
                         " bounded recovery attempt(s); the simulated system entered safe mode.";
    logger.record(simulator.tickCount(), "recovery", "safe_mode_entered", result.explanation);
    return result;
}

} // namespace aibars

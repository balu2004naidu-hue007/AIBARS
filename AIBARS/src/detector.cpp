#include "aibars/detector.hpp"

#include <cmath>
#include <stdexcept>
#include <sstream>

namespace aibars {

FaultDetectionEngine::FaultDetectionEngine(DetectionConfig config) : config_(config) {
    const bool finite_ranges = std::isfinite(config_.minimum_temperature_c) &&
        std::isfinite(config_.maximum_temperature_c) &&
        std::isfinite(config_.minimum_voltage_v) && std::isfinite(config_.maximum_voltage_v) &&
        std::isfinite(config_.minimum_current_a) && std::isfinite(config_.maximum_current_a);
    const bool ordered_ranges = config_.minimum_temperature_c < config_.maximum_temperature_c &&
        config_.minimum_voltage_v < config_.maximum_voltage_v &&
        config_.minimum_current_a < config_.maximum_current_a;
    const bool valid_windows = config_.sensor_timeout_ticks >= 1U && config_.sensor_timeout_ticks <= 1000U &&
        config_.communication_timeout_ticks >= 1U && config_.communication_timeout_ticks <= 1000U &&
        config_.stuck_sample_count >= 2U && config_.stuck_sample_count <= 1000U &&
        config_.task_stall_ticks >= 1U && config_.task_stall_ticks <= 1000U;
    if (!finite_ranges || !ordered_ranges || !valid_windows) {
        throw std::invalid_argument("Invalid fault-detection configuration: finite ordered ranges and supported tick windows are required");
    }
}

std::vector<Fault> FaultDetectionEngine::evaluate(const Telemetry& t) {
    std::vector<Fault> faults;

    // A missing/freshness flag alone is not enough: allow the configured age
    // window to elapse before declaring a timeout. This makes the timeout
    // threshold meaningful and prevents one missed sample becoming a fault.
    if (t.temperature_age_ticks >= config_.sensor_timeout_ticks) {
        std::ostringstream evidence;
        evidence << "temperature freshness=" << (t.temperature_fresh ? "reported-fresh" : "stale")
                 << ", age=" << t.temperature_age_ticks
                 << " ticks, threshold=" << config_.sensor_timeout_ticks << " ticks";
        faults.push_back({FaultCode::SensorTimeout, Severity::High, evidence.str()});
    }

    if (t.temperature_fresh) {
        if (previous_temperature_.has_value() && std::abs(t.temperature_c - *previous_temperature_) < 0.0001) {
            ++repeated_temperature_count_;
        } else {
            repeated_temperature_count_ = 0;
        }
        previous_temperature_ = t.temperature_c;
    } else {
        previous_temperature_.reset();
        repeated_temperature_count_ = 0U;
    }
    if (repeated_temperature_count_ >= (config_.stuck_sample_count > 0U ? config_.stuck_sample_count - 1U : 0U)) {
        std::ostringstream evidence;
        evidence << "temperature value remained unchanged across " << config_.stuck_sample_count
                 << " consecutive fresh samples";
        faults.push_back({FaultCode::SensorStuck, Severity::Medium, evidence.str()});
    }

    if (t.temperature_c < config_.minimum_temperature_c || t.temperature_c > config_.maximum_temperature_c ||
        t.voltage_v < config_.minimum_voltage_v || t.voltage_v > config_.maximum_voltage_v ||
        t.current_a < config_.minimum_current_a || t.current_a > config_.maximum_current_a) {
        std::ostringstream evidence;
        evidence << "out-of-range telemetry: temperature=" << t.temperature_c
                 << " C (allowed " << config_.minimum_temperature_c << ".." << config_.maximum_temperature_c
                 << "), voltage=" << t.voltage_v << " V (allowed " << config_.minimum_voltage_v << ".."
                 << config_.maximum_voltage_v << "), current=" << t.current_a << " A (allowed "
                 << config_.minimum_current_a << ".." << config_.maximum_current_a << ")";
        faults.push_back({FaultCode::SensorOutOfRange, Severity::High, evidence.str()});
    }

    // Communication loss is confirmed only after the configured heartbeat
    // age limit has been reached, not on the first missing heartbeat.
    if (t.communication_age_ticks >= config_.communication_timeout_ticks) {
        std::ostringstream evidence;
        evidence << "communication status=" << (t.communication_ok ? "reported-ok" : "lost")
                 << ", heartbeat age=" << t.communication_age_ticks
                 << " ticks, threshold=" << config_.communication_timeout_ticks << " ticks";
        faults.push_back({FaultCode::CommunicationTimeout, Severity::High, evidence.str()});
    }

    if (!t.task_progressing && t.task_stall_ticks >= config_.task_stall_ticks) {
        std::ostringstream evidence;
        evidence << "task=PRIMARY_CONTROL_LOOP progress stalled for " << t.task_stall_ticks
                 << " ticks, threshold=" << config_.task_stall_ticks << " ticks";
        faults.push_back({FaultCode::TaskHang, Severity::High, evidence.str()});
    }
    if (!t.secondary_task_progressing && t.secondary_task_stall_ticks >= config_.task_stall_ticks) {
        std::ostringstream evidence;
        evidence << "task=SECONDARY_TELEMETRY_TASK progress stalled for "
                 << t.secondary_task_stall_ticks << " ticks, threshold=" << config_.task_stall_ticks << " ticks";
        faults.push_back({FaultCode::TaskHang, Severity::High, evidence.str()});
    }

    return faults;
}

void FaultDetectionEngine::reset() noexcept {
    previous_temperature_.reset();
    repeated_temperature_count_ = 0;
}

} // namespace aibars

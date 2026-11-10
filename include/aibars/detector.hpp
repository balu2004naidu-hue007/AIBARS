#pragma once

#include "aibars/types.hpp"

#include <optional>
#include <vector>

namespace aibars {

struct DetectionConfig {
    double minimum_temperature_c{-40.0};
    double maximum_temperature_c{125.0};
    double minimum_voltage_v{9.0};
    double maximum_voltage_v{36.0};
    double minimum_current_a{0.0};
    double maximum_current_a{100.0};
    std::uint32_t sensor_timeout_ticks{3U};
    std::uint32_t communication_timeout_ticks{3U};
    std::uint32_t stuck_sample_count{5U};
    std::uint32_t task_stall_ticks{3U};
};

class FaultDetectionEngine {
public:
    explicit FaultDetectionEngine(DetectionConfig config = {});
    std::vector<Fault> evaluate(const Telemetry& telemetry);
    void reset() noexcept;

private:
    DetectionConfig config_;
    std::optional<double> previous_temperature_;
    std::uint32_t repeated_temperature_count_{0};
};

} // namespace aibars

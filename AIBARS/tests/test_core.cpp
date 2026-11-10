#include "aibars/black_box.hpp"
#include "aibars/detector.hpp"
#include "aibars/diagnostics.hpp"
#include "aibars/recovery.hpp"
#include "aibars/ring_buffer.hpp"
#include "aibars/simulator.hpp"

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <system_error>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

class TemporaryDirectory {
public:
    explicit TemporaryDirectory(const std::string& prefix) {
        static std::atomic<std::uint64_t> sequence{0U};
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        const auto unique = std::to_string(stamp) + "_" +
                            std::to_string(sequence.fetch_add(1U, std::memory_order_relaxed));
        path_ = std::filesystem::temp_directory_path() / (prefix + "_" + unique);
        if (!std::filesystem::create_directory(path_)) {
            throw std::runtime_error("Unable to create unique temporary test directory: " + path_.string());
        }
    }

    TemporaryDirectory(const TemporaryDirectory&) = delete;
    TemporaryDirectory& operator=(const TemporaryDirectory&) = delete;

    ~TemporaryDirectory() {
        std::error_code error;
        std::filesystem::remove_all(path_, error);
    }

    const std::filesystem::path& path() const noexcept { return path_; }

private:
    std::filesystem::path path_;
};

void testRingBufferPreservesLatestItemsInOrder() {
    aibars::RingBuffer<int> buffer(3U);
    buffer.push(1);
    buffer.push(2);
    buffer.push(3);
    buffer.push(4);
    const auto values = buffer.ordered();
    require(values.size() == 3U, "ring buffer should retain its capacity");
    require(values[0] == 2 && values[1] == 3 && values[2] == 4,
            "ring buffer should return the latest items in chronological order");
}

void testSensorTimeoutDetection() {
    aibars::EmbeddedSystemSimulator simulator(aibars::Scenario::SensorTimeout);
    aibars::FaultDetectionEngine detector;
    std::vector<aibars::Fault> faults;
    for (int i = 0; i < 7; ++i) faults = detector.evaluate(simulator.step());
    require(!faults.empty(), "sensor timeout should be detected after its configured age window");
    require(faults.front().code == aibars::FaultCode::SensorTimeout,
            "sensor timeout should map to SENSOR_TIMEOUT");
}


void testSensorAndCommunicationTimeoutsRespectConfiguredAgeWindows() {
    aibars::FaultDetectionEngine detector;
    aibars::Telemetry sample;
    sample.temperature_c = 35.0;
    sample.voltage_v = 24.0;
    sample.current_a = 4.0;
    sample.temperature_fresh = false;
    sample.communication_ok = false;
    sample.temperature_age_ticks = 1U;
    sample.communication_age_ticks = 1U;
    require(detector.evaluate(sample).empty(),
            "one stale sample must not trigger a default three-tick sensor/communication timeout");

    sample.tick = 2U;
    sample.temperature_age_ticks = 2U;
    sample.communication_age_ticks = 2U;
    require(detector.evaluate(sample).empty(),
            "two stale ticks must remain inside the default three-tick timeout window");

    sample.tick = 3U;
    sample.temperature_age_ticks = 3U;
    sample.communication_age_ticks = 3U;
    const auto faults = detector.evaluate(sample);
    require(faults.size() == 2U, "both timeouts should trigger exactly at their configured age threshold");
    require(faults[0].code == aibars::FaultCode::SensorTimeout,
            "sensor timeout should be reported at the configured age threshold");
    require(faults[1].code == aibars::FaultCode::CommunicationTimeout,
            "communication timeout should be reported at the configured heartbeat threshold");
    require(faults[0].evidence.find("threshold=3 ticks") != std::string::npos,
            "sensor timeout evidence should include the configured threshold");
    require(faults[1].evidence.find("threshold=3 ticks") != std::string::npos,
            "communication timeout evidence should include the configured threshold");
}

void testStuckSensorRequiresRepeatedSamples() {
    aibars::EmbeddedSystemSimulator simulator(aibars::Scenario::SensorStuck);
    aibars::FaultDetectionEngine detector;
    std::vector<aibars::Fault> faults;
    for (int i = 0; i < 8; ++i) faults = detector.evaluate(simulator.step());
    require(faults.empty(), "stuck sensor should not trigger before the sample threshold");
    faults = detector.evaluate(simulator.step());
    require(faults.size() == 1U && faults.front().code == aibars::FaultCode::SensorStuck,
            "stuck sensor should be detected after the configured repeated-sample window");
}

void testTaskHangRequiresSustainedStall() {
    aibars::EmbeddedSystemSimulator simulator(aibars::Scenario::TaskHang);
    aibars::FaultDetectionEngine detector;
    std::vector<aibars::Fault> faults;
    for (int i = 0; i < 6; ++i) {
        faults = detector.evaluate(simulator.step());
        require(faults.empty(), "a single or two-tick missed progress update must not be called a task hang");
    }
    faults = detector.evaluate(simulator.step());
    require(faults.size() == 1U && faults.front().code == aibars::FaultCode::TaskHang,
            "task hang should be detected after the three-tick stall threshold");
}

void testRecoveryActionsAffectOnlyTheirTargetSubsystem() {
    aibars::EmbeddedSystemSimulator sensor_sim(aibars::Scenario::SensorTimeout);
    for (int i = 0; i < 7; ++i) (void)sensor_sim.step();
    sensor_sim.executeRecovery(aibars::RecoveryAction::RestartCommunication);
    const auto still_stale = sensor_sim.step();
    require(!still_stale.temperature_fresh && still_stale.temperature_age_ticks > 0U,
            "restarting communication must not silently repair a sensor timeout");

    aibars::EmbeddedSystemSimulator recovered_sensor(aibars::Scenario::SensorTimeout);
    for (int i = 0; i < 7; ++i) (void)recovered_sensor.step();
    recovered_sensor.executeRecovery(aibars::RecoveryAction::RestartSensor);
    const auto fresh_sample = recovered_sensor.step();
    require(fresh_sample.temperature_fresh && fresh_sample.temperature_age_ticks == 0U,
            "sensor restart should restore fresh sensor telemetry");

    aibars::EmbeddedSystemSimulator secondary_task(aibars::Scenario::SecondaryTaskHang);
    for (int i = 0; i < 7; ++i) (void)secondary_task.step();
    secondary_task.executeRecovery(aibars::RecoveryAction::RestartTask);
    const auto task_sample = secondary_task.step();
    require(task_sample.secondary_task_progressing,
            "task restart should restore the affected secondary task");
}

void testCompoundDiagnosisChoosesContainment() {
    const std::vector<aibars::Fault> faults{
        {aibars::FaultCode::SensorOutOfRange, aibars::Severity::High, "temperature too high"},
        {aibars::FaultCode::CommunicationTimeout, aibars::Severity::High, "heartbeat missing"}
    };
    const auto diagnosis = aibars::ExplainableDiagnosisEngine{}.diagnose(faults);
    require(diagnosis.primary_cause == "COMPOUND_FAULT", "multiple faults should be diagnosed as compound");
    require(diagnosis.recommended_action == aibars::RecoveryAction::EnterSafeMode,
            "compound fault should select safe mode");
    require(diagnosis.severity == aibars::Severity::Critical, "compound fault should be critical");
}

void testSingleFaultRecoveryRequiresThreeHealthyCycles() {
    TemporaryDirectory temporary_directory("aibars_cpp_test_recovery");
    {
        // Keep the logger inside this scope so events.jsonl is closed before
        // TemporaryDirectory removes the directory. Windows does not permit
        // deleting an open file, unlike POSIX systems.
        aibars::BlackBoxLogger logger(temporary_directory.path());
        aibars::EmbeddedSystemSimulator simulator(aibars::Scenario::SensorTimeout);
        aibars::FaultDetectionEngine detector;
        std::vector<aibars::Fault> faults;
        for (int i = 0; i < 7; ++i) faults = detector.evaluate(simulator.step());
        const auto diagnosis = aibars::ExplainableDiagnosisEngine{}.diagnose(faults);
        const auto result = aibars::AutonomousRecoveryManager(2U, 3U).execute(diagnosis, simulator, detector, logger);
        require(result.status == aibars::RecoveryStatus::Verified, "recoverable sensor timeout should recover");
        require(result.verified_cycles == 3U, "recovery should require three consecutive healthy cycles");
        require(simulator.mode() == aibars::SystemMode::Normal, "verified recovery should return to normal mode");
    }
}

void testPersistentFaultEntersSafeModeAfterBoundedRetries() {
    TemporaryDirectory temporary_directory("aibars_cpp_test_persistent");
    {
        aibars::BlackBoxLogger logger(temporary_directory.path());
        aibars::EmbeddedSystemSimulator simulator(aibars::Scenario::RecoveryFailure);
        aibars::FaultDetectionEngine detector;
        std::vector<aibars::Fault> faults;
        for (int i = 0; i < 7; ++i) faults = detector.evaluate(simulator.step());
        const auto diagnosis = aibars::ExplainableDiagnosisEngine{}.diagnose(faults);
        const auto result = aibars::AutonomousRecoveryManager(2U, 3U).execute(diagnosis, simulator, detector, logger);
        require(result.status == aibars::RecoveryStatus::SafeModeEntered,
                "persistent fault should enter safe mode");
        require(result.attempts == 2U, "recovery attempts should remain bounded at two");
        require(simulator.mode() == aibars::SystemMode::SafeMode, "simulator should end in safe mode");
    }
}

} // namespace

int main() {
    try {
        testRingBufferPreservesLatestItemsInOrder();
        testSensorTimeoutDetection();
        testSensorAndCommunicationTimeoutsRespectConfiguredAgeWindows();
        testStuckSensorRequiresRepeatedSamples();
        testTaskHangRequiresSustainedStall();
        testRecoveryActionsAffectOnlyTheirTargetSubsystem();
        testCompoundDiagnosisChoosesContainment();
        testSingleFaultRecoveryRequiresThreeHealthyCycles();
        testPersistentFaultEntersSafeModeAfterBoundedRetries();
        std::cout << "PASS: 9 AIBARS core tests\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}

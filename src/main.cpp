#include "aibars/black_box.hpp"
#include "aibars/detector.hpp"
#include "aibars/diagnostics.hpp"
#include "aibars/recovery.hpp"
#include "aibars/simulator.hpp"

#include <filesystem>
#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <type_traits>
#include <stdexcept>
#include <string>
#include <vector>
#include <array>
#include <random>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace {

using aibars::Scenario;

Scenario parseScenario(const std::string& name) {
    if (name == "nominal") return Scenario::Nominal;
    if (name == "sensor_timeout") return Scenario::SensorTimeout;
    if (name == "sensor_stuck") return Scenario::SensorStuck;
    if (name == "sensor_out_of_range") return Scenario::SensorOutOfRange;
    if (name == "communication_timeout") return Scenario::CommunicationTimeout;
    if (name == "task_hang") return Scenario::TaskHang;
    if (name == "secondary_task_hang") return Scenario::SecondaryTaskHang;
    if (name == "multiple_task_hangs") return Scenario::MultipleTaskHangs;
    if (name == "multiple_faults") return Scenario::MultipleFaults;
    if (name == "recovery_failure") return Scenario::RecoveryFailure;
    throw std::invalid_argument("Unknown scenario: " + name);
}


template <typename UInt>
UInt parseUnsigned(const std::string& value, const std::string& option) {
    static_assert(std::is_unsigned<UInt>::value, "UInt must be an unsigned integer type");
    if (value.empty() || value.front() == '-') {
        throw std::invalid_argument(option + " requires a non-negative integer");
    }
    unsigned long long parsed = 0;
    const char* begin = value.data();
    const char* end = begin + value.size();
    const auto result = std::from_chars(begin, end, parsed);
    if (result.ec != std::errc{} || result.ptr != end ||
        parsed > static_cast<unsigned long long>(std::numeric_limits<UInt>::max())) {
        throw std::invalid_argument(option + " is outside the supported integer range");
    }
    return static_cast<UInt>(parsed);
}

double parseFiniteDouble(const std::string& value, const std::string& option) {
    std::size_t consumed = 0;
    double parsed = 0.0;
    try {
        parsed = std::stod(value, &consumed);
    } catch (const std::exception&) {
        throw std::invalid_argument(option + " requires a numeric value");
    }
    if (consumed != value.size() || !std::isfinite(parsed)) {
        throw std::invalid_argument(option + " requires a finite numeric value");
    }
    return parsed;
}

void printHelp(const char* executable) {
    std::cout << "AIBARS - explainable black-box diagnostics and recovery simulator\n\n"
              << "Usage: " << executable << " [--scenario NAME] [--out DIRECTORY]\n"
              << "       " << executable << " --autonomous [session options] [--out DIRECTORY]\n\n"
              << "Scenarios:\n"
              << "  nominal                Normal operation; no injected fault\n"
              << "  sensor_timeout         Temperature data becomes stale\n"
              << "  sensor_stuck           Temperature value stops changing\n"
              << "  sensor_out_of_range    Temperature exceeds its engineering range\n"
              << "  communication_timeout  Communication heartbeat is lost\n"
              << "  task_hang              Primary task progress stops\n"
              << "  secondary_task_hang    Secondary task progress stops\n"
              << "  multiple_task_hangs    Two task progress monitors stall together\n"
              << "  multiple_faults        Two independent faults occur together\n"
              << "  recovery_failure       Fault persists after recovery commands\n\n"
              << "Autonomous options: --session-cycles N --max-incidents N --fault-interval-min N\n"
              << "                    --fault-interval-max N --seed N --critical-fault-percent N --stop-file PATH\n\n"
              << "Options: --sensor-timeout-ticks N --communication-timeout-ticks N\n"
              << "        --stuck-samples N --task-stall-ticks N --temp-min-c X --temp-max-c X\n"
              << "        --voltage-min-v X --voltage-max-v X --current-min-a X --current-max-a X\n"
              << "        --recovery-attempts N --verify-cycles N --retry-backoff-ticks N --tick-delay-ms N\n\n"
              << "Example:\n  " << executable
              << " --scenario task_hang --out runs/task_hang\n";
}


struct AutonomousEpisode {
    std::uint32_t number{0};
    std::string scenario;
    std::string primary_cause;
    std::string terminal_state;
    std::string recovery_status;
    std::uint32_t attempts{0};
    std::uint32_t verified_cycles{0};
    std::uint64_t start_tick{0};
    std::uint64_t end_tick{0};
};

void writeAutonomousStatus(const std::filesystem::path& output,
                           const std::string& state,
                           std::uint32_t cycles,
                           std::uint32_t maximum_cycles,
                           std::uint32_t incidents,
                           std::uint32_t maximum_incidents,
                           std::uint32_t verified,
                           std::uint32_t safe_modes,
                           const std::string& current_scenario,
                           const aibars::Telemetry& telemetry,
                           std::uint32_t seed,
                           std::uint32_t next_fault_cycle = 0U,
                           std::uint32_t fault_interval_min_cycles = 0U,
                           std::uint32_t fault_interval_max_cycles = 0U,
                           std::uint32_t tick_delay_ms = 0U) {
    const auto temporary = output / "session_status.json.tmp";
    const auto target = output / "session_status.json";
    std::ofstream out(temporary, std::ios::out | std::ios::trunc);
    if (!out) throw std::runtime_error("Unable to write autonomous session status");
    out << std::fixed << std::setprecision(3)
        << "{\n  \"session_state\": \"" << state
        << "\",\n  \"device_id\": \"AIBARS-AUTO-ECU-01\""
        << ",\n  \"session_cycles\": " << cycles
        << ",\n  \"maximum_cycles\": " << maximum_cycles
        << ",\n  \"incidents\": " << incidents
        << ",\n  \"maximum_incidents\": " << maximum_incidents
        << ",\n  \"verified_recoveries\": " << verified
        << ",\n  \"safe_mode_entries\": " << safe_modes
        << ",\n  \"current_scenario\": \"" << current_scenario << "\""
        << ",\n  \"global_tick\": " << telemetry.tick
        << ",\n  \"temperature_c\": " << telemetry.temperature_c
        << ",\n  \"voltage_v\": " << telemetry.voltage_v
        << ",\n  \"current_a\": " << telemetry.current_a
        << ",\n  \"communication_ok\": " << (telemetry.communication_ok ? "true" : "false")
        << ",\n  \"primary_task_progressing\": " << (telemetry.task_progressing ? "true" : "false")
        << ",\n  \"secondary_task_progressing\": " << (telemetry.secondary_task_progressing ? "true" : "false")
        << ",\n  \"seed\": " << seed
        << ",\n  \"next_fault_cycle\": " << next_fault_cycle
        << ",\n  \"cycles_until_next_fault\": " << (next_fault_cycle > cycles ? next_fault_cycle - cycles : 0U)
        << ",\n  \"next_fault_in_seconds\": " << ((next_fault_cycle > cycles ? next_fault_cycle - cycles : 0U) * tick_delay_ms / 1000.0)
        << ",\n  \"fault_interval_min_cycles\": " << fault_interval_min_cycles
        << ",\n  \"fault_interval_max_cycles\": " << fault_interval_max_cycles
        << ",\n  \"tick_delay_ms\": " << tick_delay_ms
        << ",\n  \"interval_mode\": \"" << (fault_interval_min_cycles == fault_interval_max_cycles ? "FIXED" : "RANDOM") << "\""
        << ",\n  \"fault_interval_min_seconds\": " << (fault_interval_min_cycles * tick_delay_ms / 1000.0)
        << ",\n  \"fault_interval_max_seconds\": " << (fault_interval_max_cycles * tick_delay_ms / 1000.0) << "\n}\n";
    out.close();
    if (!out) throw std::runtime_error("Failed while writing autonomous session status");
    std::error_code error;
    std::filesystem::remove(target, error);
    error.clear();
    std::filesystem::rename(temporary, target, error);
    if (error) throw std::runtime_error("Unable to publish autonomous session status: " + error.message());
}

std::string telemetryDetail(const aibars::Telemetry& telemetry) {
    std::ostringstream detail;
    detail << std::fixed << std::setprecision(3)
           << "temperature=" << telemetry.temperature_c << " C"
           << ", voltage=" << telemetry.voltage_v << " V"
           << ", current=" << telemetry.current_a << " A"
           << ", temperature_age=" << telemetry.temperature_age_ticks
           << ", communication_age=" << telemetry.communication_age_ticks
           << ", communication_ok=" << (telemetry.communication_ok ? "true" : "false")
           << ", primary_task_progressing=" << (telemetry.task_progressing ? "true" : "false")
           << ", primary_task_stall=" << telemetry.task_stall_ticks
           << ", secondary_task_progressing=" << (telemetry.secondary_task_progressing ? "true" : "false")
           << ", secondary_task_stall=" << telemetry.secondary_task_stall_ticks;
    return detail.str();
}

int runAutonomousSession(const std::filesystem::path& output_directory,
                         const aibars::DetectionConfig& detection_config,
                         std::uint32_t recovery_attempts,
                         std::uint32_t verify_cycles,
                         std::uint32_t retry_backoff_ticks,
                         std::uint32_t tick_delay_ms,
                         std::uint32_t session_cycles_limit,
                         std::uint32_t max_incidents,
                         std::uint32_t fault_interval_min,
                         std::uint32_t fault_interval_max,
                         std::uint32_t seed,
                         std::uint32_t critical_fault_percent,
                         const std::filesystem::path& stop_file) {
    if (output_directory.empty()) throw std::invalid_argument("Output directory cannot be empty");
    if (session_cycles_limit < 10U || session_cycles_limit > 10000U || max_incidents == 0U || max_incidents > 20U ||
        fault_interval_min < 4U || fault_interval_max < fault_interval_min || fault_interval_max > 10000U ||
        critical_fault_percent > 100U) {
        throw std::invalid_argument("Autonomous session limits are invalid");
    }

    std::filesystem::create_directories(output_directory / "episodes");
    aibars::BlackBoxLogger black_box(output_directory);
    aibars::EmbeddedSystemSimulator simulator(Scenario::Nominal, tick_delay_ms);
    aibars::FaultDetectionEngine detector(detection_config);
    aibars::ExplainableDiagnosisEngine diagnosis_engine;
    aibars::AutonomousRecoveryManager recovery_manager(recovery_attempts, verify_cycles, retry_backoff_ticks);

    std::mt19937 generator(seed);
    std::uniform_int_distribution<std::uint32_t> interval_distribution(fault_interval_min, fault_interval_max);
    std::uniform_int_distribution<std::uint32_t> fault_distribution(0U, 5U);
    std::uniform_int_distribution<std::uint32_t> critical_distribution(0U, 99U);
    std::uniform_int_distribution<std::uint32_t> critical_scenario_distribution(0U, 2U);
    const std::array<Scenario, 6> recoverable_scenarios{{
        Scenario::SensorTimeout, Scenario::SensorStuck, Scenario::SensorOutOfRange,
        Scenario::CommunicationTimeout, Scenario::TaskHang, Scenario::SecondaryTaskHang
    }};
    const std::array<Scenario, 3> critical_scenarios{{
        Scenario::RecoveryFailure, Scenario::MultipleTaskHangs, Scenario::MultipleFaults
    }};

    std::vector<AutonomousEpisode> episodes;
    std::uint32_t verified_recoveries = 0U;
    std::uint32_t safe_mode_entries = 0U;
    std::uint32_t session_cycles = 0U;
    std::uint32_t selected_interval_cycles = interval_distribution(generator);
    std::uint32_t next_fault_cycle = selected_interval_cycles;
    std::string session_state = "MONITORING";
    std::string last_scenario = "nominal";
    std::string last_cause = "NO_FAULT_DETECTED";
    std::string last_recovery = "NOT_REQUIRED";
    aibars::Telemetry latest{};

    black_box.record(0U, "autonomous_supervisor", "session_started",
                     "continuous monitoring enabled; automatic seeded fault scheduling active; device=AIBARS-AUTO-ECU-01; seed=" + std::to_string(seed) +
                     "; interval_mode=" + (fault_interval_min == fault_interval_max ? std::string("FIXED") : std::string("RANDOM")) +
                     "; interval_seconds=" + std::to_string(fault_interval_min * tick_delay_ms / 1000.0) +
                     ".." + std::to_string(fault_interval_max * tick_delay_ms / 1000.0) +
                     "; tick_delay_ms=" + std::to_string(tick_delay_ms));
    writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                          0U, max_incidents, verified_recoveries, safe_mode_entries,
                          last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);

    while (session_cycles < session_cycles_limit && episodes.size() < max_incidents) {
        if (!stop_file.empty() && std::filesystem::exists(stop_file)) {
            session_state = "STOPPED";
            black_box.record(simulator.tickCount(), "autonomous_supervisor", "stop_requested",
                             "operator requested a controlled stop; current episode boundary honoured");
            break;
        }

        latest = simulator.step();
        ++session_cycles;
        black_box.record(latest.tick, "telemetry", "normal_sample_observed", telemetryDetail(latest));
        (void)detector.evaluate(latest);
        writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                              static_cast<std::uint32_t>(episodes.size()), max_incidents,
                              verified_recoveries, safe_mode_entries, last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);

        if (session_cycles < next_fault_cycle) {
            continue;
        }

        Scenario selected = recoverable_scenarios[fault_distribution(generator)];
        const bool critical_selected = critical_fault_percent > 0U &&
            critical_distribution(generator) < critical_fault_percent;
        if (critical_selected) selected = critical_scenarios[critical_scenario_distribution(generator)];

        const std::uint32_t episode_number = static_cast<std::uint32_t>(episodes.size() + 1U);
        const auto episode_start_tick = simulator.tickCount() + 1U;
        last_scenario = aibars::toString(selected);
        session_state = "FAULT_INJECTED";
        black_box.record(simulator.tickCount(), "fault_scheduler", "fault_scheduled",
                         "automatic scheduler selected scenario=" + last_scenario +
                         ", episode=" + std::to_string(episode_number) +
                         ", healthy_interval_cycles=" + std::to_string(selected_interval_cycles) +
                         ", healthy_interval_seconds=" + std::to_string(selected_interval_cycles * tick_delay_ms / 1000.0) +
                         (critical_selected ? ", severity_class=critical_test" : ", severity_class=recoverable_test"));
        simulator.beginScenario(selected);
        detector.reset();
        writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                              episode_number, max_incidents, verified_recoveries, safe_mode_entries,
                              last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
        std::vector<aibars::Fault> detected_faults;
        aibars::Diagnosis diagnosis;
        black_box.record(simulator.tickCount(), "autonomous_supervisor", "episode_started",
                         "episode=" + std::to_string(episode_number) + ", scenario=" + last_scenario +
                         ", monitoring continues on the same logical device");

        const std::uint32_t maximum_detection_window = std::max({
            detection_config.sensor_timeout_ticks,
            detection_config.communication_timeout_ticks,
            detection_config.stuck_sample_count,
            detection_config.task_stall_ticks,
        });
        const std::uint32_t maximum_observation_ticks = std::max(30U, maximum_detection_window + 6U);
        session_state = "MONITORING_FAULT_EPISODE";
        writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                              episode_number, max_incidents, verified_recoveries, safe_mode_entries,
                              last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
        for (std::uint32_t index = 0U; index < maximum_observation_ticks; ++index) {
            if (!stop_file.empty() && std::filesystem::exists(stop_file)) break;
            latest = simulator.step();
            const std::uint64_t episode_tick = latest.tick - episode_start_tick + 1U;
            if (episode_tick == 5U) {
                black_box.record(latest.tick, "fault_injector", "fault_activated",
                                 "automatic scheduler activated " + last_scenario + " on the simulated device");
            }
            black_box.record(latest.tick, "telemetry", "episode_sample_observed", telemetryDetail(latest));
            detected_faults = detector.evaluate(latest);
            if (!detected_faults.empty()) {
                session_state = "DIAGNOSING";
                for (const auto& fault : detected_faults) {
                    black_box.record(latest.tick, "fault_detector", "fault_detected",
                                     aibars::toString(fault.code) + " | " + fault.evidence);
                }
                diagnosis = diagnosis_engine.diagnose(detected_faults);
                last_cause = diagnosis.primary_cause;
                writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                                      episode_number, max_incidents, verified_recoveries, safe_mode_entries,
                                      last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
                black_box.record(latest.tick, "diagnosis", "diagnosis_completed",
                                 diagnosis.primary_cause + " | " + diagnosis.rationale);
                break;
            }
        }

        if (!stop_file.empty() && std::filesystem::exists(stop_file)) {
            session_state = "STOPPED";
            black_box.record(simulator.tickCount(), "autonomous_supervisor", "stop_requested",
                             "operator requested stop during the active fault episode");
            break;
        }

        if (detected_faults.empty()) {
            black_box.record(simulator.tickCount(), "autonomous_supervisor", "episode_detection_timeout",
                             "scheduler episode ended without a deterministic detector match; returning to monitoring");
            simulator.beginScenario(Scenario::Nominal);
            detector.reset();
            selected_interval_cycles = interval_distribution(generator);
            next_fault_cycle = session_cycles + selected_interval_cycles;
            continue;
        }

        session_state = "RECOVERING_AND_VERIFYING";
        writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                              episode_number, max_incidents, verified_recoveries, safe_mode_entries,
                              last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
        const auto recovery = recovery_manager.execute(diagnosis, simulator, detector, black_box);
        last_recovery = aibars::toString(recovery.status);
        if (recovery.status == aibars::RecoveryStatus::Verified) {
            ++verified_recoveries;
        } else if (recovery.status == aibars::RecoveryStatus::SafeModeEntered) {
            ++safe_mode_entries;
        }
        black_box.writeIncidentReport(diagnosis, recovery, aibars::toString(simulator.mode()));

        AutonomousEpisode episode;
        episode.number = episode_number;
        episode.scenario = last_scenario;
        episode.primary_cause = diagnosis.primary_cause;
        episode.terminal_state = aibars::toString(simulator.mode());
        episode.recovery_status = aibars::toString(recovery.status);
        episode.attempts = recovery.attempts;
        episode.verified_cycles = recovery.verified_cycles;
        episode.start_tick = episode_start_tick;
        episode.end_tick = simulator.tickCount();
        episodes.push_back(episode);

        const auto episode_report = output_directory / "episodes" /
            ("episode_" + (episode_number < 10U ? std::string("0") : std::string()) + std::to_string(episode_number) + ".json");
        std::ofstream report(episode_report, std::ios::out | std::ios::trunc);
        report << "{\n  \"episode\": " << episode.number
               << ",\n  \"scenario\": \"" << episode.scenario
               << "\",\n  \"primary_cause\": \"" << episode.primary_cause
               << "\",\n  \"terminal_state\": \"" << episode.terminal_state
               << "\",\n  \"recovery_status\": \"" << episode.recovery_status
               << "\",\n  \"recovery_attempts\": " << episode.attempts
               << ",\n  \"verified_cycles\": " << episode.verified_cycles
               << ",\n  \"start_tick\": " << episode.start_tick
               << ",\n  \"end_tick\": " << episode.end_tick << "\n}\n";
        report.close();
        std::error_code copy_error;
        std::filesystem::copy_file(output_directory / "incident.json",
                                   output_directory / "episodes" /
                                   ("episode_" + (episode_number < 10U ? std::string("0") : std::string()) +
                                    std::to_string(episode_number) + "_incident.json"),
                                   std::filesystem::copy_options::overwrite_existing, copy_error);

        black_box.record(simulator.tickCount(), "autonomous_supervisor", "episode_completed",
                         "episode=" + std::to_string(episode_number) + ", scenario=" + last_scenario +
                         ", diagnosis=" + diagnosis.primary_cause + ", recovery=" + last_recovery +
                         ", terminal_state=" + aibars::toString(simulator.mode()));

        if (simulator.mode() == aibars::SystemMode::SafeMode) {
            session_state = "SAFE_MODE";
            writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                                  episode_number, max_incidents, verified_recoveries, safe_mode_entries,
                                  last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
            break;
        }

        // The same simulator object and global tick counter continue. Only the
        // recovered episode is cleared, then the supervisor resumes normal monitoring.
        simulator.beginScenario(Scenario::Nominal);
        detector.reset();
        session_state = "MONITORING";
        black_box.record(simulator.tickCount(), "autonomous_supervisor", "monitoring_resumed",
                         "recovery verified; normal telemetry monitoring resumed on AIBARS-AUTO-ECU-01");
        latest = simulator.step();
        ++session_cycles;
        selected_interval_cycles = interval_distribution(generator);
        next_fault_cycle = session_cycles + selected_interval_cycles;
        black_box.record(latest.tick, "telemetry", "post_recovery_normal_sample",
                         telemetryDetail(latest));
        writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                              static_cast<std::uint32_t>(episodes.size()), max_incidents,
                              verified_recoveries, safe_mode_entries, "nominal", latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
    }

    if (session_state != "STOPPED" && session_state != "SAFE_MODE") {
        session_state = "COMPLETED";
    }
    black_box.record(simulator.tickCount(), "autonomous_supervisor", "session_completed",
                     "state=" + session_state + ", monitored_cycles=" + std::to_string(session_cycles) +
                     ", incidents=" + std::to_string(episodes.size()) +
                     ", verified_recoveries=" + std::to_string(verified_recoveries));

    std::ofstream summary(output_directory / "session_summary.json", std::ios::out | std::ios::trunc);
    summary << "{\n  \"session_state\": \"" << session_state
            << "\",\n  \"device_id\": \"AIBARS-AUTO-ECU-01\""
            << ",\n  \"session_cycles\": " << session_cycles
            << ",\n  \"global_ticks\": " << simulator.tickCount()
            << ",\n  \"incidents\": " << episodes.size()
            << ",\n  \"verified_recoveries\": " << verified_recoveries
            << ",\n  \"safe_mode_entries\": " << safe_mode_entries
            << ",\n  \"seed\": " << seed
            << ",\n  \"interval_mode\": \"" << (fault_interval_min == fault_interval_max ? "FIXED" : "RANDOM") << "\""
            << ",\n  \"fault_interval_min_cycles\": " << fault_interval_min
            << ",\n  \"fault_interval_max_cycles\": " << fault_interval_max
            << ",\n  \"tick_delay_ms\": " << tick_delay_ms
            << ",\n  \"fault_interval_min_seconds\": " << (fault_interval_min * tick_delay_ms / 1000.0)
            << ",\n  \"fault_interval_max_seconds\": " << (fault_interval_max * tick_delay_ms / 1000.0)
            << ",\n  \"episodes\": [";
    for (std::size_t i = 0; i < episodes.size(); ++i) {
        const auto& episode = episodes[i];
        if (i != 0U) summary << ',';
        summary << "\n    {\"episode\": " << episode.number
                << ", \"scenario\": \"" << episode.scenario
                << "\", \"primary_cause\": \"" << episode.primary_cause
                << "\", \"terminal_state\": \"" << episode.terminal_state
                << "\", \"recovery_status\": \"" << episode.recovery_status
                << "\", \"recovery_attempts\": " << episode.attempts
                << ", \"verified_cycles\": " << episode.verified_cycles
                << ", \"start_tick\": " << episode.start_tick
                << ", \"end_tick\": " << episode.end_tick << "}";
    }
    if (!episodes.empty()) summary << '\n' << "  ";
    summary << "]\n}\n";
    summary.close();

    aibars::RunSummary run_summary;
    run_summary.scenario = "autonomous_session";
    run_summary.terminal_state = session_state == "SAFE_MODE" ? "SAFE_MODE" : "NORMAL";
    run_summary.primary_cause = last_cause;
    run_summary.recovery_action = "AUTOMATIC_POLICY";
    run_summary.recovery_status = session_state == "SAFE_MODE" ? "SAFE_MODE_ENTERED" : "SESSION_COMPLETED";
    run_summary.recovery_attempts = 0U;
    run_summary.verified_cycles = verified_recoveries;
    run_summary.total_ticks = simulator.tickCount();
    black_box.writeSummary(run_summary);

    writeAutonomousStatus(output_directory, session_state, session_cycles, session_cycles_limit,
                          static_cast<std::uint32_t>(episodes.size()), max_incidents,
                          verified_recoveries, safe_mode_entries, last_scenario, latest, seed, next_fault_cycle, fault_interval_min, fault_interval_max, tick_delay_ms);
    std::cout << "\nAIBARS AUTONOMOUS SESSION SUMMARY\n"
              << "Device             : AIBARS-AUTO-ECU-01\n"
              << "Session state      : " << session_state << '\n'
              << "Monitoring cycles  : " << session_cycles << '\n'
              << "Fault episodes     : " << episodes.size() << '\n'
              << "Verified recoveries: " << verified_recoveries << '\n'
              << "Safe-mode entries  : " << safe_mode_entries << '\n'
              << "Global ticks       : " << simulator.tickCount() << '\n'
              << "Session report     : " << (output_directory / "session_summary.json") << '\n';
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    try {
        std::string scenario_name = "nominal";
        std::filesystem::path output_directory = "runs/nominal";
        aibars::DetectionConfig detection_config;
        std::uint32_t recovery_attempts = 2U;
        std::uint32_t verify_cycles = 3U;
        std::uint32_t retry_backoff_ticks = 1U;
        std::uint32_t tick_delay_ms = 0U;
        bool autonomous_mode = false;
        std::uint32_t session_cycles = 120U;
        std::uint32_t max_incidents = 3U;
        std::uint32_t fault_interval_min = 8U;
        std::uint32_t fault_interval_max = 16U;
        std::uint32_t random_seed = 20261110U;
        std::uint32_t critical_fault_percent = 0U;
        std::filesystem::path stop_file;
        for (int i = 1; i < argc; ++i) {
            const std::string argument = argv[i];
            if (argument == "--help" || argument == "-h") {
                printHelp(argv[0]);
                return 0;
            }
            if (argument == "--autonomous") { autonomous_mode = true; continue; }
            if (argument == "--session-cycles" && i + 1 < argc) { session_cycles = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--max-incidents" && i + 1 < argc) { max_incidents = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--fault-interval-min" && i + 1 < argc) { fault_interval_min = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--fault-interval-max" && i + 1 < argc) { fault_interval_max = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--seed" && i + 1 < argc) { random_seed = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--critical-fault-percent" && i + 1 < argc) { critical_fault_percent = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--stop-file" && i + 1 < argc) { stop_file = argv[++i]; continue; }
            if (argument == "--scenario" && i + 1 < argc) {
                scenario_name = argv[++i];
                continue;
            }
            if (argument == "--out" && i + 1 < argc) {
                output_directory = argv[++i];
                continue;
            }
            if (argument == "--sensor-timeout-ticks" && i + 1 < argc) { detection_config.sensor_timeout_ticks = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--communication-timeout-ticks" && i + 1 < argc) { detection_config.communication_timeout_ticks = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--stuck-samples" && i + 1 < argc) { detection_config.stuck_sample_count = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--task-stall-ticks" && i + 1 < argc) { detection_config.task_stall_ticks = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--temp-min-c" && i + 1 < argc) { detection_config.minimum_temperature_c = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--temp-max-c" && i + 1 < argc) { detection_config.maximum_temperature_c = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--voltage-min-v" && i + 1 < argc) { detection_config.minimum_voltage_v = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--voltage-max-v" && i + 1 < argc) { detection_config.maximum_voltage_v = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--current-min-a" && i + 1 < argc) { detection_config.minimum_current_a = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--current-max-a" && i + 1 < argc) { detection_config.maximum_current_a = parseFiniteDouble(argv[++i], argument); continue; }
            if (argument == "--recovery-attempts" && i + 1 < argc) { recovery_attempts = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--verify-cycles" && i + 1 < argc) { verify_cycles = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--retry-backoff-ticks" && i + 1 < argc) { retry_backoff_ticks = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            if (argument == "--tick-delay-ms" && i + 1 < argc) { tick_delay_ms = parseUnsigned<std::uint32_t>(argv[++i], argument); continue; }
            throw std::invalid_argument("Invalid or incomplete argument: " + argument);
        }

        const Scenario scenario = parseScenario(scenario_name);
        if (output_directory.empty()) throw std::invalid_argument("Output directory cannot be empty");
        if (!std::isfinite(detection_config.minimum_temperature_c) ||
            !std::isfinite(detection_config.maximum_temperature_c) ||
            !std::isfinite(detection_config.minimum_voltage_v) ||
            !std::isfinite(detection_config.maximum_voltage_v) ||
            !std::isfinite(detection_config.minimum_current_a) ||
            !std::isfinite(detection_config.maximum_current_a) ||
            detection_config.minimum_temperature_c >= detection_config.maximum_temperature_c ||
            detection_config.minimum_voltage_v >= detection_config.maximum_voltage_v ||
            detection_config.minimum_current_a >= detection_config.maximum_current_a ||
            detection_config.sensor_timeout_ticks == 0U || detection_config.sensor_timeout_ticks > 1000U ||
            detection_config.communication_timeout_ticks == 0U || detection_config.communication_timeout_ticks > 1000U ||
            detection_config.stuck_sample_count < 2U || detection_config.stuck_sample_count > 1000U ||
            detection_config.task_stall_ticks == 0U || detection_config.task_stall_ticks > 1000U) {
            throw std::invalid_argument("Invalid detection configuration: finite ordered ranges and tick limits 1..1000 are required; stuck samples must be 2..1000");
        }
        if (recovery_attempts == 0U || recovery_attempts > 20U || verify_cycles == 0U || verify_cycles > 1000U ||
            retry_backoff_ticks > 1000U) {
            throw std::invalid_argument("Invalid recovery configuration: attempts 1..20, verification cycles 1..1000 and backoff 0..1000 are required");
        }
        if (tick_delay_ms > 1000U) throw std::invalid_argument("tick delay must not exceed 1000 ms");

        if (autonomous_mode) {
            return runAutonomousSession(output_directory, detection_config, recovery_attempts, verify_cycles,
                                        retry_backoff_ticks, tick_delay_ms, session_cycles, max_incidents,
                                        fault_interval_min, fault_interval_max, random_seed,
                                        critical_fault_percent, stop_file);
        }

        aibars::BlackBoxLogger black_box(output_directory);
        aibars::EmbeddedSystemSimulator simulator(scenario, tick_delay_ms);
        aibars::FaultDetectionEngine detector(detection_config);
        aibars::ExplainableDiagnosisEngine diagnosis_engine;
        aibars::AutonomousRecoveryManager recovery_manager(recovery_attempts, verify_cycles, retry_backoff_ticks);

        black_box.record(0U, "supervisor", "run_started", "scenario=" + scenario_name);
        std::vector<aibars::Fault> detected_faults;
        aibars::Diagnosis diagnosis;

        // Continue observing long enough to honour every accepted threshold,
        // including user profiles that set a timeout above the nominal 30 ticks.
        const std::uint32_t maximum_detection_window = std::max({
            detection_config.sensor_timeout_ticks,
            detection_config.communication_timeout_ticks,
            detection_config.stuck_sample_count,
            detection_config.task_stall_ticks,
        });
        const std::uint32_t maximum_observation_ticks = std::max(30U, maximum_detection_window + 6U);
        for (std::uint32_t index = 0U; index < maximum_observation_ticks; ++index) {
            const aibars::Telemetry telemetry = simulator.step();
            if (telemetry.tick == 5U && scenario != Scenario::Nominal) {
                black_box.record(telemetry.tick, "fault_injector", "fault_injected",
                                 "scenario=" + scenario_name);
            }
            black_box.record(telemetry.tick, "telemetry", "sample_observed",
                             "temperature=" + std::to_string(telemetry.temperature_c) +
                             " C, voltage=" + std::to_string(telemetry.voltage_v) +
                             " V, current=" + std::to_string(telemetry.current_a) +
                             " A, temperature_age=" + std::to_string(telemetry.temperature_age_ticks) +
                             " ticks, communication_age=" + std::to_string(telemetry.communication_age_ticks) +
                             " ticks, communication_ok=" + (telemetry.communication_ok ? "true" : "false") +
                             ", primary_task_progressing=" + (telemetry.task_progressing ? "true" : "false") +
                             ", primary_task_stall=" + std::to_string(telemetry.task_stall_ticks) +
                             " ticks, secondary_task_progressing=" + (telemetry.secondary_task_progressing ? "true" : "false") +
                             ", secondary_task_stall=" + std::to_string(telemetry.secondary_task_stall_ticks) + " ticks");

            detected_faults = detector.evaluate(telemetry);
            if (!detected_faults.empty()) {
                diagnosis = diagnosis_engine.diagnose(detected_faults);
                for (const auto& fault : detected_faults) {
                    black_box.record(telemetry.tick, "fault_detector", "fault_detected",
                                     toString(fault.code) + " | " + fault.evidence);
                }
                black_box.record(telemetry.tick, "diagnosis", "diagnosis_completed",
                                 diagnosis.primary_cause + " | " + diagnosis.rationale);
                break;
            }
        }

        aibars::RecoveryResult recovery;
        if (detected_faults.empty()) {
            diagnosis = diagnosis_engine.diagnose({});
            recovery.status = aibars::RecoveryStatus::NotRequired;
            recovery.explanation = "No fault was detected during the observation window.";
            black_box.record(simulator.tickCount(), "supervisor", "nominal_run_completed",
                             recovery.explanation);
        } else {
            recovery = recovery_manager.execute(diagnosis, simulator, detector, black_box);
        }

        const std::string terminal_state = aibars::toString(simulator.mode());
        aibars::RunSummary summary;
        summary.scenario = scenario_name;
        summary.terminal_state = terminal_state;
        summary.primary_cause = diagnosis.primary_cause;
        summary.recovery_action = aibars::toString(diagnosis.recommended_action);
        summary.recovery_status = aibars::toString(recovery.status);
        summary.recovery_attempts = recovery.attempts;
        summary.verified_cycles = recovery.verified_cycles;
        summary.total_ticks = simulator.tickCount();
        for (const auto& fault : detected_faults) summary.detected_faults.push_back(aibars::toString(fault.code));

        black_box.record(simulator.tickCount(), "supervisor", "run_completed",
                         "terminal_state=" + terminal_state + ", recovery=" + aibars::toString(recovery.status));
        black_box.writeSummary(summary);
        if (!detected_faults.empty()) {
            black_box.writeIncidentReport(diagnosis, recovery, terminal_state);
        }

        std::cout << "\nAIBARS RUN SUMMARY\n"
                  << "Scenario           : " << summary.scenario << '\n'
                  << "Detected faults    : ";
        if (summary.detected_faults.empty()) {
            std::cout << "NONE\n";
        } else {
            for (std::size_t i = 0; i < summary.detected_faults.size(); ++i) {
                if (i != 0U) std::cout << ", ";
                std::cout << summary.detected_faults[i];
            }
            std::cout << '\n';
        }
        std::cout << "Primary cause      : " << summary.primary_cause << '\n'
                  << "Recovery action    : " << summary.recovery_action << '\n'
                  << "Recovery status    : " << summary.recovery_status << '\n'
                  << "Recovery attempts  : " << summary.recovery_attempts << '\n'
                  << "Verified cycles    : " << summary.verified_cycles << '\n'
                  << "Terminal state     : " << summary.terminal_state << '\n'
                  << "Total ticks        : " << summary.total_ticks << '\n'
                  << "Output directory   : " << output_directory.string() << "\n\n";
        std::cout << recovery.explanation << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "AIBARS error: " << error.what() << '\n';
        return 2;
    }
}

#include "aibars/black_box.hpp"

#include <iomanip>
#include <stdexcept>

namespace aibars {

std::string jsonEscape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size() + 8U);
    for (const char raw : value) {
        const auto ch = static_cast<unsigned char>(raw);
        switch (ch) {
            case '"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\b': escaped += "\\b"; break;
            case '\f': escaped += "\\f"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default:
                if (ch < 0x20U) {
                    escaped += '?';
                } else {
                    escaped += static_cast<char>(ch);
                }
        }
    }
    return escaped;
}

BlackBoxLogger::BlackBoxLogger(const std::filesystem::path& output_directory,
                               std::size_t history_capacity)
    : output_directory_(output_directory), history_(history_capacity) {
    std::filesystem::create_directories(output_directory_);
    event_stream_.open(output_directory_ / "events.jsonl", std::ios::out | std::ios::trunc);
    if (!event_stream_.is_open()) {
        throw std::runtime_error("Unable to open events.jsonl in output directory");
    }
}

void BlackBoxLogger::record(std::uint64_t tick, const std::string& component,
                            const std::string& event, const std::string& detail) {
    EventRecord record{next_sequence_++, tick, component, event, detail};
    history_.push(record);
    event_stream_ << "{\"sequence\":" << record.sequence
                  << ",\"tick\":" << record.tick
                  << ",\"component\":\"" << jsonEscape(record.component)
                  << "\",\"event\":\"" << jsonEscape(record.event)
                  << "\",\"detail\":\"" << jsonEscape(record.detail) << "\"}\n";
    event_stream_.flush();
    if (!event_stream_) {
        throw std::runtime_error("Failed while writing black-box event log");
    }
}

void BlackBoxLogger::writeIncidentReport(const Diagnosis& diagnosis,
                                         const RecoveryResult& recovery,
                                         const std::string& terminal_state) {
    std::ofstream out(output_directory_ / "incident.json", std::ios::out | std::ios::trunc);
    if (!out) throw std::runtime_error("Unable to write incident.json");

    out << "{\n  \"primary_cause\": \"" << jsonEscape(diagnosis.primary_cause)
        << "\",\n  \"severity\": \"" << toString(diagnosis.severity)
        << "\",\n  \"rule_match_score\": " << std::fixed << std::setprecision(2) << diagnosis.rule_match_score
        << ",\n  \"rationale\": \"" << jsonEscape(diagnosis.rationale)
        << "\",\n  \"recommended_action\": \"" << toString(diagnosis.recommended_action)
        << "\",\n  \"terminal_state\": \"" << jsonEscape(terminal_state)
        << "\",\n  \"recovery_status\": \"" << toString(recovery.status)
        << "\",\n  \"recovery_explanation\": \"" << jsonEscape(recovery.explanation)
        << "\",\n  \"recovery_attempts\": " << recovery.attempts
        << ",\n  \"verified_cycles\": " << recovery.verified_cycles
        << ",\n  \"faults\": [";

    for (std::size_t i = 0; i < diagnosis.faults.size(); ++i) {
        const Fault& fault = diagnosis.faults[i];
        if (i != 0U) out << ',';
        out << "\n    {\"code\": \"" << toString(fault.code)
            << "\", \"severity\": \"" << toString(fault.severity)
            << "\", \"evidence\": \"" << jsonEscape(fault.evidence) << "\"}";
    }
    if (!diagnosis.faults.empty()) out << '\n' << "  ";
    out << "],\n  \"recent_events\": [";

    const auto events = history_.ordered();
    for (std::size_t i = 0; i < events.size(); ++i) {
        const EventRecord& event = events[i];
        if (i != 0U) out << ',';
        out << "\n    {\"sequence\":" << event.sequence
            << ",\"tick\":" << event.tick
            << ",\"component\":\"" << jsonEscape(event.component)
            << "\",\"event\":\"" << jsonEscape(event.event)
            << "\",\"detail\":\"" << jsonEscape(event.detail) << "\"}";
    }
    if (!events.empty()) out << '\n' << "  ";
    out << "]\n}\n";
}

void BlackBoxLogger::writeSummary(const RunSummary& summary) {
    std::ofstream out(output_directory_ / "summary.json", std::ios::out | std::ios::trunc);
    if (!out) throw std::runtime_error("Unable to write summary.json");
    out << "{\n  \"scenario\": \"" << jsonEscape(summary.scenario)
        << "\",\n  \"terminal_state\": \"" << jsonEscape(summary.terminal_state)
        << "\",\n  \"primary_cause\": \"" << jsonEscape(summary.primary_cause)
        << "\",\n  \"recovery_action\": \"" << jsonEscape(summary.recovery_action)
        << "\",\n  \"recovery_status\": \"" << jsonEscape(summary.recovery_status)
        << "\",\n  \"recovery_attempts\": " << summary.recovery_attempts
        << ",\n  \"verified_cycles\": " << summary.verified_cycles
        << ",\n  \"total_ticks\": " << summary.total_ticks
        << ",\n  \"detected_faults\": [";
    for (std::size_t i = 0; i < summary.detected_faults.size(); ++i) {
        if (i != 0U) out << ", ";
        out << '"' << jsonEscape(summary.detected_faults[i]) << '"';
    }
    out << "]\n}\n";
}

} // namespace aibars

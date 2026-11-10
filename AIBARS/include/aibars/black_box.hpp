#pragma once

#include "aibars/ring_buffer.hpp"
#include "aibars/types.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace aibars {

struct EventRecord {
    std::uint64_t sequence{0};
    std::uint64_t tick{0};
    std::string component;
    std::string event;
    std::string detail;
};

class BlackBoxLogger {
public:
    explicit BlackBoxLogger(const std::filesystem::path& output_directory,
                            std::size_t history_capacity = 128);

    void record(std::uint64_t tick, const std::string& component,
                const std::string& event, const std::string& detail);
    void writeIncidentReport(const Diagnosis& diagnosis,
                             const RecoveryResult& recovery,
                             const std::string& terminal_state);
    void writeSummary(const RunSummary& summary);

    std::vector<EventRecord> recentEvents() const { return history_.ordered(); }
    const std::filesystem::path& outputDirectory() const noexcept { return output_directory_; }

private:
    std::filesystem::path output_directory_;
    std::ofstream event_stream_;
    RingBuffer<EventRecord> history_;
    std::uint64_t next_sequence_{1};
};

std::string jsonEscape(const std::string& value);

} // namespace aibars

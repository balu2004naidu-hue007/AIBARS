#pragma once

#include "aibars/types.hpp"

namespace aibars {

class ExplainableDiagnosisEngine {
public:
    Diagnosis diagnose(const std::vector<Fault>& faults) const;
};

} // namespace aibars

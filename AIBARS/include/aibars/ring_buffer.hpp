#pragma once

#include <cstddef>
#include <stdexcept>
#include <vector>

namespace aibars {

template <typename T>
class RingBuffer {
public:
    explicit RingBuffer(std::size_t capacity) : capacity_(capacity) {
        if (capacity_ == 0) {
            throw std::invalid_argument("RingBuffer capacity must be greater than zero");
        }
    }

    void push(const T& value) {
        if (items_.size() < capacity_) {
            items_.push_back(value);
            return;
        }
        items_[next_] = value;
        next_ = (next_ + 1) % capacity_;
    }

    std::vector<T> ordered() const {
        if (items_.size() < capacity_ || next_ == 0) {
            return items_;
        }
        std::vector<T> result;
        result.reserve(items_.size());
        result.insert(result.end(), items_.begin() + static_cast<std::ptrdiff_t>(next_), items_.end());
        result.insert(result.end(), items_.begin(), items_.begin() + static_cast<std::ptrdiff_t>(next_));
        return result;
    }

    std::size_t size() const noexcept { return items_.size(); }
    std::size_t capacity() const noexcept { return capacity_; }

private:
    std::size_t capacity_;
    std::size_t next_{0};
    std::vector<T> items_;
};

} // namespace aibars

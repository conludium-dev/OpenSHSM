#pragma once
#include "stock_gx_completed_frame.h"
#include "stock_movie_capture_gate.h"
#include <cstdint>
#include <limits>

struct StockPECadenceObservation {
    stock_movie_capture_gate::Gate gate;
    uint64_t consumed = 0;
    uint64_t batch = 0;
    unsigned samples = 0;
    unsigned markers = 0;
    bool enabled;

    explicit StockPECadenceObservation(const char* delay) : gate(delay), enabled(delay && gate.valid) {}

    template<class Emit>
    bool inspect(const std::vector<nwii::runtime::gx::GXCommand>& commands,
        const StockGXCompletedFrameBounds& bounds, uint64_t host_us, Emit emit) {
        if (!enabled) {
            return false;
        }
        const uint64_t count = bounds.end < 0 ? 0 : uint64_t(bounds.end) + 1;
        if (count > commands.size() || commands.size() > std::numeric_limits<uint64_t>::max() - consumed) {
            enabled = false;
            return false;
        }
        ++batch;
        const bool accepted = samples < 128 && gate.accept(host_us);
        if (accepted) {
            ++samples;
            for (size_t index = 0; index < commands.size(); ++index) {
                const auto& command = commands[index];
                if (markers < 512 && stock_gx_pe_completion(command)) {
                    ++markers;
                    emit(batch, consumed + index, command.reg, command.val,
                        int(index) <= bounds.end, host_us);
                }
            }
        }
        consumed += count;
        return accepted;
    }
};

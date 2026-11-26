#pragma once
#include "stock_gx_completion.h"

struct StockGXCompletedFrameBounds : StockGXExecutionBounds {
    int last_copy = -1;
};

inline StockGXCompletedFrameBounds stock_gx_completed_frame_bounds(
    const std::vector<nwii::runtime::gx::GXCommand>& commands) {
    using nwii::runtime::gx::GXCommandType;
    StockGXCompletedFrameBounds result;
    int completion = -1;
    for (size_t index = 0; index < commands.size(); ++index) {
        const auto& command = commands[index];
        if (command.type == GXCommandType::BPRegister && command.reg == 0x52 && (command.val & 0x4000)) {
            result.previous_copy = result.last_copy;
            result.last_copy = int(index);
        } else if (stock_gx_pe_completion(command)) {
            completion = int(index);
        }
    }
    result.end = result.last_copy >= 0 ? result.last_copy : completion;
    return result;
}

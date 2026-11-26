#pragma once
#include "runtime/gx_command.h"
#include <vector>

inline bool stock_gx_pe_completion(const nwii::runtime::gx::GXCommand& command) {
    using nwii::runtime::gx::GXCommandType;
    return command.type == GXCommandType::BPRegister &&
        ((command.reg == 0x45 && (command.val & 0xFF) == 2) ||
            command.reg == 0x47 || command.reg == 0x48);
}
struct StockGXExecutionBounds {
    int end = -1;
    int previous_copy = -1;
};
inline StockGXExecutionBounds stock_gx_execution_bounds(
    const std::vector<nwii::runtime::gx::GXCommand>& commands) {
    using nwii::runtime::gx::GXCommandType;
    StockGXExecutionBounds result;
    int last_copy = -1;
    for (size_t index = 0; index < commands.size(); ++index) {
        const auto& command = commands[index];
        if (command.type == GXCommandType::BPRegister && command.reg == 0x52 && (command.val & 0x4000)) {
            result.previous_copy = last_copy;
            last_copy = int(index);
            result.end = int(index);
        } else if (stock_gx_pe_completion(command)) {
            result.end = int(index);
        }
    }
    return result;
}

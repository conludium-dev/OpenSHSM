#pragma once
#include "template_nop.h"

namespace nwii::runtime {
inline void experiment_table_write_observer(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    const auto mapping = bat_memory_range(context, address, 4);
    try {
        bat_memory_write32(context, address, value);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; table instruction=" << std::hex << instruction
                << " address=" << address << " physical=" << mapping.physical << " value=" << value;
        for (const auto& [start, image] : memory_context(context).instructionImages) {
            const uint32_t code = start & 0x3fffffff;
            if (uint64_t(mapping.physical) < uint64_t(code) + image.size() && uint64_t(mapping.physical) + 4 > code) {
                message << " protected=" << start << " size=" << image.size();
            }
        }
        throw std::runtime_error(message.str());
    }
}
}

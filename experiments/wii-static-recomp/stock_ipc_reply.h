#pragma once
#include "runtime/cpu_context.h"

namespace openshsm::experiment {
inline bool prepare_ipc_reply(nwii::runtime::MMU& mmu, uint32_t address) {
    const auto region = address & 0xF0000000;
    if (region != 0 && region != 0x10000000 && region != 0x80000000
        && region != 0x90000000 && region != 0xC0000000 && region != 0xD0000000) {
        return false;
    }
    const auto physical = address & 0x1FFFFFFF;
    const bool mem1 = physical < 0x01800000 && 64 <= 0x01800000 - physical;
    const bool mem2 = physical >= 0x10000000 && physical < 0x14000000
        && 64 <= 0x14000000 - physical;
    if ((!mem1 && !mem2) || (physical & 31)) {
        return false;
    }
    auto* bytes = mmu.get_ptr(physical);
    if (!bytes || mmu.get_ptr(physical + 63) != bytes + 63) {
        return false;
    }
    const auto command = mmu.read32(physical);
    if (command == 8) {
        const auto original = mmu.read32(physical + 8);
        return original >= 1 && original <= 7;
    }
    if (command < 1 || command > 7) {
        return false;
    }
    mmu.write32(physical + 8, command);
    mmu.write32(physical, 8);
    return true;
}
}

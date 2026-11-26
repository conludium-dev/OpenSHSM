#pragma once
#include <cstdint>
#include <cstdlib>
#include <iostream>

namespace openshsm::experiment {
constexpr uint32_t pc_boot_index(uint32_t index, bool skip) {
    if (skip && index < 4) {
        return 4;
    }
    if (index == 5) {
        return 6;
    }
    return index;
}

template <typename Context> void skip_pc_boot_notices(Context& ctx) {
    static const bool enabled = [] {
        const char* value = std::getenv("NWII_SKIP_BOOT_NOTICES");
        return value && value[0] == '1' && value[1] == '\0';
    }();
    if (ctx.gpr[18] != 0x803F2418) {
        return;
    }
    const uint32_t object = ctx.gpr[15];
    const bool backed = (object >= 0x80000000 && object <= 0x81800000 - 24)
        || (object >= 0x90000000 && object <= 0x94000000 - 24);
    if (!backed || (object & 3)) {
        return;
    }
    const uint32_t previous = ctx.mmu.read32(object + 16);
    const uint32_t next = pc_boot_index(previous, enabled);
    if (next != previous) {
        ctx.mmu.write32(object + 16, next);
        std::cerr << "[PCBoot] skipped console notice index=" << previous << " next=" << next << '\n';
    }
}
}

#pragma once

namespace nwii::runtime {
extern bool experimentPlayrecordOpened;
inline bool experiment_playrecord_read_flush(CPUContext& context) {
    if (std::getenv("SHSM_PLAYRECORD_READ_DISABLED") || stmSubmitted != 44 || !experimentPlayrecordOpened ||
        context.msr != 0x32 || context.lr != 0x80242240 || context.gpr[3] != 0x935e0100 || context.gpr[4] != 1 ||
        !devices::experiment_stm_pending() || bat_memory_read32(context,0x804931d0) != 4 ||
        bat_memory_read32(context,0x80528a40) != 2 || bat_memory_read32(context,0x804b2b4c) != 0x935e0120 ||
        bat_memory_read32(context,0x935e1280) != 0x802464b0 ||
        bat_memory_read32(context,0x935e1284) != 0x8049325c || bat_memory_read32(context,0x80493260) != 0x8021cde0) {
        return false;
    }
    const std::array<uint32_t,10> expected{3,1,4,0x493120,128,32,0x80492260,32,0x80240680,0x935e1180};
    for (unsigned index = 0; index < expected.size(); ++index) {
        if (bat_memory_read32(context,0x935e00e0 + index * 4) != expected[index]) {
            return false;
        }
    }
    return true;
}
}

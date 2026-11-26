#pragma once

namespace nwii::runtime {
extern bool experimentPlayrecordReadReplied;
inline bool experiment_playrecord_seek_flush(CPUContext& context) {
    if (std::getenv("SHSM_PLAYRECORD_SEEK_DISABLED") || stmSubmitted != 46 || !experimentPlayrecordReadReplied ||
        context.msr != 0x32 || context.lr != 0x80242240 || context.gpr[3] != 0x935e00a0 || context.gpr[4] != 1 ||
        !devices::experiment_stm_pending() || bat_memory_read32(context,0x804931d0) != 4 ||
        bat_memory_read32(context,0x80528a40) != 3 || bat_memory_read32(context,0x8052ab40) != 1 ||
        bat_memory_read32(context,0x804b2b4c) != 0x935e0120 ||
        bat_memory_read32(context,0x935e1120) != 0x802464b0 ||
        bat_memory_read32(context,0x935e1124) != 0x8049325c || bat_memory_read32(context,0x80493260) != 0x8021cde0) {
        return false;
    }
    const std::array<uint32_t,10> expected{5,4,4,0,0,2,0x8053fd70,0,0x80240680,0x935e1020};
    for (unsigned index = 0; index < expected.size(); ++index) {
        if (bat_memory_read32(context,0x935e0080 + index * 4) != expected[index]) {
            return false;
        }
    }
    return true;
}
}

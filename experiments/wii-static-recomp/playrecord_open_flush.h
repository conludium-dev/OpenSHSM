#pragma once

namespace nwii::runtime {
extern bool experimentPostConsumptionClosed;
inline bool experiment_playrecord_open_flush(CPUContext& context) {
    if (std::getenv("SHSM_PLAYRECORD_FLUSH_DISABLED") || stmSubmitted != 42 || !experimentPostConsumptionClosed ||
        context.msr != 0xa032 || context.lr != 0x8024250c || context.gpr[3] != 0x935e1060 ||
        context.gpr[4] != 2 || context.gpr[27] != 0x935e1020 || context.gpr[28] != 3 ||
        context.gpr[29] != 0x80240680 || context.gpr[30] || context.gpr[31] != 0x935e0080 ||
        !devices::experiment_stm_pending() || bat_memory_read32(context, 0x80528ce8) != 0xffffffff ||
        bat_memory_read32(context, 0x804b2b4c) != 0x935e00c0 ||
        bat_memory_read32(context, 0x935e1120) != 0x80244e30 ||
        bat_memory_read32(context, 0x935e1124) != 0x8049325c || bat_memory_read32(context, 0x935e1128)) {
        return false;
    }
    constexpr char path[] = "/title/00000001/00000002/data/play_rec.dat";
    for (unsigned index = 0; index < sizeof(path); ++index) {
        if (bat_memory_read8(context, 0x935e1020 + index) != uint8_t(path[index])) { return false; }
    }
    const std::array<uint32_t, 10> packet{1, 0, 0, 0x16, 1, 2, 0x8053fd70, 0, 0x80240680, 0x935e1020};
    for (unsigned index = 0; index < packet.size(); ++index) {
        if (bat_memory_read32(context, 0x935e0080 + index * 4) != packet[index]) { return false; }
    }
    return true;
}
}

#pragma once

namespace nwii::runtime {
extern bool experimentDiBurstFirstRetired;
extern unsigned experimentDiBurstInputInvalidates;
inline bool experiment_es_di_ticket_flush(CPUContext& context) {
    if (std::getenv("SHSM_ES_DI_TICKET_FLUSH_DISABLED") || stmSubmitted != 36 || context.msr != 0xa032 ||
        context.gpr[29] != 0x935e0080 || context.gpr[30] != 0x8053ff10 ||
        !experimentDiBurstFirstRetired || experimentDiBurstInputInvalidates != 1 ||
        !devices::experiment_stm_pending()) {
        return false;
    }
    const std::array<uint32_t, 8> expected{7, 1, 4, 0x1b, 1, 1, 0x8053ff10, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (bat_memory_read32(context, 0x935e0080 + index * 4) != expected[index]) {
            return false;
        }
    }
    if (bat_memory_read32(context, 0x8053ff10) || bat_memory_read32(context, 0x8053ff14) ||
        bat_memory_read32(context, 0x8053ff1c) != 216) {
        return false;
    }
    const auto output = bat_memory_read32(context, 0x8053ff18);
    return (context.lr == 0x80242fc8 && context.gpr[3] == 0x80540060 && context.gpr[4] == 7 &&
        context.gpr[27] == 8 && output == 0x8053ff80) ||
        (context.lr == 0x80243068 && context.gpr[3] == 0x8053ff30 && context.gpr[4] == 1 && output == 0x53ff80);
}
}

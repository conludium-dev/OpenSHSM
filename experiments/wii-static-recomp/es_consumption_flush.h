#pragma once

namespace nwii::runtime {
extern bool experimentInquiryTicketReturned;
extern bool experimentInquiryReplyActive;
extern unsigned experimentInquiryInputInvalidates;
inline bool experiment_es_consumption_flush(CPUContext& context) {
    if (std::getenv("SHSM_ES_CONSUMPTION_FLUSH_DISABLED") || stmSubmitted != 38 || context.msr != 0xa032 ||
        context.gpr[29] != 0x935e0080 || context.gpr[30] != 0x8053fd70 ||
        !experimentInquiryTicketReturned || !experimentInquiryReplyActive || experimentInquiryInputInvalidates != 1 ||
        !devices::experiment_stm_pending() || bat_memory_read32(context, 0x804983c8) ||
        bat_memory_read32(context, 0x8052ac50) || bat_memory_read32(context, 0x804b2b4c) != 0x935e00c0 ||
        bat_memory_read16(context, 0x800030e6) != 0x8002) {
        return false;
    }
    const std::array<uint32_t, 8> packet{7, 0, 4, 0x16, 1, 2, 0x8053fd70, 0};
    for (unsigned index = 0; index < 8; ++index) {
        if (bat_memory_read32(context, 0x935e0080 + index * 4) != packet[index]) {
            return false;
        }
    }
    uint32_t input = 0x8053fca0;
    uint32_t output = 0x8053fcc0;
    bool site = context.lr == 0x80242fc8 && context.gpr[3] == 0x8053fce0 && context.gpr[4] == 1 &&
        context.gpr[27] == 8 && context.gpr[28] == 8;
    if (context.lr == 0x80243020 && context.gpr[3] == 0x8053fcc0 && context.gpr[4] == 1 &&
        !context.gpr[27] && !context.gpr[28]) {
        output = 0x53fcc0;
        site = true;
    }
    if (context.lr == 0x80243068 && context.gpr[3] == 0x8053fdb0 && context.gpr[4] == 2) {
        input = 0x53fca0;
        output = 0x53fcc0;
        site = true;
    }
    const std::array<uint32_t, 6> vectors{input, 8, 0, 0, output, 4};
    for (unsigned index = 0; index < 6; ++index) {
        if (bat_memory_read32(context, 0x8053fd70 + index * 4) != vectors[index]) {
            return false;
        }
    }
    return site;
}
}

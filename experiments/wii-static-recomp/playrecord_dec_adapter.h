#pragma once
#include "dec_clock_adapter.h"

namespace nwii::runtime {
inline void experiment_playrecord_dec_write(CPUContext& context,uint32_t value) {
    if (std::getenv("SHSM_PLAYRECORD_DEC_DISABLED")) {
        throw std::runtime_error("UNVERIFIED_PROCESSOR_REGISTER_22");
    }
    if (context.pc != 0x802106e0 || context.lr != 0x80212078 || context.msr != 0x32 ||
        value != 0x7fffffff || stmSubmitted != 48 || !experimentPlayrecordSeekReplied ||
        !experimentPlayrecordReadRetired || bat_memory_read32(context,0x80528a40) != 4 ||
        bat_memory_read32(context,0x8052ab40) != 1 || bat_memory_read32(context,0x804931d0) != 4 ||
        bat_memory_read32(context,0x804b2b4c) != 0x935e00c0 || !devices::experiment_stm_pending()) {
        throw std::runtime_error("DEC original play-record alarm caller/state unverified");
    }
    experiment_write_dec(context,value);
    std::cout << "PLAYRECORD_DEC_PROGRAMMED " << std::hex << value << ' ' << context.dec_written_tb << ' '
        << context.dec_irq_pending << ' ' << static_cast<ClockContext&>(context).decCounterArmed
        << std::dec << std::endl;
}
}

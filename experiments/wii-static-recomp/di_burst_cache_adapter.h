#pragma once

namespace nwii::runtime {
inline unsigned experimentDiBurstInputInvalidates = 0;
inline bool experiment_di_burst_reply_ready(const hw::ExperimentIpcSnapshot& ipc) {
    return ipc.ppcControl == 0x34 || (ipc.ppcControl == 0x3c && stmSubmitted == 36 &&
        experimentDiBurstFirstRetired && experimentDiBurstReplyOwner == 0x135e0140 &&
        experiment_di_burst_arm_match(ipc.ppcMessage, ipc.armMessage));
}
inline void experiment_di_burst_es_return_observe(CPUContext& context) {
    if (stmSubmitted == 36) {
        std::cout << "DI_BURST_ES_SOURCE " << std::hex << context.gpr[3] << ' ' << context.msr << ' '
            << bat_memory_read32(context, 0x80528ce8) << std::dec << std::endl;
    }
}
inline void experiment_di_burst_cache_operation(CPUContext& context, uint32_t address, unsigned operation) {
    if (operation == 470 && address == 0x135e2560 && stmSubmitted == 36 &&
        context.pc == 0x80212fa0 && context.lr == 0x80241d88 && context.msr == 0x30 &&
        context.gpr[31] == 0x935e0080 && context.gpr[4] == 1 && context.ctr == 1 &&
        experiment_di_burst_arm_match(hw::experiment_ipc_snapshot().ppcMessage, hw::experiment_ipc_snapshot().armMessage)) {
        const std::array<uint32_t, 8> expected{8, 1, 6, 0x86, 0x135e2560, 32, 0, 0};
        for (unsigned index = 0; index < 8; ++index) {
            if (bat_memory_read32(context, 0x935e0080 + index * 4) != expected[index]) {
                throw std::runtime_error("DI86 laboratory input dcbi packet unverified");
            }
        }
        if (bat_memory_read32(context, 0x804983a8) != 0x01000000 ||
            bat_memory_read32(context, 0x804b2b4c) != 0x935e0180 || experimentDiBurstInputInvalidates) {
            throw std::runtime_error("DI86 laboratory input dcbi lifetime unverified");
        }
        ++experimentDiBurstInputInvalidates;
        std::cout << "DI86_INPUT_DCBI_LAB_OBSERVED_UNCHANGED" << std::endl;
        return;
    }
    bat_memory_cache_operation(context, address, operation);
}
}

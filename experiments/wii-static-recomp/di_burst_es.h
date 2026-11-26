#pragma once

namespace nwii::runtime {
inline uint32_t experimentDiBurstReplyOwner = 0x135e0080;
inline bool experimentDiBurstFirstRetired = false;
inline bool experiment_di_burst_arm_match(uint32_t message, uint32_t arm) {
    return stmSubmitted == 36 && message == 0x135e0140 && arm == experimentDiBurstReplyOwner &&
        experimentDiBurstPending == std::array<uint32_t, 3>{0x135e0080, 0x135e00e0, 0x135e0140};
}

inline void experiment_di_burst_es_guard(CPUContext& context, uint32_t address, bool store) {
    const auto ipc = hw::experiment_ipc_snapshot();
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, store);
    if (context.msr != 0x30 || memory_context(context).hid0 != 0xc200 ||
        bat_memory_read32(context, 0x800000d4) != 0x80492a70 || bat_memory_read32(context, 0x800000e4) ||
        bat_memory_read32(context, 0x80492934) != 0x935e016c ||
        bat_memory_read32(context, 0x935e016c) != 0x80492658 || bat_memory_read32(context, 0x935e0170) != 0x80492658 ||
        ipc.ppcControl != 0x30 || ipc.armMessage != 0x135e0080 || ipc.armControl || ipc.delay ||
        ipc.ppcMask != 0x40000000 || hw::pi_intmr.load() != 0x40f8 ||
        mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5 ||
        context.in_callback || context.callback_depth || !context.backup_stack.empty() ||
        experimentDiBurstPending[0] != 0x135e0080 || experimentDiBurstPending[1] != 0x135e00e0 || experimentDiBurstPending[2]) {
        throw std::runtime_error("Concurrent ES sender state unverified");
    }
}

inline bool experiment_di_burst_es_write(CPUContext& context, uint32_t address, uint32_t value) {
    if (context.pc != 0x80241c30 || (stmSubmitted != 34 && stmSubmitted != 35) ||
        (context.lr != 0x8024204c && context.lr != 0x80242094)) {
        return false;
    }
    experiment_di_burst_es_guard(context, address, true);
    const auto ipc = hw::experiment_ipc_snapshot();
    const uint32_t head = stmSubmitted == 34 ? 17 : 18;
    if (bat_memory_read32(context, 0x804b2a80) != head || bat_memory_read32(context, 0x804b2a84) != 18) {
        throw std::runtime_error("Concurrent ES FIFO unverified");
    }
    if (stmSubmitted == 34 && context.lr == 0x8024204c && address == 0xcd000000 && value == 0x135e0140 && ipc.ppcMessage == 0x135e00e0) {
        const auto* packet = experiment_ipc_mem1_span(context, value, 64);
        const std::array<uint32_t, 8> expected{1, 0, 0, 0x528cf0, 0, 0, 0, 0};
        for (unsigned index = 0; index < 8; ++index) {
            if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                throw std::runtime_error("Concurrent ES physical header unverified");
            }
        }
        for (unsigned index = 32; index < 64; ++index) {
            if (packet[index]) {
                throw std::runtime_error("Concurrent ES physical tail unverified");
            }
        }
        const std::array<uint8_t, 8> path{'/', 'd', 'e', 'v', '/', 'e', 's', 0};
        for (unsigned index = 0; index < 8; ++index) {
            if (*experiment_ipc_mem1_span(context, 0x528cf0 + index, 1) != path[index]) {
                throw std::runtime_error("Concurrent ES path unverified");
            }
        }
        MMIODispatcher::get().write32(address, value);
        ++stmSubmitted;
        return true;
    }
    if (stmSubmitted == 35 && context.lr == 0x80242094 && address == 0xcd000004 && value == 0x31 && ipc.ppcMessage == 0x135e0140) {
        experiment_di_burst_ack(context, 0x135e0140);
        ++stmSubmitted;
        return true;
    }
    throw std::runtime_error("Concurrent ES sender caller/value unverified");
}

inline bool experiment_di_burst_es_read(CPUContext& context, uint32_t address, uint32_t& value) {
    if (stmSubmitted != 35 || context.pc != 0x80241c20 || context.lr != 0x80242084 || address != 0xcd000004) {
        return false;
    }
    experiment_di_burst_es_guard(context, address, false);
    if (hw::experiment_ipc_snapshot().ppcMessage != 0x135e0140) {
        throw std::runtime_error("Concurrent ES control read owner unverified");
    }
    value = 0x30;
    return true;
}
}

#pragma once

namespace nwii::runtime {
inline std::array<uint32_t, 3> experimentDiBurstPending{};
void experiment_di_burst_ack(CPUContext& context, uint32_t request);

inline void experiment_di_burst_sender_guard(CPUContext& context) {
    const auto ipc = hw::experiment_ipc_snapshot();
    if (context.msr != 0x30 || (context.pc != 0x80241c30 && context.pc != 0x80241c20) ||
        bat_memory_read32(context, 0x800000d4) != 0x80492a70 ||
        bat_memory_read32(context, 0x800000e4) ||
        bat_memory_read32(context, 0x80492934) != 0x935e016c ||
        bat_memory_read32(context, 0x935e016c) != 0x80492658 ||
        bat_memory_read32(context, 0x935e0170) != 0x80492658 ||
        ipc.ppcControl != 0x30 || ipc.armMessage != 0x135e0080 || ipc.armControl || ipc.delay ||
        ipc.ppcMask != 0x40000000 || hw::pi_intmr.load() != 0x40f8 ||
        context.in_callback || context.callback_depth || !context.backup_stack.empty() ||
        experimentDiBurstPending[0] != 0x135e0080 || experimentDiBurstPending[1]) {
        throw std::runtime_error("Concurrent DI sender state outside measured profile");
    }
}

inline bool experiment_di_burst_sender_write(CPUContext& context, uint32_t address, uint32_t value) {
    if (context.pc != 0x80241c30 || context.msr != 0x30 ||
        (context.lr != 0x8024204c && context.lr != 0x80242094) ||
        (stmSubmitted != 32 && stmSubmitted != 33)) {
        return false;
    }
    experiment_di_burst_sender_guard(context);
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, true);
    if (mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5) {
        throw std::runtime_error("Concurrent DI sender BAT unverified");
    }
    if (stmSubmitted == 32 && context.lr == 0x8024204c && address == 0xcd000000 && value == 0x135e00e0 &&
        hw::experiment_ipc_snapshot().ppcMessage == 0x135e0080 &&
        bat_memory_read32(context, 0x804b2a80) == 16 && bat_memory_read32(context, 0x804b2a84) == 18) {
        const auto* packet = experiment_ipc_mem1_span(context, value, 64);
        const std::array<uint32_t, 8> expected{6, 0, 3, 0x12, 0x135e2580, 32, 0x492260, 32};
        for (unsigned index = 0; index < 8; ++index) {
            if (experiment_ipc_be32(packet + index * 4) != expected[index]) {
                throw std::runtime_error("Concurrent DI inquiry physical header unverified");
            }
        }
        for (unsigned index = 32; index < 64; ++index) {
            if (packet[index]) {
                throw std::runtime_error("Concurrent DI inquiry physical tail unverified");
            }
        }
        if (bat_memory_read32(context, 0x935e0100) != 0x802258a0 ||
            bat_memory_read32(context, 0x935e0104) != 0x804983c0 ||
            bat_memory_read32(context, 0x804983c0) != 0x80222f80 ||
            bat_memory_read32(context, 0x804983c8) != 0x01000000 ||
            bat_memory_read32(context, 0x804983cc) != 0xfeebdaed) {
            throw std::runtime_error("Concurrent DI inquiry callback unverified");
        }
        MMIODispatcher::get().write32(address, value);
        ++stmSubmitted;
        return true;
    }
    if (stmSubmitted == 33 && context.lr == 0x80242094 && address == 0xcd000004 && value == 0x31 &&
        hw::experiment_ipc_snapshot().ppcMessage == 0x135e00e0 &&
        bat_memory_read32(context, 0x804b2a80) == 17 && bat_memory_read32(context, 0x804b2a84) == 18) {
        experiment_di_burst_ack(context, 0x135e00e0);
        ++stmSubmitted;
        return true;
    }
    throw std::runtime_error("Concurrent DI sender caller/value unverified");
}

inline bool experiment_di_burst_sender_read(CPUContext& context, uint32_t address, uint32_t& value) {
    if (stmSubmitted != 33 || context.pc != 0x80241c20 || context.lr != 0x80242084 || address != 0xcd000004) {
        return false;
    }
    experiment_di_burst_sender_guard(context);
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, false);
    if (mapping.physical != 0x0d000004 || mapping.slot != 1 || mapping.wimg != 5 ||
        hw::experiment_ipc_snapshot().ppcMessage != 0x135e00e0) {
        throw std::runtime_error("Concurrent DI control read unverified");
    }
    value = 0x30;
    return true;
}
}

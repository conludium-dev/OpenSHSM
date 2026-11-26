#pragma once
#include "finite_mem2_clear.h"
#include "ipc_startup_frontend.h"

namespace nwii::runtime {
inline void experiment_ipc_ack_access(CPUContext& context, uint32_t address) {
    const auto mapping = resolve_reference_bat(bat_context(context).dbat, bat_context(context).hid4, context.msr, address, true);
    if (!experimentStmIrq || context.msr != 0x2030 || memory_context(context).hid0 != 0xc200 ||
        mapping.physical != (address & 0x1fffffffu) || mapping.slot != 1 || mapping.wimg != 5 ||
        hw::pi_intmr.load() != 0x40f8) {
        throw std::runtime_error("IPC ACK access profile unverified");
    }
}
inline uint32_t experiment_ipc_ack_read(CPUContext& context, uint32_t address) {
    if (context.pc != 0x80241c20 || address != 0xcd000004 ||
        (context.lr != 0x80241f24 && context.lr != 0x80241f44 && context.lr != 0x80241f58)) {
        throw std::runtime_error("IPC ACK read caller unverified");
    }
    experiment_ipc_ack_access(context, address);
    const auto ipc = hw::experiment_ipc_snapshot();
    if (ipc.ppcControl != 0x32 || ipc.ppcMessage != 0x135e0020 || ipc.armMessage || ipc.armControl || ipc.delay) {
        throw std::runtime_error("IPC ACK read hardware state unverified");
    }
    return ipc.ppcControl;
}
inline void experiment_ipc_ack_write(CPUContext& context, uint32_t address, uint32_t value) {
    if (!experimentStmIrq) { experiment_ipc_startup_store(context, address, value); return; }
    experiment_ipc_ack_access(context, address);
    if (context.pc != 0x80241c30 || context.lr != 0x80241f68 || address != 0xcd000004 || value != 0x32 ||
        hw::experiment_ipc_snapshot().ppcControl != 0x32) {
        throw std::runtime_error("IPC ACK write caller/value unverified");
    }
    hw::experiment_ipc_control_latched_irq(value);
}
inline void experiment_ipc_ack_clear(CPUContext& context, uint32_t address, uint32_t value) {
    experiment_ipc_ack_access(context, address);
    if (context.pc != 0x80241f68 || address != 0xcd000030 || value != 0x40000000 ||
        hw::experiment_ipc_snapshot().ppcControl != 0x30) {
        throw std::runtime_error("IPC ACK flag clear unverified");
    }
    hw::experiment_ipc_irq_clear(value);
    hw::experiment_ipc_irq_update();
}
}

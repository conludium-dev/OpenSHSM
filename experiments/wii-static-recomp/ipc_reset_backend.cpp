#define hle_set_ipc_arm_msg experiment_unused_vendor_arm_message
#include "hw_ipc.cpp"
#undef hle_set_ipc_arm_msg
#include "ipc_reset_backend.h"
#include <stdexcept>

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
MMU* g_mmu = nullptr;
int g_ipc_interrupt_delay = 0;
}

namespace nwii::runtime::hw {
static uint32_t experimentPpcMask = 0x40000000;
static uint32_t experimentPpcFlags = 0;

extern "C" int32_t handle_ios_ipc(CPUContext&, uint32_t) {
    throw std::runtime_error("IOS requests outside verified quiescent IPC reset");
}

ExperimentIpcSnapshot experiment_ipc_snapshot() {
    return {ipc_ppc_msg, ipc_arm_msg, ipc_ppc_ctrl, ipc_arm_ctrl, experimentPpcMask, g_ipc_interrupt_delay};
}

void experiment_ipc_quiescent_mask(uint32_t value) {
    if (ipc_ppc_msg || ipc_arm_msg || ipc_arm_ctrl || (ipc_ppc_ctrl & ~0x30u) || experimentPpcFlags ||
        g_ipc_interrupt_delay || (pi_intsr.load() & 0x4000u) || g_ctx_ptr || g_mmu) {
        throw std::runtime_error("In-flight IPC reset requires verified IOS queues/events");
    }
    if (value & 0x40000000u) {
        ipc_ppc_ctrl = 0;
        experimentPpcMask = 0x40000000;
    } else {
        experimentPpcMask = value;
    }
}

void experiment_ipc_control_no_request(uint32_t value) {
    if ((value & ~0x3eu) || (ipc_ppc_ctrl & 1u) || g_ctx_ptr || g_mmu || g_ipc_interrupt_delay) {
        throw std::runtime_error("IPC control projection cannot send requests or service active runtime");
    }
    ipc_ppc_ctrl = (ipc_ppc_ctrl & 6u & ~value) | (value & 0x38u);
}

ExperimentIpcIrqSnapshot experiment_ipc_irq_snapshot() {
    return {experimentPpcFlags, pi_intsr.load()};
}

void experiment_ipc_control_latched_irq(uint32_t value) {
    experiment_ipc_control_no_request(value);
    if (((value & 4u) && (ipc_ppc_ctrl & 0x10u)) || ((value & 2u) && (ipc_ppc_ctrl & 0x20u))) {
        experimentPpcFlags |= 0x40000000;
    }
}

void experiment_ipc_irq_clear(uint32_t value) {
    if (value != 0x40000000 || (ipc_ppc_ctrl & 1u) || g_ctx_ptr || g_mmu || g_ipc_interrupt_delay) {
        throw std::runtime_error("IRQFLAG clear outside bounded IPC projection");
    }
    experimentPpcFlags &= ~value;
}

void experiment_ipc_irq_update() {
    if (((ipc_ppc_ctrl & 4u) && (ipc_ppc_ctrl & 0x10u)) || ((ipc_ppc_ctrl & 2u) && (ipc_ppc_ctrl & 0x20u))) {
        experimentPpcFlags |= 0x40000000;
    }
    if (experimentPpcFlags & experimentPpcMask) {
        pi_intsr.fetch_or(0x4000);
    } else {
        pi_intsr.fetch_and(~0x4000u);
    }
}
}

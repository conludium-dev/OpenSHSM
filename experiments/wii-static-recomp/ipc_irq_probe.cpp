#include "ipc_reset_backend.cpp"
#include "runtime/event_scheduler.h"
#include <iostream>

int main() {
    using namespace nwii::runtime;
    CPUContext context;
    unsigned index, before, value, request, reply;
    while (std::cin >> index >> before >> value >> request >> reply) {
        EventScheduler::get().reset();
        hw::experimentPpcFlags = 0;
        hw::pi_intsr = 0x10000;
        hw::ipc_ppc_ctrl = before;
        hw::ipc_ppc_msg = request;
        hw::ipc_arm_msg = reply ? request : 0;
        hw::experiment_ipc_control_latched_irq(value);
        EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) { hw::experiment_ipc_irq_update(); });
        EventScheduler::get().advance(context, 1);
        const auto afterControl = hw::experiment_ipc_snapshot();
        const auto latched = hw::experiment_ipc_irq_snapshot();
        hw::experiment_ipc_control_latched_irq(0x38);
        hw::experiment_ipc_irq_clear(0x40000000);
        if (!reply) {
            hw::ipc_ppc_ctrl |= 4;
            hw::ipc_arm_msg = request;
        }
#ifdef SHSM_SYNC_IRQ_CLEAR_MUTANT
        hw::pi_intsr.fetch_and(~0x4000u);
#endif
        const auto immediate = hw::experiment_ipc_irq_snapshot();
        const auto immediateControl = hw::experiment_ipc_snapshot();
        EventScheduler::get().schedule_after(1, [](CPUContext&, uint64_t) { hw::experiment_ipc_irq_update(); });
        EventScheduler::get().advance(context, 2);
        const auto later = hw::experiment_ipc_irq_snapshot();
        const auto laterControl = hw::experiment_ipc_snapshot();
        std::cout << "IPC_IRQ " << index << ' ' << afterControl.ppcControl << ' ' << latched.piCause
                  << ' ' << immediate.piCause << ' ' << immediateControl.ppcControl << ' ' << immediateControl.armMessage
                  << ' ' << later.piCause << ' ' << laterControl.ppcControl << ' ' << laterControl.armMessage << '\n';
    }
    const auto old = hw::experiment_ipc_snapshot();
    const auto oldIrq = hw::experiment_ipc_irq_snapshot();
    bool refused = false;
    try {
        hw::experiment_ipc_irq_clear(0);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    const auto next = hw::experiment_ipc_snapshot();
    const auto nextIrq = hw::experiment_ipc_irq_snapshot();
    if (!refused || oldIrq.ppcFlags != nextIrq.ppcFlags || oldIrq.piCause != nextIrq.piCause
        || old.ppcControl != next.ppcControl || old.armMessage != next.armMessage) {
        return 9;
    }
    std::cout << "IPC_IRQ_REFUSAL 1\n";
}

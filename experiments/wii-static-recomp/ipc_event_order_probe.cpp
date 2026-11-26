#include "ipc_reset_backend.cpp"
#include "runtime/event_scheduler.h"
#include <iostream>

using namespace nwii::runtime;

namespace nwii::runtime::hw {
void experiment_fixture_reply_after(uint32_t request, uint64_t delay, EventScheduler::Callback beforeReply = {}) {
    EventScheduler::get().schedule_after(delay, [request, beforeReply](CPUContext& context, uint64_t late) {
        if (ipc_ppc_ctrl & 6u) {
            experiment_fixture_reply_after(request, 1, beforeReply);
            return;
        }
        if (beforeReply) {
            beforeReply(context, late);
        }
        ipc_arm_msg = request;
        ipc_ppc_ctrl |= 4;
    });
}

void experiment_fixture_mask(uint32_t value) {
    if (value & 0x40000000) {
        ipc_ppc_msg = 0;
        ipc_arm_msg = 0;
        ipc_ppc_ctrl = 0;
        ipc_arm_ctrl = 0;
        experimentPpcMask = 0x40000000;
    } else {
        experimentPpcMask = value;
    }
}
}

int main() {
    CPUContext context;
    context.msr = 0x2030;
    for (unsigned index = 0; index < 8; ++index) {
        EventScheduler::get().reset();
        const bool reply = index & 2;
        const auto request = 0x6a0000u + index * 64;
        hw::ipc_ppc_ctrl = reply ? 0x34 : 0x32;
        hw::ipc_arm_msg = reply ? request : 0;
        hw::ipc_ppc_msg = request;
        hw::ipc_arm_ctrl = 0;
        if (!reply) {
            hw::experiment_fixture_reply_after(request, 1);
        }
        hw::experiment_fixture_mask(index & 1 ? 0x40000000 : 0);
        const auto immediate = hw::experiment_ipc_snapshot();
        EventScheduler::get().advance(context, 1);
        const auto later = hw::experiment_ipc_snapshot();
        std::cout << "IPC_EVENT_CASE " << index << ' ' << immediate.ppcControl << ' ' << immediate.armMessage
                  << ' ' << later.ppcControl << ' ' << later.armMessage << '\n';
        if (!(index & 1) && !reply) {
            hw::experiment_fixture_mask(0x40000000);
            EventScheduler::get().advance(context, 2);
            const auto released = hw::experiment_ipc_snapshot();
            if (released.ppcControl != 4 || released.armMessage != request) {
                return 9;
            }
        }
    }
    return 0;
}

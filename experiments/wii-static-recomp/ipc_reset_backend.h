#pragma once
#include <cstdint>

namespace nwii::runtime::hw {
struct ExperimentIpcSnapshot {
    uint32_t ppcMessage;
    uint32_t armMessage;
    uint32_t ppcControl;
    uint32_t armControl;
    uint32_t ppcMask;
    int delay;
};
ExperimentIpcSnapshot experiment_ipc_snapshot();
void experiment_ipc_quiescent_mask(uint32_t value);
void experiment_ipc_control_no_request(uint32_t value);
struct ExperimentIpcIrqSnapshot {
    uint32_t ppcFlags;
    uint32_t piCause;
};
ExperimentIpcIrqSnapshot experiment_ipc_irq_snapshot();
void experiment_ipc_control_latched_irq(uint32_t value);
void experiment_ipc_irq_clear(uint32_t value);
void experiment_ipc_irq_update();
}

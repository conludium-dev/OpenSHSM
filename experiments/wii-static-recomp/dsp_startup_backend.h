#pragma once
#include "runtime/event_scheduler.h"
#include "runtime/cpu_context.h"
#include <array>
#include <vector>

namespace nwii::runtime::hw {
struct ExperimentDspStartup {
    bool enabled = false;
    bool lostDma = false;
    bool wrongMail = false;
    bool lostMail = false;
    bool schedulingDma = false;
    unsigned command = 0;
    unsigned completedDmas = 0;
    std::vector<std::array<uint32_t, 3>> accesses;
    std::vector<uint64_t> accessTicks;
};
extern ExperimentDspStartup experimentDspStartup;
void experiment_dsp_startup_reset();
uint32_t experiment_dsp_startup_read(CPUContext& context, uint32_t address, unsigned width);
void experiment_dsp_startup_write(CPUContext& context, uint32_t address, uint32_t value, unsigned width);
}

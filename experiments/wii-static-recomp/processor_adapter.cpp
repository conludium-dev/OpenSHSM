#include "processor_adapter.h"
#include <algorithm>
#include <stdexcept>

namespace nwii::runtime {
uint32_t experiment_read_hid2(CPUContext& context) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged HID2 access in user mode is not implemented");
    }
    return static_cast<ProcessorContext&>(context).hid2;
}

void experiment_write_hid2(CPUContext& context, uint32_t value) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged HID2 access in user mode is not implemented");
    }
    auto& processor = static_cast<ProcessorContext&>(context);
    processor.hid2 = (value & 0xf0ff0000) | (processor.hid2 & 0x0f000000);
}

uint32_t experiment_read_hid0(CPUContext& context) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged HID0 access in user mode is not implemented");
    }
    return static_cast<ProcessorContext&>(context).hid0;
}

void experiment_write_hid0(CPUContext& context, uint32_t value) {
    if (context.msr & 0x4000) {
        throw std::runtime_error("Privileged HID0 access in user mode is not implemented");
    }
    auto& processor = static_cast<ProcessorContext&>(context);
    if ((value ^ processor.hid0) & ~0x800u) {
        throw std::runtime_error("HID0 control-bit effects beyond verified instruction cache invalidation are unavailable");
    }
    if (value & 0x800) {
        if (processor.instructionImages.empty()) {
            throw std::runtime_error("Instruction cache image is not registered");
        }
        for (const auto& [address, image] : processor.instructionImages) {
            auto actual = processor.mmu.get_ptr(address);
            if (!actual || !processor.mmu.get_ptr(address + image.size() - 1) || !std::equal(image.begin(), image.end(), actual)) {
                throw std::runtime_error("Modified guest code requires recompilation before instruction cache invalidation");
            }
        }
        ++processor.instructionCacheInvalidations;
    }
    processor.hid0 = value & ~0x800u;
}
}

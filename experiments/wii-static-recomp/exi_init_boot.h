#pragma once
#include "set_mask_pi_boot.h"
#include "exi_init_backend.h"

namespace nwii::runtime {
inline void experiment_exi_init_boot_guard(CPUContext& context, uint32_t address) {
    if (context.msr != 0x2030 || memory_context(context).hid0 != 0xc200
        || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)
        || context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("EXI initialization outside verified idle boot profile");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != (address & 0x1fffffffu) || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("EXI initialization BAT mapping unverified");
    }
}

inline uint32_t experiment_exi_init_boot_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    constexpr std::array<uint32_t, 3> reads{0x8020e910, 0x8020e920, 0x8020e930};
    unsigned channel = 3;
    for (unsigned index = 0; index < 3; ++index) {
        if (address == 0xcd00680c + index * 20 && instruction == reads[index]) {
            channel = index;
        }
    }
    if (channel == 3) {
        throw std::runtime_error("EXI idle read caller/address unverified");
    }
    experiment_exi_init_boot_guard(context, address);
    static const bool registered = [] {
        hw::experiment_register_exi_idle_controls(MMIODispatcher::get());
        return true;
    }();
    (void)registered;
    const auto value = MMIODispatcher::get().read32(address);
    if (value) {
        throw std::runtime_error("EXI busy transfer state unverified");
    }
    std::cout << "EXI_INIT_IDLE_READ_ACCEPTED channel=" << channel << '\n';
    return value;
}

inline void experiment_exi_init_boot_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    const bool matched = (instruction == 0x8020e954 && address == 0xcd006800 && value == 0)
        || (instruction == 0x8020e958 && address == 0xcd006814 && value == 0)
        || (instruction == 0x8020e95c && address == 0xcd006828 && value == 0)
        || (instruction == 0x8020e964 && address == 0xcd006800 && value == 0x2000);
    if (!matched) {
        throw std::runtime_error("EXI initialization writer caller/address/value unverified");
    }
    experiment_exi_init_boot_guard(context, address);
    hw::experiment_exi_init_csr_write(address, value);
    std::cout << "EXI_INIT_CSR_WRITE_ACCEPTED instruction=" << std::hex << instruction << std::dec << '\n';
}
}

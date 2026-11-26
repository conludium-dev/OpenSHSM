#pragma once
#include "mi_mask_boot.h"

namespace nwii::runtime {
inline void experiment_dsp_boot_guard(CPUContext& context, uint32_t address, uint32_t instruction) {
    if (address != 0xcc00500a || (instruction != 0x802176f4 && instruction != 0x80217724)
        || context.msr != 0x2030 || memory_context(context).hid0 != 0xc200
        || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)) {
        throw std::runtime_error("DSP mask outside verified boot profile");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("DSP mask with pending delivery unverified");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0c00500a || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("DSP mask BAT mapping unverified");
    }
}

inline uint16_t experiment_dsp_boot_read16(CPUContext& context, uint32_t address, uint32_t instruction) {
    experiment_dsp_boot_guard(context, address, instruction);
    static const bool registered = [] {
        auto& dispatcher = MMIODispatcher::get();
        hw::register_dsp(dispatcher);
        if (dispatcher.read16(0xcc00500a) != 0x0800) {
            throw std::runtime_error("Unexpected vendor DSP initial state");
        }
        dispatcher.write16(0xcc00500a, 0x0804);
        return true;
    }();
    (void)registered;
    const auto value = MMIODispatcher::get().read16(address);
    if (value != 0x0804) {
        throw std::runtime_error("DSP boot loader read unverified");
    }
    std::cout << "DSP_MASK_BOOT_READ_ACCEPTED value=804 loader-seed\n";
    return value;
}

inline void experiment_dsp_boot_write16(CPUContext& context, uint32_t address, uint16_t value, uint32_t instruction) {
    experiment_dsp_boot_guard(context, address, instruction);
    if ((value & ~0x0150u) != 0x0804 || MMIODispatcher::get().read16(address) != 0x0804) {
        throw std::runtime_error("DSP boot mask value or preceding state unverified");
    }
    const auto cause = hw::pi_intsr.load();
    MMIODispatcher::get().write16(address, value);
    if (MMIODispatcher::get().read16(address) != value || hw::pi_intsr.load() != cause) {
        throw std::runtime_error("DSP boot mask readback/PI mismatch");
    }
    std::cout << "DSP_MASK_BOOT_WRITE_ACCEPTED value=" << std::hex << value << std::dec << '\n';
}

inline uint32_t experiment_dsp_next_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    try {
        return bat_memory_read32(context, address);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction
                << " address=" << address << " length=4 read";
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        message << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}
}

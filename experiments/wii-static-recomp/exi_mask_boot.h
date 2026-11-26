#pragma once
#include "ai_mask_boot.h"
#include "exi_mask_backend.h"

namespace nwii::runtime {
inline unsigned experiment_exi_boot_guard(CPUContext& context, uint32_t address, uint32_t instruction, bool writing) {
    constexpr std::array<uint32_t, 3> reads{0x80217760, 0x802177a4, 0x802177e8};
    constexpr std::array<uint32_t, 3> writes{0x80217794, 0x802177d8, 0x8021780c};
    unsigned channel = 3;
    for (unsigned index = 0; index < 3; ++index) {
        if (address == 0xcd006800 + index * 20 && instruction == (writing ? writes[index] : reads[index])) {
            channel = index;
        }
    }
    if (channel == 3 || context.msr != 0x2030 || memory_context(context).hid0 != 0xc200
        || (hw::pi_intsr.load() != 0 && hw::pi_intsr.load() != 0x10000)) {
        throw std::runtime_error("EXI mask outside verified boot profile");
    }
    if (context.in_callback || context.callback_depth || !context.backup_stack.empty()
        || context.dispatch_saved_ctx || context.ext_resched_pending || context.exception_pc
        || context.vblank_pending.load() || context.dec_irq_pending || context.pending_cb_count.load()
        || !context.pending_callbacks.empty()) {
        throw std::runtime_error("EXI mask with pending delivery unverified");
    }
    const auto& state = bat_context(context);
    const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
    if (mapping.physical != 0x0d006800 + channel * 20 || mapping.wimg != 5 || mapping.slot != 1) {
        throw std::runtime_error("EXI mask BAT mapping unverified");
    }
    return channel;
}

inline uint32_t experiment_exi_boot_read32(CPUContext& context, uint32_t address, uint32_t instruction) {
    const auto channel = experiment_exi_boot_guard(context, address, instruction, false);
    static const bool registered = [] {
        hw::experiment_register_exi_masks(MMIODispatcher::get());
        return true;
    }();
    (void)registered;
    constexpr std::array<uint32_t, 3> initial{0x1800, 0x0880, 0};
    const auto value = MMIODispatcher::get().read32(address);
    if (value != initial[channel]) {
        throw std::runtime_error("EXI boot loader channel state unverified");
    }
    std::cout << "EXI_MASK_BOOT_READ_ACCEPTED channel=" << channel << '\n';
    return value;
}

inline void experiment_exi_boot_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    const auto channel = experiment_exi_boot_guard(context, address, instruction, true);
    if (value != hw::experimentExiWriteBase[channel]) {
        throw std::runtime_error("EXI boot mask enable unverified");
    }
    const auto before = MMIODispatcher::get().read32(address);
    const auto cause = hw::pi_intsr.load();
    MMIODispatcher::get().write32(address, value);
    if (MMIODispatcher::get().read32(address) != before || hw::pi_intsr.load() != cause) {
        throw std::runtime_error("EXI boot mask readback/PI mismatch");
    }
    std::cout << "EXI_MASK_BOOT_WRITE_ACCEPTED channel=" << channel << '\n';
}

inline void experiment_exi_next_write32(CPUContext& context, uint32_t address, uint32_t value, uint32_t instruction) {
    try {
        bat_memory_write32(context, address, value);
    } catch (const std::runtime_error& failure) {
        std::ostringstream message;
        message << failure.what() << "; memory instruction=" << std::hex << instruction
                << " address=" << address << " value=" << value << " length=4 write";
        const auto& state = bat_context(context);
        const auto mapping = resolve_reference_bat(state.dbat, state.hid4, context.msr, address, false);
        message << " physical=" << mapping.physical << " wimg=" << mapping.wimg << " slot=" << mapping.slot;
        throw std::runtime_error(message.str());
    }
}
}

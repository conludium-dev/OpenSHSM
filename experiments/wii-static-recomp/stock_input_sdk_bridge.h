#pragma once
#include "stock_input_sample_bridge.h"

namespace openshsm::experiment {

inline bool input_word(uint32_t address) {
    return (address & 3) == 0 && address >= 0x80000000 && address <= 0x817FFFFC;
}

inline void bootstrap_pc_primary_input(nwii::runtime::CPUContext& ctx) {
    const auto transition = sync_primary_connection(ctx);
    if (transition == ConnectionSyncResult::Connected || transition == ConnectionSyncResult::Disconnected) {
        reset_pc_sample(ctx);
    }
    if (transition == ConnectionSyncResult::Disconnected) {
        primary_desktop_look_runtime().disconnect();
        primary_desktop_qte_runtime().disconnect();
        primary_desktop_roll().release_gesture();
    }
}

inline void forward_pc_kpad_read(nwii::runtime::CPUContext& ctx, bool extended) {
    const uint32_t channel = ctx.gpr[3], destination = ctx.gpr[4], capacity = ctx.gpr[5];
    const uint32_t error_output = extended ? ctx.gpr[6] : 0;
    if (!extended) {
        ctx.gpr[6] = 0;
        ctx.gpr[7] = 0;
    }
    if (error_output != 0 && !input_word(error_output)) {
        ctx.gpr[3] = 0;
        ctx.pc = ctx.lr;
        return;
    }
    auto result = read_pc_primary_samples(ctx, channel, destination, capacity, true);
    if (result.count != 0) {
        const uint32_t oldest = destination + (result.count - 1) * 176;
        // PC hold samples complete the batch; only observed snapshots carry button edges.
        for (unsigned record = result.count; record < capacity; ++record) {
            const uint32_t target = destination + record * 176;
            for (unsigned offset = 0; offset < 176; ++offset) {
                ctx.mmu.write8(target + offset, ctx.mmu.read8(oldest + offset));
            }
            ctx.mmu.write32(target, ctx.mmu.read32(target) & 0x7FFFFFFFu);
            ctx.mmu.write32(target + 4, 0);
            ctx.mmu.write32(target + 8, 0);
            ctx.mmu.write_f32(target + 0x1C, 0);
            ctx.mmu.write_f32(target + 0x28, 0);
            ctx.mmu.write_f32(target + 0x2C, 0);
            ctx.mmu.write_f32(target + 0x30, 0);
        }
        result.count = capacity;
    }
    if (error_output != 0) {
        ctx.mmu.write32(error_output, uint32_t(result.error));
    }
    ctx.gpr[3] = result.count;
    ctx.pc = ctx.lr;
}

// PC virtual extension and provider presence, not Wii Bluetooth/readiness emulation.
inline void forward_pc_wpad_probe(nwii::runtime::CPUContext& ctx) {
    const uint32_t channel = ctx.gpr[3], type_output = ctx.gpr[4];
    if (channel > 3 || (type_output != 0 && !input_word(type_output))) {
        ctx.gpr[3] = uint32_t(-6);
        ctx.pc = ctx.lr;
        return;
    }
    const bool connected = channel == 0 && nwii::runtime::input::InputManager::get().get_wiimote_state(0).err == 0;
    if (type_output != 0) {
        ctx.mmu.write32(type_output, connected ? 1 : 0xFD);
    }
    ctx.gpr[3] = connected ? 0 : uint32_t(-1);
    ctx.pc = ctx.lr;
}

}

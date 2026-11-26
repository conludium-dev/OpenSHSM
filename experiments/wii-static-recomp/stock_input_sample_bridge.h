#pragma once
#include "stock_input_connection_bridge.h"
#include "stock_desktop_roll.h"
#include "stock_desktop_look_bridge.h"
#include "stock_desktop_qte_bridge.h"
#include <array>
#include <cmath>

extern "C" void func_80278450(nwii::runtime::CPUContext&);

namespace openshsm::experiment {

struct SampleReadResult {
    unsigned count = 0;
    int error = -1;
    uint64_t generation = 0;
};

inline void reset_pc_sample(nwii::runtime::CPUContext& ctx) {
    constexpr uint32_t block = 0x804EFD58;
    for (unsigned i = 0; i < 176; ++i) {
        ctx.mmu.write8(block + i, 0);
    }
    ctx.mmu.write16(block + 0x500, 0);
    ctx.mmu.write16(block + 0x502, ctx.mmu.read16(block + 0x504));
    ctx.mmu.write16(block + 0x508, 0);
    ctx.mmu.write16(block + 0x50A, ctx.mmu.read16(block + 0x504));
    ctx.mmu.write8(block + 0x555, 0);
}

inline void sample_buttons(nwii::runtime::CPUContext& ctx, uint32_t type, uint32_t buttons, uint32_t extra) {
    const auto gpr = ctx.gpr;
    const auto cr = ctx.cr;
    const auto lr = ctx.lr, pc = ctx.pc, ctr = ctx.ctr, xer = ctx.xer;
    const auto msr = ctx.msr;
    const auto restore = [&]() {
        ctx.gpr = gpr;
        ctx.cr = cr;
        ctx.lr = lr;
        ctx.pc = pc;
        ctx.ctr = ctr;
        ctx.xer = xer;
        ctx.msr = msr;
    };
    ctx.gpr[3] = 0x804EFD58;
    ctx.gpr[4] = type;
    ctx.gpr[5] = 1;
    ctx.gpr[6] = buttons;
    ctx.gpr[7] = extra;
    ctx.gpr[8] = 0;
    ctx.pc = 0x80278450;
    ctx.lr = pc;
    ctx.msr &= ~0x8000u;
    try {
        func_80278450(ctx);
    } catch (...) {
        restore();
        throw;
    }
    const bool returned = ctx.pc == pc && ctx.gpr[1] == gpr[1];
    restore();
    if (!returned) {
        throw std::runtime_error("Original button helper did not return");
    }
}

// PC adaptation: ordered host snapshots become newest-first guest records, not raw Wii sensor reports.
inline SampleReadResult read_pc_primary_samples(nwii::runtime::CPUContext& ctx, unsigned channel,
    uint32_t destination, unsigned capacity, bool virtual_extension) {
    constexpr uint32_t block = 0x804EFD58;
    if (channel != 0 || capacity > 16 || ctx.gpr[13] != 0x8052E720 || ctx.gpr[1] < 0x80000040
        || ctx.gpr[1] > 0x817FFFF0 || (ctx.gpr[1] & 3) != 0) {
        return {0, -6, 0};
    }
    if (capacity == 0) {
        return {};
    }
    const uint32_t bytes = capacity * 176;
    const uint64_t end = uint64_t(destination) + bytes;
    if ((destination & 3) != 0 || destination < 0x80000000 || end > 0x81800000
        || (destination < block + 0x578 && end > block)
        || (destination < 0x804584F0 && end > 0x804579C0)
        || (destination < ctx.gpr[1] && end > ctx.gpr[1] - 0x40)) {
        return {0, -6, 0};
    }
    if (ctx.mmu.read32(block + 0x550) != 0x80009CF8) {
        return {0, -5, 0};
    }
    primary_desktop_look_runtime().validate_context(ctx);
    if (ctx.mmu.read8(block + 0x4FF) != 0) {
        return {0, -4, 0};
    }
    const uint32_t controller = ctx.mmu.read32(ctx.gpr[13] - 0x55C0);
    const bool controller_valid = (controller & 3u) == 0
        && ((controller >= 0x80000000 && controller <= 0x81800000 - 0x513A)
            || (controller >= 0x90000000 && controller <= 0x94000000 - 0x513A));
    primary_desktop_roll().publish_twist_context(virtual_extension && controller_valid
        && ctx.mmu.read8(controller + 0x5139) == 1, controller_valid ? controller : 0);
    const uint32_t interaction = virtual_extension ? DesktopLookRuntime::interaction_object(ctx) : 0;
    primary_desktop_look_input().publish_interaction(interaction);
    const uint32_t gui = ctx.mmu.read32(0x80529D20);
    primary_desktop_look_input().publish_menu(virtual_extension
        && nwii::runtime::Config::get().input_mode == 6 && interaction == 0
        && desktop_look_guest_span(gui, 0x698) && ctx.mmu.read32(gui + 0x694) != 0);
    std::array<std::array<uint8_t, 176>, 16> records{};
    SampleReadResult result;
    auto& input = nwii::runtime::input::InputManager::get();
    primary_desktop_qte_runtime().synchronize(ctx, virtual_extension, input.dropped_input(0));
    nwii::runtime::input::InputSnapshot snapshot;
    while (result.count < capacity && input.consume_input(0, snapshot)) {
        result.generation = snapshot.generation;
        const bool connected = snapshot.mote.err == 0;
        const auto transition = sync_primary_connection(ctx, connected);
        if (transition == ConnectionSyncResult::Connected || transition == ConnectionSyncResult::Disconnected) {
            reset_pc_sample(ctx);
        }
        if (!connected) {
            primary_desktop_look_runtime().disconnect();
            primary_desktop_qte_runtime().disconnect();
            return {0, -2, result.generation};
        }
        primary_desktop_look_runtime().consume(snapshot.look, snapshot.generation);
        primary_desktop_look_runtime().observe_interaction_button(snapshot.look.focused,
            (snapshot.mote.buttons & 0x0800) != 0);
        primary_desktop_qte_runtime().consume(snapshot.look, snapshot.generation);
        const uint32_t type = virtual_extension && snapshot.pad.err == 0 ? 1 : 0;
        const uint32_t extra = type == 1
            ? ((snapshot.pad.buttons & 0x100) != 0 ? 0x2000 : 0)
                | ((snapshot.pad.buttons & 0x200) != 0 ? 0x4000 : 0)
            : 0;
        if (ctx.mmu.read8(block + 0x5C) != type) {
            for (unsigned i = 0x60; i < 176; ++i) {
                ctx.mmu.write8(block + i, 0);
            }
            ctx.mmu.write8(block + 0x555, 0);
        }
        sample_buttons(ctx, type, snapshot.mote.buttons, extra);
        ctx.mmu.write8(block + 0x5C, type);
        ctx.mmu.write8(block + 0x5D, 0);
        const bool previous_motion = ctx.mmu.read8(block + 0x5F) != 0;
        std::array<float, 3> acceleration{}, delta{};
        for (unsigned axis = 0; axis < 3; ++axis) {
            const float value = axis == 0 ? snapshot.mote.accel_x : axis == 1 ? snapshot.mote.accel_y : snapshot.mote.accel_z;
            acceleration[axis] = std::isfinite(value) ? value : 0.0f;
            const float difference = acceleration[axis] - ctx.mmu.read_f32(block + 0x0C + axis * 4);
            delta[axis] = previous_motion && std::isfinite(difference) ? difference : 0.0f;
            ctx.mmu.write_f32(block + 0x0C + axis * 4, acceleration[axis]);
        }
        const auto length = [](const std::array<float, 3>& value) {
            const float result = std::hypot(value[0], value[1], value[2]);
            return std::isfinite(result) ? result : 0.0f;
        };
        ctx.mmu.write_f32(block + 0x18, length(acceleration));
        ctx.mmu.write_f32(block + 0x1C, length(delta));
        const float horizon_length = std::hypot(acceleration[1], acceleration[0]);
        const bool horizon_valid = std::isfinite(horizon_length) && horizon_length > 0.000001f;
        ctx.mmu.write_f32(block + 0x34, horizon_valid ? -acceleration[1] / horizon_length : 1.0f);
        ctx.mmu.write_f32(block + 0x38, horizon_valid ? -acceleration[0] / horizon_length : 0.0f);
        const bool pointer = std::isfinite(snapshot.mote.ir_x) && std::isfinite(snapshot.mote.ir_y)
            && snapshot.mote.ir_x >= 0 && snapshot.mote.ir_x <= 1 && snapshot.mote.ir_y >= 0 && snapshot.mote.ir_y <= 1;
        if (pointer) {
            const float x = snapshot.mote.ir_x * 2.0f - 1.0f;
            const float y = snapshot.mote.ir_y * 2.0f - 1.0f;
            const bool previous = ctx.mmu.read8(block + 0x5E) != 0;
            const float dx = previous ? x - ctx.mmu.read_f32(block + 0x20) : 0;
            const float dy = previous ? y - ctx.mmu.read_f32(block + 0x24) : 0;
            ctx.mmu.write_f32(block + 0x20, x);
            ctx.mmu.write_f32(block + 0x24, y);
            ctx.mmu.write_f32(block + 0x28, dx);
            ctx.mmu.write_f32(block + 0x2C, dy);
            ctx.mmu.write_f32(block + 0x30, std::hypot(dx, dy));
        }
        // PC pointer: original Wii consumers at 80009740/8000AB50 require validity 2.
        ctx.mmu.write8(block + 0x5E, pointer ? 2 : 0);
        ctx.mmu.write8(block + 0x5F, type == 1 ? (pointer ? 5 : 4) : (pointer ? 2 : 1));
        if (type == 1) {
            float x = snapshot.pad.stick_x / (snapshot.pad.stick_x < 0 ? 128.0f : 127.0f);
            float y = snapshot.pad.stick_y / (snapshot.pad.stick_y < 0 ? 128.0f : 127.0f);
            const float radius = std::hypot(x, y);
            if (radius > 1) {
                x /= radius;
                y /= radius;
            }
            ctx.mmu.write_f32(block + 0x60, x);
            ctx.mmu.write_f32(block + 0x64, y);
            ctx.mmu.write_f32(block + 0x68, 0);
            ctx.mmu.write_f32(block + 0x6C, -1);
            ctx.mmu.write_f32(block + 0x70, 0);
            ctx.mmu.write_f32(block + 0x74, 1);
            ctx.mmu.write_f32(block + 0x78, 0);
        }
        for (unsigned i = 0; i < 176; ++i) {
            records[result.count][i] = ctx.mmu.read8(block + i);
        }
        ++result.count;
    }
    if (result.count != 0) {
        for (unsigned record = 0; record < result.count; ++record) {
            for (unsigned i = 0; i < 176; ++i) {
                ctx.mmu.write8(destination + record * 176 + i, records[result.count - record - 1][i]);
            }
        }
        result.error = 0;
    }
    return result;
}

}

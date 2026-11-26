#pragma once
#include <processor_adapter.h>
#include <input/input_manager.h>
#include <stdexcept>

extern "C" void func_80009CF8(nwii::runtime::CPUContext&);

namespace openshsm::experiment {

enum class ConnectionSyncResult {
    Unregistered,
    UnsupportedCallback,
    UnsupportedContext,
    Unchanged,
    Connected,
    Disconnected
};

// PC adaptation: primary-channel transitions use the game's registered original callback.
inline ConnectionSyncResult sync_primary_connection(nwii::runtime::CPUContext& ctx, bool connected) {
    if (ctx.gpr[13] != 0x8052E720 || ctx.gpr[1] < 0x80000040 || ctx.gpr[1] > 0x817FFFF0 || (ctx.gpr[1] & 3) != 0) {
        return ConnectionSyncResult::UnsupportedContext;
    }
    const uint32_t callback = ctx.mmu.read32(0x804EFD58 + 0x550);
    if (callback == 0) {
        return ConnectionSyncResult::Unregistered;
    }
    if (callback != 0x80009CF8) {
        return ConnectionSyncResult::UnsupportedCallback;
    }
    const bool previous = ctx.mmu.read8(0x804579C0) != 0;
    if (previous == connected) {
        return ConnectionSyncResult::Unchanged;
    }
    const auto gpr = ctx.gpr;
    const auto cr = ctx.cr;
    const auto lr = ctx.lr;
    const auto pc = ctx.pc;
    const auto ctr = ctx.ctr;
    const auto xer = ctx.xer;
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
    ctx.gpr[3] = 0;
    ctx.gpr[4] = connected ? 0 : 0xFFFFFFFF;
    ctx.pc = callback;
    ctx.lr = pc;
    ctx.msr &= ~0x8000u;
    try {
        func_80009CF8(ctx);
    } catch (...) {
        restore();
        throw;
    }
    const bool returned = ctx.pc == pc && ctx.gpr[1] == gpr[1];
    restore();
    if (!returned) {
        throw std::runtime_error("Original primary connection callback did not return");
    }
    return connected ? ConnectionSyncResult::Connected : ConnectionSyncResult::Disconnected;
}

inline ConnectionSyncResult sync_primary_connection(nwii::runtime::CPUContext& ctx) {
    return sync_primary_connection(ctx, nwii::runtime::input::InputManager::get().get_wiimote_state(0).err == 0);
}

}

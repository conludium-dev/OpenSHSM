#include "stock_input_connection_bridge.h"
#include <iomanip>
#include <iostream>
#include <memory>

class ControlledSource : public nwii::runtime::input::IInputSource {
public:
    bool connected = false;
    void update(nwii::runtime::input::GameCubePadState[4], nwii::runtime::input::WiimoteState motes[4]) override {
        motes[0].err = connected ? 0 : -1;
    }
};

int main() {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    unsigned id = 0;
    for (unsigned pattern = 0; pattern < 8; ++pattern) {
        for (unsigned previous = 0; previous < 2; ++previous) {
            for (uint32_t result : {0u, 0xFFFFFFFFu}) {
                for (unsigned i = 0; i < 0xB30; ++i) {
                    ctx.mmu.write8(0x804579C0 + i, (i * 37 + pattern) & 255);
                }
                ctx.mmu.write8(0x804579C0, previous);
                ctx.mmu.write32(0x80526B10, 0xCAFEBABE);
                ctx.gpr[1] = 0x80700000;
                ctx.gpr[13] = 0x8052E720;
                ctx.gpr[3] = 0;
                ctx.gpr[4] = result;
                ctx.gpr[29] = 0x11111111;
                ctx.gpr[30] = 0x22222222;
                ctx.gpr[31] = 0x33333333;
                ctx.pc = 0x80009CF8;
                ctx.lr = 0x8009BB80;
                func_80009CF8(ctx);
                if (ctx.pc != 0x8009BB80 || ctx.lr != 0x8009BB80 || ctx.gpr[1] != 0x80700000
                    || ctx.gpr[29] != 0x11111111 || ctx.gpr[30] != 0x22222222 || ctx.gpr[31] != 0x33333333) {
                    return 1;
                }
                std::cout << "CALLBACK " << id++ << ' ' << ctx.mmu.read32(0x80526B10) << ' ';
                for (unsigned i = 0; i < 0xB30; ++i) {
                    std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(ctx.mmu.read8(0x804579C0 + i));
                }
                std::cout << std::dec << '\n';
            }
        }
    }
    auto source = std::make_unique<ControlledSource>();
    auto* controlled = source.get();
    auto& input = nwii::runtime::input::InputManager::get();
    input.add_source(std::move(source));
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0x8052E720;
    ctx.pc = 0x8009BB80;
    ctx.lr = 0x12345678;
    ctx.mmu.write8(0x804579C0, 0);
    ctx.mmu.write32(0x804EFD58 + 0x550, 0);
    controlled->connected = true;
    input.update();
    using openshsm::experiment::ConnectionSyncResult;
    using openshsm::experiment::sync_primary_connection;
    if (sync_primary_connection(ctx) != ConnectionSyncResult::Unregistered || ctx.mmu.read8(0x804579C0) != 0) {
        return 2;
    }
    ctx.mmu.write32(0x804EFD58 + 0x550, 0xDEADBEEF);
    if (sync_primary_connection(ctx) != ConnectionSyncResult::UnsupportedCallback || ctx.mmu.read8(0x804579C0) != 0) {
        return 3;
    }
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    ctx.gpr[1] = 0;
    if (sync_primary_connection(ctx) != ConnectionSyncResult::UnsupportedContext || ctx.mmu.read8(0x804579C0) != 0) {
        return 7;
    }
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0;
    if (sync_primary_connection(ctx) != ConnectionSyncResult::UnsupportedContext || ctx.mmu.read8(0x804579C0) != 0) {
        return 8;
    }
    ctx.gpr[13] = 0x8052E720;
    for (bool connected : {false, false, true, true, false, false, true}) {
        const bool previous = ctx.mmu.read8(0x804579C0) != 0;
        ctx.mmu.write32(0x804579C0 + 0xB0C, 13);
        ctx.mmu.write32(0x80526B10, 0xCAFEBABE);
        controlled->connected = connected;
        input.update();
        const auto gpr = ctx.gpr;
        const auto cr = ctx.cr;
        const auto lr = ctx.lr, pc = ctx.pc, ctr = ctx.ctr, xer = ctx.xer;
        const auto result = sync_primary_connection(ctx);
        const auto expected = previous == connected ? ConnectionSyncResult::Unchanged
            : connected ? ConnectionSyncResult::Connected : ConnectionSyncResult::Disconnected;
        if (result != expected || ctx.mmu.read8(0x804579C0) != unsigned(connected)
            || ctx.mmu.read32(0x804579C0 + 0xB0C) != (previous == connected ? 13u : 0u)
            || ctx.gpr != gpr || ctx.lr != lr || ctx.pc != pc || ctx.ctr != ctr || ctx.xer != xer) {
            return 4;
        }
        for (unsigned i = 0; i < 8; ++i) {
            if (ctx.cr[i].lt != cr[i].lt || ctx.cr[i].gt != cr[i].gt || ctx.cr[i].eq != cr[i].eq || ctx.cr[i].so != cr[i].so) {
                return 5;
            }
        }
        if (ctx.mmu.read32(0x80526B10) != ((!previous && connected) ? 0u : 0xCAFEBABE)) {
            return 6;
        }
    }
    std::cout << "PRIMARY_CONNECTION_ADAPTER_PASS 7 polls/4 registration-context refusals\n";
}

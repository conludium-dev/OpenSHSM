#include "stock_input_sdk_bridge.h"
#include <iostream>
#include <memory>

extern "C" void func_80009DD0(nwii::runtime::CPUContext&);
extern "C" void func_8027AAC0(nwii::runtime::CPUContext&);
extern "C" void func_80280AC0(nwii::runtime::CPUContext&);
extern "C" void func_802020D4(nwii::runtime::CPUContext&);

class SDKSource : public nwii::runtime::input::IInputSource {
public:
    bool connected = true;
    uint32_t buttons = 0x800;
    float tilt = 0;
    void update(nwii::runtime::input::GameCubePadState pads[4], nwii::runtime::input::WiimoteState motes[4]) override {
        pads[0] = {};
        pads[0].err = 0;
        motes[0] = {};
        motes[0].ir_x = 0.5f;
        motes[0].ir_y = 0.5f;
        motes[0].buttons = buttons;
        motes[0].accel_x = tilt;
        motes[0].err = connected ? 0 : -1;
    }
};

int main() {
    std::cout << std::unitbuf;
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0x8052E720;
    ctx.msr |= 0xA000;
    ctx.mmu.write32(0x800000F8, 243000000);
    ctx.mmu.write32(0x800000FC, 729000000);
    ctx.tb_freq = 60750000;
    auto source = std::make_unique<SDKSource>();
    auto* control = source.get();
    auto& input = nwii::runtime::input::InputManager::get();
    input.add_source(std::move(source));
    constexpr uint32_t result = 0x80550000;
    const auto call = [&](uint32_t pc, auto function) {
        std::cerr << "SDK probe call " << std::hex << pc << std::dec << '\n';
        const auto msr = ctx.msr;
        ctx.pc = pc;
        ctx.lr = 0x8009BB80;
        function(ctx);
        if (ctx.pc != 0x8009BB80 || ctx.gpr[1] != 0x80700000 || ctx.gpr[13] != 0x8052E720 || ctx.msr != msr) {
            throw std::runtime_error("SDK integration did not return");
        }
    };
    ctx.gpr[3] = 0;
    ctx.gpr[4] = result;
    call(0x80280AC0, func_80280AC0);
    if (ctx.gpr[3] != uint32_t(-1) || ctx.mmu.read32(result) != 0xFD) {
        return 1;
    }
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    ctx.mmu.write16(0x804EFD58 + 0x504, 1000);
    ctx.mmu.write16(0x804EFD58 + 0x506, 10);
    input.update();
    ctx.gpr[3] = 0;
    ctx.gpr[4] = result;
    call(0x80280AC0, func_80280AC0);
    if (ctx.gpr[3] != 0 || ctx.mmu.read32(result) != 1 || ctx.mmu.read8(0x804579C0) != 0) {
        return 2;
    }
    call(0x802020D4, func_802020D4);
    ctx.mmu.write32(0x80526720, ctx.gpr[3]);
    call(0x80009DD0, func_80009DD0);
    if (ctx.mmu.read8(0x804579C0) != 1 || ctx.mmu.read32(0x804579C0 + 0xB0C) != 16
        || ctx.mmu.read32(0x804579C0 + 8) != 0x80000800
        || ctx.mmu.read32(0x804579C0 + 12) != 0x800 || ctx.mmu.read8(0x804579C0 + 0x64) != 1) {
        return 3;
    }
    ctx.gpr[3] = 0;
    ctx.gpr[4] = result;
    ctx.gpr[5] = 1;
    ctx.gpr[6] = result + 0x100;
    ctx.gpr[7] = 1;
    ctx.mmu.write32(result, 0xCDCDCDCD);
    call(0x8027AAD0, func_8027AAC0);
    if (ctx.gpr[3] != 0 || ctx.mmu.read32(result + 0x100) != uint32_t(-1)
        || ctx.mmu.read32(result) != 0xCDCDCDCD) {
        return 4;
    }
    control->buttons = 0;
    input.update();
    ctx.gpr[3] = 0;
    ctx.gpr[4] = result;
    ctx.gpr[5] = 1;
    ctx.gpr[6] = 0xFFFFFFFF;
    call(0x8027AAD0, func_8027AAC0);
    if (ctx.gpr[3] != 0) {
        return 5;
    }
    ctx.gpr[3] = 0;
    ctx.gpr[4] = result;
    ctx.gpr[5] = 1;
    ctx.gpr[6] = result + 0x100;
    call(0x8027AAD0, func_8027AAC0);
    if (ctx.gpr[3] != 1 || ctx.mmu.read32(result + 8) != 0x800 || ctx.mmu.read32(result + 0x100) != 0) {
        return 6;
    }
    control->connected = false;
    input.update();
    call(0x80009DD0, func_80009DD0);
    if (ctx.mmu.read8(0x804579C0) != 0 || ctx.mmu.read32(0x804579C0 + 0xB0C) != 0) {
        return 7;
    }
    control->connected = true;
    control->buttons = 0x800;
    input.update();
    call(0x802020D4, func_802020D4);
    ctx.mmu.write32(0x80526720, ctx.gpr[3]);
    call(0x80009DD0, func_80009DD0);
    if (ctx.mmu.read8(0x804579C0) != 0 || ctx.mmu.read32(0x804579C0 + 0xB0C) != 0) {
        return 8;
    }
    call(0x80009DD0, func_80009DD0);
    if (ctx.mmu.read32(0x804579C0 + 0xB0C) != 16 || ctx.mmu.read32(0x804579C0 + 12) != 0x800) {
        return 9;
    }
    control->tilt = 1;
    input.update();
    call(0x80009DD0, func_80009DD0);
    if (ctx.mmu.read_f32(0x804579C0 + 8 + 0x1C) != 1) {
        return 10;
    }
    for (unsigned i = 1; i < 16; ++i) {
        if (ctx.mmu.read_f32(0x804579C0 + 8 + i * 176 + 0x1C) != 0) {
            return 11;
        }
    }
    std::cout << "PC_INPUT_SDK_INTEGRATION_PASS original-sampler/copy/query/read/error/disconnect-reconnect\n";
}

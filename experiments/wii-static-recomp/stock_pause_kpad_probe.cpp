#include "input/input_manager.h"
#include <processor_adapter.h>
#include <cstdint>
#include <memory>
#include <cstdio>

extern "C" void func_8027AAC0(nwii::runtime::CPUContext&);

class PauseSource : public nwii::runtime::input::IInputSource {
public:
    uint32_t buttons = 0;

    void update(nwii::runtime::input::GameCubePadState pads[4],
            nwii::runtime::input::WiimoteState motes[4]) override {
        pads[0].err = 0;
        motes[0].err = 0;
        motes[0].ir_x = 0.5f;
        motes[0].ir_y = 0.5f;
        motes[0].buttons = buttons;
    }
};

int main() {
    using namespace nwii::runtime;
    auto owned = std::make_unique<ProcessorContext>();
    auto& ctx = *owned;
    auto& input = input::InputManager::get();
    auto source = std::make_unique<PauseSource>();
    auto* control = source.get();
    input.add_source(std::move(source));
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0x8052E720;
    ctx.msr |= 0xA000;
    ctx.mmu.write32(0x800000F8, 243000000);
    ctx.mmu.write32(0x800000FC, 729000000);
    ctx.tb_freq = 60750000;
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    ctx.mmu.write16(0x804EFD58 + 0x504, 1000);
    ctx.mmu.write16(0x804EFD58 + 0x506, 10);
    constexpr uint32_t output = 0x80550000;
    const auto read = [&](uint32_t capacity, int expected_error) {
        ctx.gpr[3] = 0;
        ctx.gpr[4] = output;
        ctx.gpr[5] = capacity;
        ctx.gpr[6] = output + 0x1000;
        ctx.pc = 0x8027AAD0;
        ctx.lr = 0x8009BB80;
        func_8027AAC0(ctx);
        return ctx.pc == 0x8009BB80 && ctx.gpr[1] == 0x80700000
            && ctx.gpr[13] == 0x8052E720
            && ctx.mmu.read32(output + 0x1000) == uint32_t(expected_error);
    };
    input.update();
    if (!read(1, 0) || ctx.gpr[3] != 1 || ctx.mmu.read32(output + 4) != 0) {
        return 1;
    }
    control->buttons = 0x0200;
    input.update();
    control->buttons = 0;
    for (int i = 0; i < 32; ++i) {
        input.update();
    }
    if (input.get_wiimote_state(0).buttons != 0 || input.dropped_input(0) != 17) {
        return 2;
    }
    if (!read(16, 0) || ctx.gpr[3] != 16) {
        return 3;
    }
    int triggers = 0;
    int releases = 0;
    for (int i = 0; i < 16; ++i) {
        triggers += (ctx.mmu.read32(output + i * 176 + 4) & 0x0200) != 0;
        releases += (ctx.mmu.read32(output + i * 176 + 8) & 0x0200) != 0;
    }
    if (triggers != 1 || releases != 1 || !read(1, -1) || ctx.gpr[3] != 0) {
        return 4;
    }
    std::puts("PAUSE_KPAD_GUEST_HEADLESS_PASS");
}

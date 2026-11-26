#include "stock_input_sample_bridge.h"
#include <iostream>
#include <limits>
#include <memory>

class SampleSource : public nwii::runtime::input::IInputSource {
public:
    nwii::runtime::input::WiimoteState mote{0, 0.5f, 0.5f, 0, 0, 0, 0, 0, 0, 0};
    nwii::runtime::input::GameCubePadState pad{0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    void update(nwii::runtime::input::GameCubePadState pads[4], nwii::runtime::input::WiimoteState motes[4]) override {
        pads[0] = pad;
        motes[0] = mote;
    }
};

int main() {
    using namespace openshsm::experiment;
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    auto source = std::make_unique<SampleSource>();
    auto* controlled = source.get();
    auto& input = nwii::runtime::input::InputManager::get();
    input.add_source(std::move(source));
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0x8052E720;
    ctx.pc = 0x8009BB80;
    ctx.lr = 0x12345678;
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    ctx.mmu.write16(0x804EFD58 + 0x504, 1000);
    ctx.mmu.write16(0x804EFD58 + 0x506, 10);
    constexpr uint32_t output = 0x80550000;
    const auto clear = [&]() {
        for (unsigned i = 0; i < 0xB20; ++i) {
            ctx.mmu.write8(output - 16 + i, 0xCD);
        }
    };
    const auto read = [&](unsigned capacity = 1, bool extension = true) {
        const auto gpr = ctx.gpr;
        const auto cr = ctx.cr;
        const auto pc = ctx.pc, lr = ctx.lr, ctr = ctx.ctr, xer = ctx.xer;
        const auto result = read_pc_primary_samples(ctx, 0, output, capacity, extension);
        if (ctx.gpr != gpr || ctx.pc != pc || ctx.lr != lr || ctx.ctr != ctr || ctx.xer != xer) {
            throw std::runtime_error("Guest integer context changed");
        }
        for (unsigned i = 0; i < 8; ++i) {
            if (ctx.cr[i].lt != cr[i].lt || ctx.cr[i].gt != cr[i].gt || ctx.cr[i].eq != cr[i].eq || ctx.cr[i].so != cr[i].so) {
                throw std::runtime_error("Guest condition register changed");
            }
        }
        for (unsigned i = 0; i < 16; ++i) {
            if (ctx.mmu.read8(output - 16 + i) != 0xCD || ctx.mmu.read8(output + 0xB00 + i) != 0xCD) {
                throw std::runtime_error("Sample buffer guard changed");
            }
        }
        return result;
    };
    clear();
    if (read().count != 0) {
        return 1;
    }
    controlled->mote.buttons = 0x800;
    input.update();
    for (uint32_t address : {0u, 0xFFFFFFFFu, 0x804EFD58u, 0x804579C0u, 0x806FFFF0u, output + 1, 0x817FFFF0u}) {
        if (read_pc_primary_samples(ctx, 0, address, 1, true).error != -6) {
            return 2;
        }
    }
    if (read_pc_primary_samples(ctx, 1, output, 1, true).error != -6
        || read_pc_primary_samples(ctx, 0, output, 17, true).error != -6 || read(0).count != 0) {
        return 3;
    }
    ctx.mmu.write8(0x804EFD58 + 0x4FF, 1);
    if (read().error != -4) {
        return 4;
    }
    ctx.mmu.write8(0x804EFD58 + 0x4FF, 0);
    ctx.mmu.write32(0x804EFD58 + 0x550, 0);
    if (read().error != -5) {
        return 5;
    }
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    ctx.gpr[1] = 0;
    if (read().error != -6) {
        return 21;
    }
    ctx.gpr[1] = 0x80700000;
    ctx.gpr[13] = 0;
    if (read().error != -6) {
        return 22;
    }
    ctx.gpr[13] = 0x8052E720;
    ctx.mmu.write32(0x804EFD58 + 0x550, 0xDEADBEEF);
    if (read().error != -5) {
        return 23;
    }
    ctx.mmu.write32(0x804EFD58 + 0x550, 0x80009CF8);
    const auto first = read();
    if (first.count != 1 || ctx.mmu.read32(output) != 0x80000800 || ctx.mmu.read32(output + 4) != 0x800
        || ctx.mmu.read32(output + 8) != 0 || ctx.mmu.read8(output + 0x5C) != 1
        || ctx.mmu.read8(0x804579C0) != 1 || ctx.mmu.read8(output + 176) != 0xCD) {
        std::cerr << "First sample count=" << first.count << " error=" << first.error << std::hex
            << " held=" << ctx.mmu.read32(output) << " trigger=" << ctx.mmu.read32(output + 4)
            << " release=" << ctx.mmu.read32(output + 8) << " type=" << unsigned(ctx.mmu.read8(output + 0x5C))
            << " connected=" << unsigned(ctx.mmu.read8(0x804579C0)) << '\n';
        return 6;
    }
    clear();
    if (read().count != 0 || ctx.mmu.read8(output) != 0xCD) {
        return 7;
    }
    input.update();
    if (read().count != 1 || ctx.mmu.read32(output + 4) != 0 || ctx.mmu.read32(output + 8) != 0) {
        return 8;
    }
    controlled->mote.buttons = 0;
    input.update();
    if (read().count != 1 || ctx.mmu.read32(output + 8) != 0x800) {
        return 9;
    }
    controlled->pad.buttons = 0x100;
    controlled->pad.stick_x = 127;
    controlled->pad.stick_y = -128;
    controlled->mote.ir_x = 0.75f;
    controlled->mote.ir_y = 0.25f;
    input.update();
    if (read().count != 1 || ctx.mmu.read32(output) != 0x80002000
        || ctx.mmu.read_f32(output + 0x20) != 0.5f || ctx.mmu.read_f32(output + 0x24) != -0.5f
        || ctx.mmu.read8(output + 0x5E) != 2 || ctx.mmu.read8(output + 0x5F) != 5 || std::abs(ctx.mmu.read_f32(output + 0x60) - 0.70710677f) > 0.000001f
        || std::abs(ctx.mmu.read_f32(output + 0x64) + 0.70710677f) > 0.000001f) {
        return 10;
    }
    controlled->pad.buttons = 0x300;
    input.update();
    if (read().count != 1 || ctx.mmu.read32(output) != 0x80006000
        || ctx.mmu.read32(output + 4) != 0x4000) {
        return 18;
    }
    controlled->mote.ir_x = std::numeric_limits<float>::quiet_NaN();
    controlled->mote.accel_x = std::numeric_limits<float>::infinity();
    input.update();
    if (read().count != 1 || ctx.mmu.read8(output + 0x5E) != 0 || ctx.mmu.read8(output + 0x5F) != 4 || ctx.mmu.read_f32(output + 0x20) != 0.5f
        || ctx.mmu.read_f32(output + 0x24) != -0.5f || ctx.mmu.read_f32(output + 0x0C) != 0) {
        return 11;
    }
    controlled->mote.ir_x = 0.5f;
    controlled->pad.buttons = 0;
    controlled->pad.err = -1;
    input.update();
    if (read().count != 1 || ctx.mmu.read8(output + 0x5C) != 0 || ctx.mmu.read8(output + 0x5F) != 2 || ctx.mmu.read_f32(output + 0x60) != 0) {
        return 12;
    }
    controlled->mote.ir_x = std::numeric_limits<float>::quiet_NaN();
    input.update();
    if (read().count != 1 || ctx.mmu.read8(output + 0x5F) != 1 || ctx.mmu.read8(output + 0x5E) != 0) {
        return 25;
    }
    controlled->mote.ir_x = 0.5f;
    controlled->mote.err = -1;
    input.update();
    clear();
    if (read().error != -2 || ctx.mmu.read8(0x804579C0) != 0 || ctx.mmu.read8(output) != 0xCD) {
        return 13;
    }
    controlled->mote.err = 0;
    controlled->mote.buttons = 0x800;
    controlled->pad.err = 0;
    input.update();
    if (read().count != 1 || ctx.mmu.read32(output + 4) != 0x800) {
        return 14;
    }
    controlled->mote.buttons = 0;
    input.update();
    read();
    controlled->mote.buttons = 0x800;
    input.update();
    controlled->mote.buttons = 0;
    input.update();
    if (read(16).count != 2 || ctx.mmu.read32(output) != 0 || ctx.mmu.read32(output + 8) != 0x800
        || ctx.mmu.read32(output + 176) != 0x80000800 || ctx.mmu.read32(output + 180) != 0x800) {
        return 15;
    }
    const auto dropped = input.dropped_input(0);
    for (unsigned i = 0; i < 18; ++i) {
        controlled->mote.ir_x = i / 20.0f;
        input.update();
    }
    clear();
    const auto batch = read(16);
    if (batch.count != 16 || batch.error != 0 || input.dropped_input(0) != dropped + 2) {
        return 16;
    }
    for (unsigned i = 0; i < 16; ++i) {
        const float expected = (17 - i) / 20.0f * 2.0f - 1.0f;
        if (ctx.mmu.read_f32(output + i * 176 + 0x20) != expected) {
            return 17;
        }
    }
    clear();
    if (read().count != 0 || ctx.mmu.read8(output) != 0xCD) {
        return 18;
    }
    controlled->mote.buttons = 0x800;
    input.update();
    controlled->mote.err = -1;
    input.update();
    controlled->mote.err = 0;
    input.update();
    if (read(16).error != -2 || ctx.mmu.read8(output) != 0xCD || ctx.mmu.read8(0x804579C0) != 0) {
        return 19;
    }
    if (read(16).count != 1 || ctx.mmu.read32(output + 4) != 0x800 || ctx.mmu.read8(0x804579C0) != 1) {
        return 20;
    }
    controlled->pad.buttons = 0x100;
    input.update();
    if (read(1, false).count != 1 || ctx.mmu.read8(output + 0x5C) != 0
        || ctx.mmu.read32(output) != 0x800 || ctx.mmu.read_f32(output + 0x60) != 0) {
        return 24;
    }
    controlled->mote.accel_x = 0;
    controlled->mote.accel_y = -1;
    controlled->mote.accel_z = 0;
    input.update();
    if (read().count != 1 || ctx.mmu.read_f32(output + 0x18) != 1
        || ctx.mmu.read_f32(output + 0x34) != 1 || ctx.mmu.read_f32(output + 0x38) != 0) {
        return 26;
    }
    controlled->mote.accel_x = -1;
    controlled->mote.accel_y = 0;
    input.update();
    if (read().count != 1 || ctx.mmu.read_f32(output + 0x18) != 1
        || std::abs(ctx.mmu.read_f32(output + 0x1C) - std::sqrt(2.0f)) > 0.000001f
        || ctx.mmu.read_f32(output + 0x34) != 0 || ctx.mmu.read_f32(output + 0x38) != 1) {
        return 27;
    }
    input.update();
    if (read().count != 1 || ctx.mmu.read_f32(output + 0x1C) != 0) {
        return 28;
    }
    std::cout << "PC_PRIMARY_SAMPLE_PIPELINE_PASS bounds/empty/press-hold-release/pointer/virtual-extension/disconnect-reconnect/newest-first\n";
}

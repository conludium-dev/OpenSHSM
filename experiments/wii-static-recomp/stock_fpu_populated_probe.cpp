#include "runtime/cpu_context.h"
#include <bit>
#include <cassert>
#include <iostream>
#include <memory>

extern "C" void func_802136F0(nwii::runtime::CPUContext&);
extern "C" void func_802135C0(nwii::runtime::CPUContext&);

int main() {
    constexpr uint32_t context = 0x80568000, caller = 0x807F0000;
    unsigned cases = 0;
    for (bool paired : {false, true}) {
        for (uint32_t fpscr : {0u, 1u, 2u, 3u, 4u, 0x82000000u}) {
            auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
            auto& ctx = *owned;
            ctx.hid2 = paired ? 0xA0000000 : 0;
            ctx.msr = 0x2032;
            ctx.fpscr = fpscr;
            ctx.gpr[1] = 0x80700000;
            for (unsigned i = 0; i < 0x2D0; ++i) {
                ctx.mmu.write8(context - 4 + i, 0xA5);
            }
            ctx.mmu.write16(context + 0x1A2, 2);
            std::array<double, 32> primary, secondary, poison;
            for (unsigned i = 0; i < 32; ++i) {
                primary[i] = i % 2 ? -(i + 0.125000000123) : i + 0.250000000321;
                secondary[i] = i == 0 ? -0.0 : double(float(int(i) - 8) / 16.0f);
                poison[i] = 100.0 + i;
                ctx.fpr[i] = primary[i];
                ctx.ps1[i] = secondary[i];
            }
            if (setjmp(ctx.exception_jmp_buf) != 0) {
                std::cerr << "UNEXPECTED_FPU_TRAP " << std::hex << ctx.pc << '\n';
                return 2;
            }
            ctx.gpr[5] = context;
            ctx.pc = 0x802136F0;
            ctx.lr = caller;
            func_802136F0(ctx);
            assert(ctx.pc == caller && ctx.mmu.read16(context + 0x1A2) == 3);
            for (unsigned i = 0; i < 32; ++i) {
                assert(ctx.mmu.read64(context + 0x90 + i * 8) == std::bit_cast<uint64_t>(primary[i]));
                if (paired) {
                    assert(ctx.mmu.read32(context + 0x1CC + i * 8) == std::bit_cast<uint32_t>(float(secondary[i])));
                } else {
                    assert(ctx.mmu.read64(context + 0x1C8 + i * 8) == 0xA5A5A5A5A5A5A5A5ull);
                }
                ctx.fpr[i] = 900.0 + i;
                ctx.ps1[i] = poison[i];
            }
            assert(ctx.mmu.read32(context + 0x194) == fpscr);
            ctx.fpscr = 0;
            ctx.gpr[4] = context;
            ctx.pc = 0x802135C0;
            ctx.lr = caller;
            func_802135C0(ctx);
            assert(ctx.pc == caller && ctx.fpscr == fpscr);
            for (unsigned i = 0; i < 32; ++i) {
                assert(std::bit_cast<uint64_t>(ctx.fpr[i]) == std::bit_cast<uint64_t>(primary[i]));
                assert(std::bit_cast<uint64_t>(ctx.ps1[i]) == std::bit_cast<uint64_t>(paired ? secondary[i] : poison[i]));
            }
            assert(ctx.mmu.read32(context - 4) == 0xA5A5A5A5 && ctx.mmu.read32(context + 0x2C8) == 0xA5A5A5A5);
            ctx.mmu.write16(context + 0x1A2, 2);
            const auto before_primary = ctx.fpr, before_secondary = ctx.ps1;
            const auto before_fpscr = ctx.fpscr;
            ctx.pc = 0x802135C0;
            ctx.lr = caller;
            func_802135C0(ctx);
            assert(ctx.pc == caller && ctx.fpscr == before_fpscr);
            for (unsigned i = 0; i < 32; ++i) {
                assert(std::bit_cast<uint64_t>(ctx.fpr[i]) == std::bit_cast<uint64_t>(before_primary[i]));
                assert(std::bit_cast<uint64_t>(ctx.ps1[i]) == std::bit_cast<uint64_t>(before_secondary[i]));
            }
            ++cases;
        }
    }
    std::cout << "POPULATED_NATIVE_FPU_SAVE_LOAD_PASS " << cases << " all32lanes/primary64/secondary32/fpscr/flags/guards/empty\n";
}

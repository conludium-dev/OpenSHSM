#include "functions.h"
#define main experiment_previous_ios_main
#include "ios_open_host.cpp"
#undef main
#ifdef SHSM_EXTERNAL_IRQ_TEST
#include "runtime/hw/hw.h"
static const std::pair<uint32_t, uint32_t> irqSpans[] = {
    {0x806fffc0, 96}, {0x800000c4, 8}, {0x80003040, 128}, {0x8052aac8, 20},
    {0x8052ab00, 8}, {0x8042cf98, 48}
};
void func_8021C000(CPUContext& c) {
    c.gpr[3] = 1;
    c.gpr[4] = 0x23456789;
    events.insert(events.end(), {42, c.gpr[3], c.gpr[4], 0});
    c.pc = c.lr;
}
void func_80213A70(CPUContext&) { throw std::runtime_error("FPU save outside IRQ fixture"); }
void func_80217500(CPUContext&) { throw std::runtime_error("Idle outside IRQ fixture"); }
#endif

namespace nwii::runtime {
#ifdef SHSM_EXTERNAL_IRQ_TEST
uint32_t experiment_external_pi_read(uint32_t address) {
    if (address != 0x0c003000 && address != 0x0c003004) {
        throw std::runtime_error("External IRQ MMIO outside PI fixture");
    }
    const auto value = MMIODispatcher::get().read32(address | 0xc0000000);
    events.insert(events.end(), {41, address, value, 0});
    return value;
}
void note_null_call(uint32_t, uint32_t) { throw std::runtime_error("Null external IRQ callback"); }
#endif
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Context MMIO unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Context MMIO unavailable"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("Context GX unavailable"); }
}

int main() {
    CPUContext c;
#ifdef SHSM_EXTERNAL_IRQ_TEST
    hw::register_pi(MMIODispatcher::get());
#endif
    unsigned target, flags, savedMsr, savedXer, seed;
    while (std::cin >> target >> flags >> savedMsr >> savedXer >> seed) {
        const uint32_t base = 0x80680000;
        std::fill(c.mmu.get_ptr(base), c.mmu.get_ptr(base) + 1024, 0);
        for (unsigned i = 0; i < 32; ++i) {
            c.gpr[i] = 0x12340000 + i;
            c.mmu.write32(base + i * 4, 0x56780000 + seed * 0x100 + i);
        }
        c.mmu.write32(base + 4, 0x80700000);
        c.mmu.write32(base + 0x80, seed ? 0x87654321 : 0);
        c.mmu.write32(base + 0x84, 0x807f1000 + seed * 4);
        c.mmu.write32(base + 0x88, 0x13570000 + seed);
        c.mmu.write32(base + 0x8c, savedXer);
        c.mmu.write32(base + 0x198, target);
        c.mmu.write32(base + 0x19c, savedMsr);
        c.mmu.write16(base + 0x1a2, flags);
        for (unsigned i = 0; i < 8; ++i) {
            c.gqr[i] = 0;
            if (i) {
                c.mmu.write32(base + 0x1a4 + i * 4, 0x10000 * seed + i);
            }
        }
#ifdef SHSM_EXTERNAL_IRQ_TEST
        unsigned irqCase;
        if (!(std::cin >> irqCase) || irqCase > 5) {
            return 2;
        }
        for (auto [address, size] : irqSpans) {
            std::fill(c.mmu.get_ptr(address), c.mmu.get_ptr(address) + size, 0);
        }
        for (unsigned i = 0; i < 12; ++i) {
            uint32_t word;
            if (!(std::cin >> word)) {
                return 2;
            }
            c.mmu.write32(0x8042cf98 + i * 4, word);
        }
        c.mmu.write32(0x8052aad8, 0x80003040);
        c.mmu.write32(0x800030ac, irqCase == 5 ? 0x807f4000 : 0);
        c.mmu.write32(0x800000c4, irqCase == 2 ? 0x10 : 0);
        c.mmu.write32(0x800000c8, irqCase == 3 ? 0x10 : 0);
        hw::pi_intsr = irqCase == 0 ? 0x10000 : 0x14000;
        hw::pi_intmr = irqCase == 1 ? 0 : 0x4000;
#endif
        c.gpr[3] = base;
        c.pc = 0x80213920;
        c.lr = 0x807f2000;
        c.ctr = 0;
        c.xer = 0;
        c.msr = 0x2002;
        c.srr0 = 0;
        c.srr1 = 0;
        c.cr.fill({});
        events.clear();
#ifdef SHSM_EXTERNAL_IRQ_TEST
        c.gpr[1] = 0x80700000;
        c.gpr[3] = 4;
        c.gpr[4] = base;
        c.gpr[13] = 0x8052e720;
        c.xer = savedXer;
        for (unsigned i = 1; i < 8; ++i) {
            c.gqr[i] = 0x20000 * seed + i;
        }
        c.pc = 0x80217c60;
        func_80217C60(c);
        if (c.pc == 0x807f4000) {
            if (irqCase != 5 || c.gpr[3] != 27 || c.gpr[4] != base || c.lr != 0x80217c24
                || c.mmu.read32(0x8052ab00) != 1) {
                throw std::runtime_error("Original dispatcher selected wrong handler/ABI");
            }
            events.insert(events.end(), {40, c.gpr[3], c.gpr[4], c.mmu.read32(0x8052ab00)});
            c.pc = c.lr;
            func_80217C60(c);
        }
        if (c.pc != target || c.mmu.read32(0x8052ab00) != 0) {
            throw std::runtime_error("Original IRQ did not restore context/scheduler");
        }
#elif defined(SHSM_SAVE_ROUNDTRIP)
        c.gpr[1] = 0x80700000;
        c.pc = 0x802138a0;
        c.lr = target;
        c.ctr = 0x13570000 + seed;
        c.xer = savedXer;
        c.msr = savedMsr;
        for (unsigned i = 1; i < 8; ++i) {
            c.gqr[i] = 0x10000 * seed + i;
        }
        for (unsigned i = 0; i < 8; ++i) {
            const unsigned field = (seed ? 0x87654321 : 0) >> (28 - i * 4);
            c.cr[i].lt = (field & 8) != 0;
            c.cr[i].gt = (field & 4) != 0;
            c.cr[i].eq = (field & 2) != 0;
            c.cr[i].so = (field & 1) != 0;
        }
        func_802138A0(c);
#ifndef SHSM_SAVE_ONLY
        c.gpr[3] = base;
        c.pc = 0x80213920;
        func_80213920(c);
#endif
#else
        func_80213920(c);
#endif
        uint32_t cr = 0;
        for (const auto& f : c.cr) {
            cr = (cr << 4) | (f.lt << 3) | (f.gt << 2) | (f.eq << 1) | f.so;
        }
        std::cout << c.pc << ' ' << c.lr << ' ' << c.ctr << ' ' << c.xer << ' ' << cr << ' ' << c.msr;
        for (auto value : c.gpr) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << c.srr0 << ' ' << c.srr1;
        for (unsigned i = 1; i < 8; ++i) {
            std::cout << ' ' << c.gqr[i];
        }
        std::cout << ' ' << events.size();
#ifdef SHSM_EXTERNAL_IRQ_TEST
        for (auto value : events) {
            std::cout << ' ' << value;
        }
#endif
        std::cout << ' ' << std::hex << std::setfill('0');
        for (unsigned i = 0; i < 1024; ++i) {
            std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(base)[i]);
        }
#ifdef SHSM_EXTERNAL_IRQ_TEST
        for (auto [address, size] : irqSpans) {
            for (unsigned i = 0; i < size; ++i) {
                std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(address)[i]);
            }
        }
#endif
        std::cout << std::dec << '\n';
    }
}

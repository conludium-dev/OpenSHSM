#include "functions.h"
#define main experiment_previous_ios_main
#include "ios_open_host.cpp"
#undef main

namespace nwii::runtime {
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Wakeup MMIO unavailable"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("Wakeup GX unavailable"); }
}

void func_8021A790(CPUContext& c) {
    events.insert(events.end(), {30, c.gpr[3], 0, 0});
    c.pc = c.lr;
}

int main() {
    CPUContext c;
    unsigned count, priority, suspended, existing, xer;
    while (std::cin >> count >> priority >> suspended >> existing >> xer) {
        if (count > 3 || priority > 31 || suspended > 7 || existing > 1) {
            return 2;
        }
        for (auto span : {std::pair{0x806a004cu, 8u}, {0x80680000u, 4096u}, {0x80690000u, 1024u},
                          {0x80492970u, 256u}, {0x8052ab04u, 8u}, {0x806fffc0u, 96u}}) {
            std::fill(c.mmu.get_ptr(span.first), c.mmu.get_ptr(span.first) + span.second, 0);
        }
        c.mmu.write32(0x806a004c, count ? 0x80680000 : 0);
        c.mmu.write32(0x806a0050, count ? 0x80680000 + (count - 1) * 1024 : 0);
        for (unsigned i = 0; i < count; ++i) {
            const auto thread = 0x80680000 + i * 1024;
            c.mmu.write16(thread + 0x2c8, 4);
            c.mmu.write32(thread + 0x2cc,
#ifdef SHSM_SLEEP_THREAD
                          0
#else
                          (suspended >> i) & 1
#endif
            );
            c.mmu.write32(thread + 0x2d0,
#ifdef SHSM_SLEEP_THREAD
                          suspended == 0 ? 7 : suspended == 1 ? (i == 0 ? 0 : i == 1 ? 7 : 31) : 31
#else
                          priority
#endif
            );
            c.mmu.write32(thread + 0x2dc, 0x806a004c);
            c.mmu.write32(thread + 0x2e0, i + 1 < count ? thread + 1024 : 0);
            c.mmu.write32(thread + 0x2e4, i ? thread - 1024 : 0);
        }
#ifdef SHSM_SLEEP_THREAD
        c.mmu.write32(0x800000e4, 0x80690000);
        c.mmu.write16(0x806902c8, existing ? 4 : 2);
        c.mmu.write32(0x806902d0, priority);
#else
        if (existing) {
            c.mmu.write32(0x80492970 + priority * 8, 0x80690000);
            c.mmu.write32(0x80492974 + priority * 8, 0x80690000);
        }
#endif
        for (unsigned i = 0; i < 32; ++i) {
            c.gpr[i] = 0x12340000 + i;
        }
        c.gpr[1] = 0x80700000;
        c.gpr[3] = 0x806a004c;
        c.gpr[13] = 0x8052e720;
        c.pc =
#ifdef SHSM_SLEEP_THREAD
            0x8021b4e0;
#else
            0x8021b5d0;
#endif
        c.lr = 0x807f0000;
        c.ctr = 0;
        c.xer = xer;
        c.cr.fill({});
        events.clear();
#ifdef SHSM_SLEEP_THREAD
        func_8021B4E0(c);
#ifdef SHSM_SLEEP_WAKEUP
        c.gpr[3] = 0x806a004c;
        c.pc = 0x8021b5d0;
        c.lr = 0x807f0000;
        func_8021B5D0(c);
#endif
#else
        func_8021B5D0(c);
#endif
        uint32_t cr = 0;
        for (const auto& f : c.cr) {
            cr = (cr << 4) | (f.lt << 3) | (f.gt << 2) | (f.eq << 1) | f.so;
        }
        std::cout << c.pc << ' ' << c.lr << ' ' << c.ctr << ' ' << c.xer << ' ' << cr;
        for (auto value : c.gpr) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << events.size();
        for (auto value : events) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << std::hex << std::setfill('0');
        for (auto span : {std::pair{0x806a004cu, 8u}, {0x80680000u, 4096u}, {0x80690000u, 1024u},
                          {0x80492970u, 256u}, {0x8052ab04u, 8u}, {0x806fffc0u, 96u}}) {
            for (unsigned i = 0; i < span.second; ++i) {
                std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(span.first)[i]);
            }
        }
        std::cout << std::dec << '\n';
    }
}

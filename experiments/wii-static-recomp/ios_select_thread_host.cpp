#include "functions.h"
#define main experiment_previous_ios_main
#include "ios_open_host.cpp"
#undef main

struct ContextBoundary {};
#ifndef SHSM_ORIGINAL_SET_CONTEXT
void func_80213890(CPUContext& c) {
    events.insert(events.end(), {31, 0, 0, 0});
    c.gpr[3] = c.mmu.read32(0x800000e4);
    c.pc = c.lr;
}
#endif
#ifndef SHSM_CONTEXT_TRANSFER
void func_802138A0(CPUContext& c) {
    events.insert(events.end(), {32, c.gpr[3], 0, 0});
    c.gpr[3] = 0;
    c.pc = c.lr;
}
#endif
#ifndef SHSM_ORIGINAL_SET_CONTEXT
void func_80213830(CPUContext&) { throw ContextBoundary{}; }
#endif
#ifndef SHSM_CONTEXT_TRANSFER
void func_80213920(CPUContext&) { throw ContextBoundary{}; }
#endif
void func_80213A70(CPUContext&) { throw ContextBoundary{}; }
void func_80217500(CPUContext&) { throw ContextBoundary{}; }
namespace nwii::runtime {
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Select MMIO unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { throw std::runtime_error("Select MMIO unavailable"); }
void GX_WGPIPE_Write16(uint16_t) { throw std::runtime_error("Select GX unavailable"); }
void note_null_call(uint32_t, uint32_t) { throw std::runtime_error("Select callback unavailable"); }
}

#ifndef SHSM_EXTERNAL_SELECTOR_MAIN
int main() {
    CPUContext c;
    unsigned disabled, currentState, currentPriority, nextPriority, yield, xer;
    while (std::cin >> disabled >> currentState >> currentPriority >> nextPriority >> yield >> xer) {
        unsigned fpuOwner = 0, initialMsr = 0;
#ifdef SHSM_ORIGINAL_SET_CONTEXT
        std::cin >> fpuOwner >> initialMsr;
#endif
        for (auto span : {std::pair{0x80680000u, 1024u}, {0x80690000u, 1024u}, {0x80492970u, 256u},
                          {0x8052ab00u, 12u}, {0x800000e4u, 4u}, {0x806fffc0u, 96u}}) {
            std::fill(c.mmu.get_ptr(span.first), c.mmu.get_ptr(span.first) + span.second, 0);
        }
#ifdef SHSM_ORIGINAL_SET_CONTEXT
        std::fill(c.mmu.get_ptr(0x800000c0), c.mmu.get_ptr(0x800000dc), 0);
        c.mmu.write32(0x800000d4, currentState ? 0x80690000 : 0);
        c.mmu.write32(0x800000d8, fpuOwner == 1 ? 0x80680000 : fpuOwner == 2 ? 0x80690000 : 0);
        c.mmu.write32(0x8068019c, initialMsr);
        c.mmu.write32(0x8069019c, initialMsr);
        c.msr = initialMsr;
#endif
#ifdef SHSM_CONTEXT_TRANSFER
        for (uint32_t base : {0x80680000u, 0x80690000u}) {
            for (unsigned i = 0; i < 32; ++i) {
                c.mmu.write32(base + i * 4, 0x56780000 + i);
            }
            c.mmu.write32(base + 4, 0x806ff000);
            c.mmu.write32(base + 12, 1);
            c.mmu.write32(base + 52, 0x8052e720);
            c.mmu.write32(base + 0x80, 0x87654321);
            c.mmu.write32(base + 0x84, 0x807f5000);
            c.mmu.write32(base + 0x88, 0x13570000);
            c.mmu.write32(base + 0x8c, xer);
            c.mmu.write32(base + 0x198, 0x807f4000);
            for (unsigned i = 1; i < 8; ++i) {
                c.mmu.write32(base + 0x1a4 + i * 4, i);
            }
        }
        c.srr0 = 0;
        c.srr1 = 0;
        c.gqr.fill(0);
#endif
        c.mmu.write32(0x8052ab00, disabled);
        c.mmu.write32(0x8052ab04, 1);
        c.mmu.write32(0x8052ab08, 1u << (31 - nextPriority));
        c.mmu.write32(0x80528a30,
#ifdef SHSM_DEFAULT_SWITCH_CALLBACK
                          0x8021a1a0
#else
                          0x807f0300
#endif
        );
        c.mmu.write32(0x800000e4, currentState ? 0x80690000 : 0);
        c.mmu.write16(0x806902c8, currentState);
        c.mmu.write32(0x806902d0, currentPriority);
        c.mmu.write16(0x806802c8, 1);
        c.mmu.write32(0x806802d0, nextPriority);
        c.mmu.write32(0x806802dc, 0x80492970 + nextPriority * 8);
        c.mmu.write32(0x80492970 + nextPriority * 8, 0x80680000);
        c.mmu.write32(0x80492974 + nextPriority * 8, 0x80680000);
        for (unsigned i = 0; i < 32; ++i) {
            c.gpr[i] = 0x12340000 + i;
        }
        c.gpr[1] = 0x80700000;
        c.gpr[3] = yield;
        c.gpr[13] = 0x8052e720;
        c.pc = 0x8021a790;
        c.lr = 0x807f0000;
        c.ctr = 0;
        c.xer = xer;
        c.cr.fill({});
        events.clear();
        try {
            func_8021A790(c);
#ifdef SHSM_DEFAULT_SWITCH_CALLBACK
            if (c.pc == 0x8021a1a0) {
                func_8021A1A0(c);
                func_8021A790(c);
            }
#endif
#ifdef SHSM_CONTEXT_TRANSFER
            if (c.pc == 0x8021a890) {
                if (c.gpr[3] != 1) {
                    throw std::runtime_error("Context resumption did not restore saved return value");
                }
                func_8021A790(c);
            }
            if (c.pc != 0x807f0000 && c.pc != 0x807f4000) {
                throw std::runtime_error("Unexpected context continuation");
            }
#endif
        } catch (const ContextBoundary&) {
        }
        uint32_t cr = 0;
        for (const auto& f : c.cr) {
            cr = (cr << 4) | (f.lt << 3) | (f.gt << 2) | (f.eq << 1) | f.so;
        }
        std::cout << c.pc << ' ' << c.lr << ' ' << c.ctr << ' ' << c.xer << ' ' << cr;
        for (auto value : c.gpr) {
            std::cout << ' ' << value;
        }
#ifdef SHSM_ORIGINAL_SET_CONTEXT
        std::cout << ' ' << c.msr;
#endif
#ifdef SHSM_CONTEXT_TRANSFER
        std::cout << ' ' << c.srr0 << ' ' << c.srr1;
        for (unsigned i = 1; i < 8; ++i) {
            std::cout << ' ' << c.gqr[i];
        }
#endif
        std::cout << ' ' << events.size();
        for (auto value : events) {
            std::cout << ' ' << value;
        }
        std::cout << ' ' << std::hex << std::setfill('0');
        for (auto span : {std::pair{0x80680000u, 1024u}, {0x80690000u, 1024u}, {0x80492970u, 256u},
                          {0x8052ab00u, 12u}, {0x800000e4u, 4u}, {0x806fffc0u, 96u}}) {
            for (unsigned i = 0; i < span.second; ++i) {
                std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(span.first)[i]);
            }
        }
#ifdef SHSM_ORIGINAL_SET_CONTEXT
        for (unsigned i = 0; i < 28; ++i) {
            std::cout << std::setw(2) << unsigned(c.mmu.get_ptr(0x800000c0)[i]);
        }
#endif
        std::cout << std::dec << '\n';
    }
}
#endif

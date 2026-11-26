#pragma once
#include "set_mask_pi_boot.h"
#include "loader-bat-seed.h"

extern "C" void func_80217650(nwii::runtime::CPUContext&);

inline int experiment_set_mask_pi_probe() {
    using namespace nwii::runtime;
    SeededBatContext context;
    g_trace_calls = false;
    hw::register_pi(MMIODispatcher::get());
    context.msr = 0x2030;
    context.hid0 = 0xc200;
    for (unsigned index = 0; index < 4; ++index) {
        context.pc = 0x802178a4;
        context.lr = 0x807f6000;
        context.gpr[4] = 0xcc000000;
        context.gpr[5] = 0xf0;
        context.fpscr = (index & 1) * 4;
        hw::pi_intmr = 0xf0;
        hw::pi_intsr = index >= 2 ? 0x10000 : 0;
        const auto registers = context.gpr;
        const auto count = context.inst_count;
        const auto cause = hw::pi_intsr.load();
        func_80217650(context);
        if (context.gpr != registers || context.pc != context.lr || context.fpscr != (index & 1) * 4
            || context.inst_count != count + 1 || hw::pi_intmr.load() != 0xf0 || hw::pi_intsr.load() != cause) {
            return 9;
        }
        std::cout << "PI_FINAL_CASE " << index << ' ' << hw::pi_intmr.load() << ' ' << hw::pi_intsr.load() << '\n';
    }
    unsigned refused = 0;
    for (unsigned mode = 0; mode < 9; ++mode) {
        const auto mask = hw::pi_intmr.load();
        const auto cause = hw::pi_intsr.load();
        const auto mapping = context.dbat[1].lower;
        if (mode == 3) { context.msr = 0xa030; }
        if (mode == 4) { context.hid0 = 0x8200; }
        if (mode == 5) { hw::pi_intmr = 0; }
        if (mode == 6) { hw::pi_intsr = 0x10; }
        if (mode == 7) { context.dbat[1].lower ^= 8; }
        if (mode == 8) { context.in_callback = true; }
        const auto beforeMask = hw::pi_intmr.load();
        const auto beforeCause = hw::pi_intsr.load();
        try {
            experiment_set_mask_pi_write32(context, mode == 0 ? 0xcc003000 : 0xcc003004,
                                           mode == 2 ? 0 : 0xf0, mode == 1 ? 0x802175d0 : 0x802178a4);
        } catch (const std::runtime_error&) {
            ++refused;
        }
        if (hw::pi_intmr.load() != beforeMask || hw::pi_intsr.load() != beforeCause) {
            return 10;
        }
        context.msr = 0x2030;
        context.hid0 = 0xc200;
        context.dbat[1].lower = mapping;
        context.in_callback = false;
        hw::pi_intmr = mask;
        hw::pi_intsr = cause;
    }
    std::cout << "PI_FINAL_GUARDS " << refused << '\n';
    return refused == 9 ? 0 : 11;
}

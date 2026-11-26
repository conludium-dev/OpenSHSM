#pragma once
#include "spd_adapter.h"
#include "loader-bat-seed.h"
#include "loader/loader.h"
#include <iomanip>

extern "C" void func_80005F34(nwii::runtime::CPUContext&);

inline int experiment_template_copy_probe(bool ni = false) {
    using namespace nwii::runtime;
    SeededBatContext context;
    nwii::loader::Executable executable;
    if (!executable.load_dol("work/private-game/disc/DATA/sys/main.dol")) {
        return 4;
    }
    for (const auto& section : executable.sections) {
        auto pointer = context.mmu.get_ptr(section.address);
        if (!pointer || !context.mmu.get_ptr(section.address + section.size - 1)) {
            return 5;
        }
        std::copy(section.data.begin(), section.data.end(), pointer);
        if (section.is_text && !section.data.empty()) {
            context.instructionImages.emplace_back(section.address, section.data);
        }
    }
    g_trace_calls = false;
    for (unsigned index = 0; index < 16; ++index) {
        context.dataLines = {};
        context.replacement.fill(0);
        context.hid0 = 0xc200;
        context.msr = 0x2030;
        context.fpscr = ni ? 4 : 0;
        context.pc = 0x80005f34;
        context.lr = 0x80600004;
        context.xer = 0;
        context.ctr = 0;
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[3] = 0x80500000 + index * 256;
        context.gpr[4] = 0x80211ba0;
        context.gpr[5] = 152;
        const uint32_t destination = context.gpr[3];
        const uint32_t value = 0x38600000 | index;
        auto word = context.mmu.get_ptr(0x80211c08);
        for (unsigned byte = 0; byte < 4; ++byte) {
            word[byte] = value >> (24 - byte * 8);
        }
        for (auto& field : context.cr) {
            field = {};
        }
        try {
            func_80005F34(context);
        } catch (const std::runtime_error& failure) {
            std::cerr << failure.what() << '\n';
            return 7;
        }
        if (context.pc != context.lr || context.lr != 0x80600004 || context.msr != 0x2030 || context.fpscr != (ni ? 4u : 0u)) {
            return 9;
        }
        std::cout << std::dec << index << ' ' << context.gpr[3] << ' ' << std::hex << std::setfill('0');
        for (unsigned offset = 0; offset < 152; ++offset) {
            std::cout << std::setw(2) << unsigned(bat_memory_read8(context, destination + offset));
        }
        std::cout << '\n';
    }
    return 0;
}

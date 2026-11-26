#pragma once
#include "spd_adapter.h"
#include "loader-bat-seed.h"
#include "loader/loader.h"

extern "C" void func_80210800(nwii::runtime::CPUContext&);

inline int experiment_spd_probe() {
    using namespace nwii::runtime;
    SeededBatContext context;
    nwii::loader::Executable executable;
    if (!executable.load_dol("work/private-game/disc/DATA/sys/main.dol")) {
        return 4;
    }
    for (const auto& section : executable.sections) {
        auto destination = context.mmu.get_ptr(section.address);
        if (!destination || !context.mmu.get_ptr(section.address + section.size - 1)) {
            return 5;
        }
        std::copy(section.data.begin(), section.data.end(), destination);
        if (section.is_text && !section.data.empty()) {
            context.instructionImages.emplace_back(section.address, section.data);
        }
    }
    g_trace_calls = false;
    uint32_t prior, cr, xer, ctr, lr;
    while (std::cin >> prior >> cr >> xer >> ctr >> lr) {
        for (auto& value : context.gpr) {
            if (!(std::cin >> value)) {
                return 8;
            }
        }
        context.dataLines = {};
        context.replacement.fill(0);
        context.hid0 = prior;
        context.msr = 0x2030;
        context.lr = lr;
        context.pc = 0x80210800;
        context.xer = xer;
        context.ctr = ctr;
        for (unsigned index = 0; index < 8; ++index) {
            const auto field = (cr >> (28 - index * 4)) & 15;
            context.cr[index].lt = bool(field & 8);
            context.cr[index].gt = bool(field & 4);
            context.cr[index].eq = bool(field & 2);
            context.cr[index].so = bool(field & 1);
        }
        func_80210800(context);
        if (context.pc != lr) {
            return 9;
        }
        for (auto value : context.gpr) {
            std::cout << value << ' ';
        }
        uint32_t actualCr = 0;
        for (const auto& field : context.cr) {
            actualCr = (actualCr << 4) | ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
        }
        std::cout << actualCr << ' ' << context.lr << ' ' << context.ctr << ' ' << context.xer << ' ' << context.msr << ' ' << context.hid0 << '\n';
    }
    context.msr = 0x2030;
    context.hid0 = 0xc200;
    unsigned guards = 0;
    for (uint32_t value : {0xc300u, 0xd200u, 0x8200u}) {
        bool refused = false;
        const auto priorHid0 = context.hid0;
        try {
            experiment_write_hid0_spd(context, value);
        } catch (const std::runtime_error&) {
            refused = true;
        }
        if (!refused || context.hid0 != priorHid0) {
            return 10;
        }
        ++guards;
    }
    context.msr = 0x6030;
    bool refused = false;
    try {
        experiment_write_hid0_spd(context, 0xc200);
    } catch (const std::runtime_error&) {
        refused = true;
    }
    if (!refused || context.hid0 != 0xc200) {
        return 11;
    }
    ++guards;
    std::cout << "SPD_GUARDS " << guards << '\n';
    return std::cin.eof() ? 0 : 8;
}

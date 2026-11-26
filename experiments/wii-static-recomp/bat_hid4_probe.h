#pragma once
#include "bat_memory_frontend.h"

extern "C" void func_80210840(nwii::runtime::CPUContext&);

inline int experiment_bat_hid4_probe() {
    using namespace nwii::runtime;
    BatContext context;
    g_trace_calls = false;
    context.ibat[0] = {0x80001fff, 2};
    context.dbat[0] = {0x80001fff, 2};
    context.dbat[1] = {0xc0001fff, 42};
    context.dbat[3] = {0xa0000002, 0x00700022};
    context.dbat[4] = {0xa0000002, 0x00720022};
    context.instructionImages.emplace_back(0x80210840, std::vector<uint8_t>(80));
    for (const auto& [address, value] : std::array<std::pair<uint32_t, uint32_t>, 2>{{{0x700000, 0x11223344}, {0x720000, 0x55667788}}}) {
        auto bytes = context.mmu.get_ptr(address);
        for (unsigned index = 0; index < 4; ++index) {
            bytes[index] = value >> (24 - index * 8);
        }
    }
    uint32_t cr, xer, ctr, lr;
    while (std::cin >> cr >> xer >> ctr >> lr) {
        for (auto& value : context.gpr) {
            if (!(std::cin >> value)) {
                return 8;
            }
        }
        for (unsigned index = 0; index < 8; ++index) {
            const unsigned field = (cr >> (28 - index * 4)) & 15;
            context.cr[index].lt = bool(field & 8);
            context.cr[index].gt = bool(field & 4);
            context.cr[index].eq = bool(field & 2);
            context.cr[index].so = bool(field & 1);
        }
        context.hid4 = 0x80000000;
        context.hid0 = 0;
        context.msr = 0x2030;
        context.pc = 0x80210840;
        context.lr = lr;
        context.xer = xer;
        context.ctr = ctr;
        func_80210840(context);
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
        std::cout << actualCr << ' ' << context.lr << ' ' << context.ctr << ' ' << context.xer << ' ' << context.msr << ' '
                  << context.hid4 << ' ' << bat_memory_read32(context, 0xa0000000) << '\n';
    }
    return std::cin.eof() ? 0 : 8;
}

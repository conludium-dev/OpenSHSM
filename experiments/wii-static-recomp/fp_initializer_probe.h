#pragma once
#include "loader-bat-seed.h"
#include "loader/loader.h"

extern "C" void func_8000C2F4(nwii::runtime::CPUContext&);

inline int experiment_fp_initializer_probe() {
    using namespace nwii::runtime;
    SeededBatContext context;
    nwii::loader::Executable executable;
    if (!executable.load_dol("work/private-game/disc/DATA/sys/main.dol")) {
        return 1;
    }
    for (const auto& section : executable.sections) {
        auto* bytes = context.mmu.get_ptr(section.address);
        if (!bytes || !context.mmu.get_ptr(section.address + section.size - 1)) {
            return 2;
        }
        std::copy(section.data.begin(),section.data.end(),bytes);
        if (section.is_text && !section.data.empty()) {
            context.instructionImages.emplace_back(section.address,section.data);
        }
    }
    g_trace_calls = false;
    unsigned index,ni;
    int64_t value;
    uint32_t status;
    while (std::cin >> index >> value >> ni >> status) {
        context.dataLines = {};
        context.replacement.fill(0);
        context.hid0 = 0xc200;
        context.msr = 0x2030;
        context.fpscr = status | ni * 4;
        context.gpr.fill(0);
        context.fpr.fill(3.0);
        context.ps1.fill(3.0);
        context.pc = 0x8000c2f4;
        context.lr = 0x80600004;
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        bat_memory_write32(context,0x8052861c,uint32_t(value));
        bat_memory_write32(context,0x80529158,0xa5a5a5a5);
        bat_memory_write32(context,0x8052915c,0xa5a5a5a5);
        func_8000C2F4(context);
        if (context.pc != 0x80600004 || context.lr != 0x80600004 || context.gpr[1] != 0x80540000 || context.msr != 0x2030) {
            return 3;
        }
        std::cout << "FP_INITIALIZER_PROBE " << index << ' ' << bat_memory_read32(context,0x80529158) << ' '
            << bat_memory_read32(context,0x8052915c) << ' ' << std::bit_cast<uint64_t>(context.fpr[0]) << ' '
            << std::bit_cast<uint64_t>(context.ps1[0]) << ' ' << context.fpscr << ' '
            << std::bit_cast<uint64_t>(context.fpr[1]) << ' ' << std::bit_cast<uint64_t>(context.ps1[1]) << '\n';
    }
    return std::cin.eof() ? 0 : 4;
}

#pragma once
#include <processor_adapter.h>
#include <bit>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include "stock_snapshot_cpu_section.h"
#include "stock_snapshot_core.h"

namespace stock_thp_snapshot {

inline void observe(nwii::runtime::CPUContext& cpu) {
    static bool attempted = false;
    const char* path = std::getenv("NWII_THP_SNAPSHOT");
    if (!path || !*path || attempted || cpu.pc != 0x80209D80 || cpu.lr != 0x8009C5E4) {
        return;
    }
    attempted = true;
    static_assert(std::endian::native == std::endian::little);
    const auto& ctx = static_cast<const nwii::runtime::ProcessorContext&>(cpu);
    std::ofstream file(path, std::ios::binary);
    auto write = [&](const auto& value) {
        file.write(reinterpret_cast<const char*>(&value), sizeof(value));
    };
    file.write("SHSMFP01", 8);
    write(ctx.gpr);
    write(ctx.fpr);
    write(ctx.ps1);
    write(ctx.gqr);
    write(ctx.sprg);
    for (const auto& cr : ctx.cr) {
        const uint32_t packed = (uint32_t(cr.lt) << 3) | (uint32_t(cr.gt) << 2)
            | (uint32_t(cr.eq) << 1) | uint32_t(cr.so);
        write(packed);
    }
    for (uint32_t value : {ctx.pc, ctx.lr, ctx.ctr, ctx.xer, ctx.msr, ctx.fpscr, ctx.srr0,
            ctx.srr1, ctx.hid0, ctx.hid2, ctx.dma_u, ctx.dma_l}) {
        write(value);
    }
    write(ctx.inst_count);
    for (const auto* memory : {&ctx.mmu.mem1, &ctx.mmu.mem2, &ctx.mmu.locked_cache}) {
        const uint64_t size = memory->size();
        write(size);
        file.write(reinterpret_cast<const char*>(memory->data()), size);
    }
    file.close();
    std::fprintf(stderr, "[THPSnapshot] saved=%u input=%08x y=%08x u=%08x v=%08x work=%08x\n",
        unsigned(bool(file)), ctx.gpr[3], ctx.gpr[4], ctx.gpr[5], ctx.gpr[6], ctx.gpr[7]);
}

}

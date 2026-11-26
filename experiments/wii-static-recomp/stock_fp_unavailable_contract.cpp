#define main unused_quantization_main
#include "stock_quantization_contract.cpp"
#undef main
#include <processor_adapter.h>
#include "stock_fp_unavailable.h"
#include "fpscr_adapter.h"
#include "selected-fpu.h"
#include <fstream>
#include <memory>
#ifdef STOCK_LAZY_CONTEXT
#include "context-helpers.h"
#endif

namespace nwii::runtime {
bool g_trace_calls = false;
void trace_call(uint32_t, CPUContext&) {}
bool process_pending_callbacks(CPUContext&) { return false; }
bool handle_syscall(CPUContext&) { throw std::runtime_error("unexpected syscall"); }
void GX_WGPIPE_WriteF64(double) { throw std::runtime_error("unexpected GX double write"); }
uint32_t experiment_read_hid2(CPUContext& ctx) { return static_cast<ProcessorContext&>(ctx).hid2; }
void experiment_write_hid2(CPUContext& ctx, uint32_t value) { static_cast<ProcessorContext&>(ctx).hid2 = value; }
uint32_t experiment_read_dma(CPUContext&, unsigned) { throw std::runtime_error("unexpected DMA"); }
void experiment_write_dma(CPUContext&, unsigned, uint32_t) { throw std::runtime_error("unexpected DMA"); }
bool interpret_one(CPUContext&);
}

static void require(bool good, const char* what) {
    if (!good) {
        throw std::runtime_error(what);
    }
}

int main(int argc, char** argv) {
    require(argc == 2, "private DOL required");
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    std::ifstream input(argv[1], std::ios::binary);
    std::vector<uint8_t> dol((std::istreambuf_iterator<char>(input)), {});
    auto word = [&](unsigned offset) {
        require(offset + 4 <= dol.size(), "DOL bounds");
        return (uint32_t(dol[offset]) << 24) | (uint32_t(dol[offset + 1]) << 16)
            | (uint32_t(dol[offset + 2]) << 8) | dol[offset + 3];
    };
    for (unsigned section = 0; section < 18; ++section) {
        const uint32_t offset = word(section * 4), address = word(72 + section * 4);
        const uint32_t size = word(144 + section * 4);
        require(uint64_t(offset) + size <= dol.size(), "DOL section bounds");
        for (uint32_t i = 0; i < size; ++i) {
            ctx.mmu.write8(address + i, dol[offset + i]);
        }
    }
    for (unsigned i = 0; i < 38; ++i) {
        uint32_t opcode = ctx.mmu.read32(0x80211BA0 + i * 4);
        if (i == 26) {
            require(opcode == 0x38600000, "original vector ID");
            opcode = 0x38600007;
        }
        ctx.mmu.write32(0x800 + i * 4, opcode);
    }
    const uint32_t current = 0x80501000, old_owner = 0x80502000, fault = 0x8020AFD4;
    unsigned cases = 0;
#ifdef STOCK_LAZY_CONTEXT
    unsigned baseline_saves = 0, baseline_loads = 0;
#endif
    for (unsigned scenario = 0; scenario < 6; ++scenario) {
        const unsigned owner_case = scenario % 3;
        const bool native = scenario >= 3;
        for (uint32_t msr : {0x9032u, 0x8032u, 0x32u, 0x1002u}) {
            for (unsigned i = 0; i < 32; ++i) {
                ctx.gpr[i] = 0xA0000000u + i;
                ctx.fpr[i] = 1000.25 + i;
                ctx.ps1[i] = -1000.5 - i;
                ctx.mmu.write_f64(current + 0x90 + i * 8, 10.125 + i);
                ctx.mmu.write_f32(current + 0x1C8 + i * 8, float(10.125 + i));
                ctx.mmu.write_f32(current + 0x1CC + i * 8, float(-10.5 - i));
                ctx.mmu.write32(current + i * 4, ctx.gpr[i]);
            }
            ctx.gpr[1] = 0x80504000;
            ctx.mmu.write32(current + 4, ctx.gpr[1]);
            ctx.lr = 0x8009C100; ctx.ctr = 0x13572468; ctx.xer = 0xA0000000;
            ctx.msr = msr; ctx.fpscr = 0; ctx.gqr.fill(0); ctx.hid2 = 0xA0000000;
            ctx.cr[0].lt = true; ctx.cr[0].gt = false;
            ctx.cr[0].eq = false; ctx.cr[0].so = true;
            for (unsigned i = 1; i < 8; ++i) { ctx.cr[i] = {}; }
            ctx.mmu.write16(current + 0x1A2, 1);
            ctx.mmu.write16(old_owner + 0x1A2, 0);
            ctx.mmu.write64(current + 0x190, 0);
            ctx.mmu.write32(0xC0, current & 0x3FFFFFFF);
            ctx.mmu.write32(0xD4, current);
            ctx.mmu.write32(0xD8, owner_case == 0 ? 0 : (owner_case == 1 ? current : old_owner));
            ctx.mmu.write32(0x301C, 0x80213DC0);
            const auto registers = ctx.gpr;
            const auto bank = ctx.fpr;
            const auto secondary = ctx.ps1;
            ctx.mmu.write64(ctx.gpr[1] + 112, 0x123456789ABCDEF0ull);
            ctx.pc = fault;
#ifdef STOCK_LAZY_CONTEXT
            baseline_save(ctx, current);
            baseline_saves += ctx.mmu.read_f64(current + 0x90) != 10.125;
            for (unsigned i = 0; i < 32; ++i) {
                ctx.mmu.write_f64(current + 0x90 + i * 8, 10.125 + i);
                ctx.mmu.write_f32(current + 0x1C8 + i * 8, float(10.125 + i));
                ctx.mmu.write_f32(current + 0x1CC + i * 8, float(-10.5 - i));
            }
            baseline_load(ctx);
            baseline_loads += ctx.fpr != bank || ctx.ps1 != secondary;
            ctx.fpr = bank; ctx.ps1 = secondary; ctx.fpscr = 0;
            lazy_save(ctx, current);
            for (unsigned i = 0; i < 32; ++i) {
                require(ctx.mmu.read_f64(current + 0x90 + i * 8) == 10.125 + i, "HLE overwrote saved scalar bank");
                require(ctx.mmu.read_f32(current + 0x1CC + i * 8) == float(-10.5 - i), "HLE overwrote saved paired bank");
            }
            ctx.gpr.fill(0);
            require(lazy_load(ctx), "HLE integer context load");
            require(ctx.gpr == registers && ctx.pc == fault && ctx.msr == msr, "HLE integer context restore");
            require(ctx.fpr == bank && ctx.ps1 == secondary && ctx.fpscr == 0, "HLE changed physical FPU bank");
            ctx.gpr[3] = current; ctx.pc = 0x80213920;
            ctx.mmu.write16(current + 0x1A2, 3);
            func_80213920(ctx);
            require(ctx.gpr == registers && ctx.pc == fault && ctx.msr == msr, "original OSLoadContext return");
            require(ctx.fpr == bank && ctx.ps1 == secondary && ctx.fpscr == 0, "original OSLoadContext changed physical bank");
#endif
#ifdef STOCK_NONLOCAL_CONTEXT
            ctx.dispatch_saved_ctx = current;
            if (setjmp(ctx.exception_jmp_buf) == 0) {
                if (native) {
                    guarded_original_stfd(ctx);
                } else {
                    nwii::runtime::interpret_one(ctx);
                }
                throw std::runtime_error("FP exception did not exit guest call stack");
            }
#else
            if (native) {
                guarded_original_stfd(ctx);
            } else {
                require(nwii::runtime::interpret_one(ctx), "fault step");
            }
#endif
            require(ctx.pc == 0x800 && ctx.srr0 == fault && ctx.srr1 == (msr & 0x87C0FFFF), "exception state");
            require(ctx.msr == (msr & ~0x4EF36u), "exception mask");
            require(ctx.gpr == registers && ctx.fpr == bank && ctx.ps1 == secondary, "pre-instruction register effects");
            require(ctx.mmu.read64(registers[1] + 112) == 0x123456789ABCDEF0ull, "store before fault");
            unsigned steps = 0;
            while (ctx.pc != 0x80213DC0 && steps++ < 40) {
                nwii::runtime::interpret_one(ctx);
            }
            require(ctx.pc == 0x80213DC0 && ctx.gpr[3] == 7 && ctx.gpr[4] == current, "relocated SDK vector route");
#ifdef STOCK_NONLOCAL_CONTEXT
            require(ctx.dispatch_saved_ctx == current, "FPU vector lost outer HLE interrupt marker");
#endif
            require(ctx.mmu.read32(current + 16) == registers[4], "SPRG0 saved original r4");
            func_80213DC0(ctx);
#ifdef STOCK_NONLOCAL_CONTEXT
            require(ctx.dispatch_saved_ctx == current, "FPU return lost outer HLE interrupt marker");
#endif
            require(ctx.pc == fault && ctx.msr == (msr | 0x2000), "SDK retry return");
            require(ctx.gpr == registers && ctx.lr == 0x8009C100 && ctx.ctr == 0x13572468 && ctx.xer == 0xA0000000, "SDK integer return");
            require(ctx.cr[0].lt && !ctx.cr[0].gt && !ctx.cr[0].eq && ctx.cr[0].so, "SDK CR return");
            require(ctx.mmu.read16(current + 0x1A2) == 1 && ctx.fpscr == 0, "SDK exception flag/FPSCR");
            require(ctx.mmu.read32(0xD8) == current, "SDK ownership");
            for (unsigned i = 0; i < 32; ++i) {
                require(ctx.fpr[i] == (owner_case == 1 ? bank[i] : 10.125 + i), "current scalar bank");
                require(ctx.ps1[i] == (owner_case == 1 ? secondary[i] : -10.5 - i), "current paired bank");
                if (owner_case == 2) {
                    require(ctx.mmu.read_f64(old_owner + 0x90 + i * 8) == bank[i], "old owner scalar saved");
                    require(ctx.mmu.read_f32(old_owner + 0x1CC + i * 8) == float(secondary[i]), "old owner paired saved");
                }
            }
            if (native) {
                guarded_original_stfd(ctx);
            } else {
                nwii::runtime::interpret_one(ctx);
            }
            require(ctx.pc == fault + 4 && ctx.mmu.read_f64(registers[1] + 112) == ctx.fpr[31], "retry original stfd");
            ++cases;
        }
    }
    unsigned faults = 0;
    for (unsigned op = 48; op <= 55; ++op) {
        ctx.mmu.write32(0x80010000, (op << 26) | (31 << 21) | (1 << 16) | 112);
        ctx.pc = 0x80010000; ctx.msr = 0x9032;
        const auto registers = ctx.gpr;
        const auto bank = ctx.fpr;
        ctx.mmu.write64(ctx.gpr[1] + 112, 0x123456789ABCDEF0ull);
#ifdef STOCK_NONLOCAL_CONTEXT
        if (setjmp(ctx.exception_jmp_buf) == 0) {
            nwii::runtime::interpret_one(ctx);
            throw std::runtime_error("Scalar transfer did not exit guest call stack");
        }
#else
        nwii::runtime::interpret_one(ctx);
#endif
        require(ctx.pc == 0x800 && ctx.srr0 == 0x80010000, "scalar transfer guard");
        require(ctx.gpr == registers && ctx.fpr == bank, "update/load side effects before fault");
        require(ctx.mmu.read64(ctx.gpr[1] + 112) == 0x123456789ABCDEF0ull, "transfer before fault");
        ++faults;
    }
    for (uint32_t invalid : {0x9033u, 0x19032u, 0x9072u}) {
        ctx.msr = invalid; ctx.pc = fault; ctx.srr0 = 123; ctx.srr1 = 456;
        bool refused = false;
        try {
            nwii::runtime::stock_scalar_fp_available(ctx, fault);
        } catch (const std::runtime_error&) {
            refused = true;
        }
        require(refused && ctx.msr == invalid && ctx.pc == fault && ctx.srr0 == 123 && ctx.srr1 == 456, "unsupported profile atomic refusal");
    }
    std::printf("PASS %u original relocated-vector/native-SDK/owner/retry cases; %u scalar transfer faults; 3 unsupported profiles refused\n", cases, faults);
#ifdef STOCK_LAZY_CONTEXT
    require(baseline_saves == 24 && baseline_loads == 24, "baseline defect not reproduced");
    std::printf("PASS lazy HLE context: 24 original OSLoadContext physical-bank matches; baseline 24 save/24 load policy violations\n");
#endif
}

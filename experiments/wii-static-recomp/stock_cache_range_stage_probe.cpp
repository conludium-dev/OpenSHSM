#include <processor_adapter.h>
#include <array>
#include <cassert>
#include <fstream>
#include <memory>
#include <cstdio>

extern "C" void func_80212FA0(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    assert(argc == 2);
    auto owned = std::make_unique<nwii::runtime::CPUContext>();
    auto& ctx = *owned;
    std::ofstream file(argv[1], std::ios::binary);
    auto write = [&](const auto& value) {
        file.write(reinterpret_cast<const char*>(&value), sizeof(value));
    };
    unsigned cases = 0;
    auto execute = [&](uint32_t pc, uint32_t address, uint32_t length, bool full_entry) {
        ctx.gpr.fill(0);
        ctx.gpr[3] = address;
        ctx.gpr[4] = length;
        ctx.gpr[5] = 0x12345678;
        ctx.pc = pc;
        ctx.lr = 0x80001000;
        ctx.ctr = 3;
        if (!full_entry) {
            ctx.gpr[5] = address & 31;
            if (pc == 0x80212FB0) {
                ctx.gpr[4] = length + (address & 31);
            } else if (pc == 0x80212FB4) {
                ctx.gpr[4] = length + (address & 31) + 31;
            } else if (pc >= 0x80212FB8) {
                ctx.gpr[4] = 1;
            }
            ctx.ctr = 1;
            if (pc >= 0x80212FC4) {
                ctx.gpr[3] += 32;
            }
            if (pc == 0x80212FC8) {
                ctx.ctr = 0;
            }
        }
        ctx.xer = 0;
        ctx.msr = 0x2000;
        ctx.inst_count = 12345;
        ctx.dispatch_saved_ctx = 0;
        ctx.in_callback = false;
        for (auto& field : ctx.cr) {
            field.lt = false; field.gt = true; field.eq = false; field.so = false;
        }
        assert(setjmp(ctx.exception_jmp_buf) == 0);
        func_80212FA0(ctx);
        assert(ctx.pc == ctx.lr && ctx.msr == 0x2000);
        if (full_entry) {
            if (length == 0) {
                assert(ctx.gpr[3] == address && ctx.gpr[4] == 0);
                assert(ctx.ctr == 3 && ctx.gpr[5] == 0x12345678);
                assert(ctx.inst_count == 12347 && ctx.cr[0].eq && !ctx.cr[0].gt);
            } else {
                const uint32_t count = (length + (address & 31) + 31) >> 5;
                assert(ctx.gpr[3] == address + count * 32 && ctx.gpr[4] == count);
                assert(ctx.gpr[5] == (address & 31) && ctx.ctr == 0);
                assert(ctx.inst_count == 12345 + 9 + uint64_t(count) * 2);
                assert(ctx.cr[0].gt && !ctx.cr[0].eq);
            }
        }
        write(ctx.gpr); write(ctx.fpr); write(ctx.ps1); write(ctx.gqr); write(ctx.cr);
        write(ctx.pc); write(ctx.lr); write(ctx.ctr); write(ctx.xer); write(ctx.msr); write(ctx.inst_count);
        ++cases;
    };
    for (uint32_t align = 0; align < 32; ++align) {
        for (uint32_t length : {0u, 1u, 31u, 32u, 33u, 307200u, 460800u}) {
            execute(0x80212FA0, 0x91000000 + align, length, true);
        }
    }
    for (uint32_t pc = 0x80212FA4; pc <= 0x80212FC8; pc += 4) {
        execute(pc, 0x91000003, 3, false);
    }
    assert(file && cases == 234);
    std::puts("ACTUAL_CACHE_RANGE_ALIGN32_LENGTH7_RESUME10_PPC_ENDPOINT_PASS234");
}
